from dataclasses import replace
import unittest

from docking.alignment import LocalPosition, calculate_alignment


class DockingAlignmentTests(unittest.TestCase):
    def setUp(self):
        self.pad = LocalPosition(10.0, 20.0, "test_world")

    def test_centered_position_has_zero_error(self):
        result = calculate_alignment(self.pad, self.pad, 1_000_000_000)
        self.assertTrue(result.valid)
        self.assertEqual(result.horizontal_error_m, 0.0)
        self.assertEqual(result.x_error_m, 0.0)
        self.assertEqual(result.y_error_m, 0.0)

    def test_offset_direction_and_distance(self):
        vehicle = LocalPosition(13.0, 16.0, "test_world")
        result = calculate_alignment(self.pad, vehicle, 1_000_000_000)
        self.assertEqual(result.x_error_m, -3.0)
        self.assertEqual(result.y_error_m, 4.0)
        self.assertEqual(result.horizontal_error_m, 5.0)
        reverse = calculate_alignment(vehicle, self.pad, 1_000_000_000)
        self.assertEqual(reverse.x_error_m, 3.0)
        self.assertEqual(reverse.y_error_m, -4.0)

    def test_missing_mismatched_or_nonfinite_positions_are_unavailable(self):
        for vehicle in (
            None,
            replace(self.pad, frame="local_ned"),
            replace(self.pad, origin_id="other_world"),
            replace(self.pad, origin_id=""),
            replace(self.pad, x_m=float("nan")),
            replace(self.pad, y_m=float("inf")),
        ):
            with self.subTest(vehicle=vehicle):
                result = calculate_alignment(self.pad, vehicle, 1_000_000_000)
                self.assertFalse(result.valid)
                self.assertIsNone(result.horizontal_error_m)
                self.assertIsNone(result.to_docking_input().x_error_m)
                self.assertTrue(result.reason)
        self.assertFalse(calculate_alignment(None, self.pad, 1_000_000_000).valid)
        self.assertFalse(calculate_alignment(
            replace(self.pad, x_m=float("inf")), self.pad, 1_000_000_000
        ).valid)

    def test_invalid_timestamps_and_overflow_are_unavailable(self):
        for timestamp in (None, -1, True, 1.0, float("nan"), float("inf")):
            with self.subTest(timestamp=timestamp):
                result = calculate_alignment(self.pad, self.pad, timestamp)
                self.assertFalse(result.valid)
                self.assertIsNone(result.timestamp_ns)
        result = calculate_alignment(
            LocalPosition(1e308, 0, "test_world"),
            LocalPosition(-1e308, 0, "test_world"), 1_000_000_000,
        )
        self.assertFalse(result.valid)

    def test_yaw_wrap_and_controller_input_conversion(self):
        pad = replace(self.pad, yaw_deg=1)
        vehicle = replace(self.pad, yaw_deg=359)
        result = calculate_alignment(pad, vehicle, 100)
        self.assertEqual(result.yaw_error_deg, 2)
        inputs = result.to_docking_input()
        self.assertEqual(inputs.alignment_timestamp_ns, 100)
        self.assertEqual(inputs.yaw_error_deg, 2)
        self.assertEqual(inputs.x_error_m, 0)
        self.assertTrue(inputs.alignment_valid)


if __name__ == "__main__":
    unittest.main()
