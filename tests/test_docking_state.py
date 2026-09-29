import unittest

from docking.states import DockingState


class DockingStateTests(unittest.TestCase):
    def test_docking_states_have_expected_values(self):
        expected = {
            "IDLE": "idle",
            "APPROACH": "approach",
            "SEARCH": "search",
            "ALIGN": "align",
            "DESCEND": "descend",
            "COMPLETE": "complete",
            "ABORT": "abort",
        }

        self.assertEqual(
            {name: state.value for name, state in DockingState.__members__.items()},
            expected,
        )

    def test_docking_state_can_be_loaded_from_string(self):
        for state in DockingState:
            with self.subTest(state=state):
                self.assertIs(DockingState(state.value), state)

    def test_unknown_docking_state_is_rejected(self):
        with self.assertRaises(ValueError):
            DockingState("unknown")


if __name__ == "__main__":
    unittest.main()
