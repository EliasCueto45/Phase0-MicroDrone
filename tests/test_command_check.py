"""Tests for the second safety check: checking one actual order.

Run this from the main project folder:
    python -m unittest tests.test_command_check -v
"""

import unittest

from safety_layer import config
from safety_layer.command_check import Command, check_command
from safety_layer.safety_policy import assess
from tests.test_safety_policy import NOW, snapshot


def good_order(**changes):
    """A perfectly safe order, unless a test changes something."""
    base = dict(
        command_id="cmd-1",
        kind="track",
        x_m=10.0,
        y_m=10.0,
        z_m=15.0,
        horizontal_speed_mps=4.0,
        vertical_speed_mps=1.0,
        yaw_rate_dps=30.0,
        issued_ns=NOW,
        source="navigation",
    )
    base.update(changes)
    return Command(**base)


def all_clear():
    """The first safety check's answer when nothing is wrong."""
    return assess(snapshot(), NOW)


class TestGoodOrder(unittest.TestCase):
    def test_safe_order_passes_through_unchanged(self):
        decision = check_command(good_order(), all_clear(), NOW)
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.command.command_id, "cmd-1")
        self.assertEqual(decision.reasons, ())


class TestExpiredOrders(unittest.TestCase):
    def test_old_order_is_replaced_with_hold(self):
        """Orders last 0.2 s. This one is half a second old."""
        old = good_order(issued_ns=NOW - int(0.5 * config.NS_PER_S))
        decision = check_command(old, all_clear(), NOW)
        self.assertFalse(decision.allowed)
        self.assertIn("command_expired", decision.reasons)
        self.assertEqual(decision.command.kind, "hold")

    def test_order_from_the_future_is_rejected(self):
        future = good_order(issued_ns=NOW + config.NS_PER_S)
        decision = check_command(future, all_clear(), NOW)
        self.assertIn("command_expired", decision.reasons)


class TestLimits(unittest.TestCase):
    def test_outside_the_fence_is_replaced(self):
        far_away = good_order(x_m=200.0, y_m=0.0)  # fence is 150 m
        decision = check_command(far_away, all_clear(), NOW)
        self.assertIn("geofence_breach", decision.reasons)
        self.assertEqual(decision.command.kind, "hold")

    def test_too_high_is_replaced(self):
        too_high = good_order(z_m=45.0)            # ceiling is 30 m
        decision = check_command(too_high, all_clear(), NOW)
        self.assertIn("altitude_ceiling", decision.reasons)

    def test_too_fast_sideways_is_replaced(self):
        too_fast = good_order(horizontal_speed_mps=9.0)   # limit is 5
        decision = check_command(too_fast, all_clear(), NOW)
        self.assertIn("horizontal_speed_limit", decision.reasons)

    def test_too_fast_downward_is_replaced(self):
        too_fast = good_order(vertical_speed_mps=6.0)     # limit is 2
        decision = check_command(too_fast, all_clear(), NOW)
        self.assertIn("vertical_speed_limit", decision.reasons)

    def test_replacement_order_stops_the_drone(self):
        """The swapped-in order must have zero speed, not just a new name."""
        decision = check_command(good_order(z_m=45.0), all_clear(), NOW)
        self.assertEqual(decision.command.horizontal_speed_mps, 0.0)
        self.assertEqual(decision.command.vertical_speed_mps, 0.0)


class TestPermissionsAreRespected(unittest.TestCase):
    def test_tracking_order_blocked_when_tracking_is_not_allowed(self):
        low_battery = assess(snapshot(battery={"percent": 15.0}), NOW)
        decision = check_command(good_order(kind="track"), low_battery, NOW)
        self.assertFalse(decision.allowed)
        self.assertIn("action_not_permitted", decision.reasons)

    def test_unknown_order_kind_is_refused(self):
        decision = check_command(good_order(kind="do_a_backflip"), all_clear(), NOW)
        self.assertIn("unknown_command_kind", decision.reasons)


class TestCartMovingDuringDescent(unittest.TestCase):
    """The scenario Section 11 calls out by name."""

    def test_cart_starts_moving_while_coming_down(self):
        # The drone is descending onto the pad, then the cart starts rolling.
        moving = assess(snapshot(environment={"cart_moving": True}), NOW)
        descending = good_order(kind="descend", z_m=2.0, vertical_speed_mps=1.0)
        decision = check_command(descending, moving, NOW)

        # The descent order must be swapped out in this same tick.
        self.assertFalse(decision.allowed)
        self.assertNotEqual(decision.command.kind, "descend")
        self.assertEqual(decision.command.vertical_speed_mps, 0.0)
        self.assertIn("action_not_permitted", decision.reasons)


class TestEmergency(unittest.TestCase):
    def test_emergency_replaces_any_order_with_landing(self):
        dying_battery = assess(snapshot(battery={"percent": 4.0}), NOW)
        decision = check_command(good_order(), dying_battery, NOW)
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.command.kind, "emergency_land")
        self.assertIn("emergency", decision.reasons)

    def test_emergency_beats_an_otherwise_fine_order(self):
        """Even a perfect order gets replaced during an emergency."""
        no_signal = assess(snapshot(environment={"comm_ok": False}), NOW)
        decision = check_command(good_order(kind="hold"), no_signal, NOW)
        self.assertEqual(decision.command.kind, "emergency_land")


class TestSeveralProblemsAtOnce(unittest.TestCase):
    def test_every_problem_is_listed(self):
        bad = good_order(x_m=300.0, z_m=50.0, horizontal_speed_mps=12.0)
        decision = check_command(bad, all_clear(), NOW)
        self.assertIn("geofence_breach", decision.reasons)
        self.assertIn("altitude_ceiling", decision.reasons)
        self.assertIn("horizontal_speed_limit", decision.reasons)


if __name__ == "__main__":
    unittest.main()
