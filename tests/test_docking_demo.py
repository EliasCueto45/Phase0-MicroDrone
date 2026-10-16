import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from docking.run_docking import run_demo
from docking.states import DockingState


class DockingDemoTests(unittest.TestCase):
    def run_scenario(self, scenario):
        stream = io.StringIO()
        state = run_demo(stream, scenario)
        events = [json.loads(line) for line in stream.getvalue().splitlines()]
        self.assertEqual(len(events), 6)
        self.assertTrue(all(event["synthetic"] for event in events))
        self.assertTrue(all(event["update"]["reason"] for event in events))
        self.assertTrue(all(event["update"]["phase"] == event["update"]["state"]
                            for event in events))
        self.assertTrue(all(event["frame"] == "local_enu" for event in events))
        self.assertTrue(all(event["origin_id"] == "demo_world" for event in events))
        return state, events

    def test_success_records_alignment_and_waiting_updates(self):
        state, events = self.run_scenario("success")
        self.assertEqual(state, DockingState.COMPLETE)
        self.assertEqual(
            [event["update"]["state"] for event in events],
            ["approach", "align", "align", "descend", "descend", "complete"],
        )
        self.assertEqual(events[0]["inputs"]["x_error_m"], 5.0)
        self.assertEqual(events[-1]["alignment"]["horizontal_error_m"], 0.0)
        self.assertTrue(events[-1]["inputs"]["vehicle"]["landing_settled"])
        self.assertTrue(events[-1]["update"]["landed_on_pad"])

    def test_missing_stale_and_cart_moving_scenarios_abort(self):
        for scenario in ("missing", "stale", "cart-moving"):
            with self.subTest(scenario=scenario):
                state, events = self.run_scenario(scenario)
                self.assertEqual(state, DockingState.ABORT)
                last = events[-1]
                self.assertEqual(last["update"]["previous_state"], "descend")
                if scenario == "missing":
                    self.assertFalse(last["alignment"]["valid"])
                    self.assertIsNone(last["inputs"]["x_error_m"])
                elif scenario == "stale":
                    self.assertGreater(
                        last["update"]["timestamp_ns"]
                        - last["inputs"]["alignment_timestamp_ns"], 500_000_000
                    )
                else:
                    self.assertEqual(last["update"]["reason"], "approach_permission_lost")

    def test_low_battery_requests_return_and_allows_landing(self):
        state, events = self.run_scenario("low-battery")
        self.assertEqual(state, DockingState.COMPLETE)
        self.assertTrue(events[0]["update"]["should_dock"])
        self.assertIn("low_battery", events[0]["update"]["reasons"])

    def test_unknown_scenario_is_rejected_before_logging(self):
        stream = io.StringIO()
        with self.assertRaises(ValueError):
            run_demo(stream, "unknown")
        self.assertEqual(stream.getvalue(), "")

    def test_cli_writes_parseable_log(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as folder:
            log = Path(folder) / "docking.jsonl"
            result = subprocess.run(
                [sys.executable, "-B", "-m", "docking.run_docking",
                 "--scenario", "success", "--log", str(log)],
                cwd=root, capture_output=True, text=True, check=True,
            )
            events = [json.loads(line) for line in log.read_text().splitlines()]
        self.assertEqual(result.stdout, "")
        self.assertIn("complete", result.stderr)
        self.assertEqual(events[-1]["update"]["state"], "complete")


if __name__ == "__main__":
    unittest.main()
