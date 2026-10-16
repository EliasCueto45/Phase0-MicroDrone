"""Replay recorded docking inputs for module diagnostics, without a mission loop."""

import argparse
from dataclasses import replace
from pathlib import Path
import sys
from typing import TextIO

from docking.alignment import LocalPosition, calculate_alignment
from docking.states import DockingController, DockingState, PadObservation
from docking.utils.docking_log import write_docking_event
from motion_engine.contracts import CommandStatus, Pose, VehicleFeedback
from safety_layer.safety_policy import SafetyAssessment

SCENARIOS = ('success', 'missing', 'stale', 'low-battery', 'cart-moving')


def run_demo(stream: TextIO, scenario: str = 'success') -> DockingState:
    """Replay fixed observations; mission entry and landing are fixture events.

    The production coordinator owns mission state, dispatch, and safety checks.
    This diagnostic does not run Motion or dispatch the proposed commands.
    """
    if scenario not in SCENARIOS:
        raise ValueError(f'Unknown scenario: {scenario}')
    controller = DockingController()
    pad_pose = Pose(10, 20, 0, 0)
    pad = LocalPosition(10, 20, 'demo_world')
    poses = [Pose(5, 15, 5), Pose(10, 20, 5), Pose(9.7, 19.7, 5),
             Pose(10, 20, 5), Pose(10, 20, 2), Pose(10, 20, 0)]
    for step, pose in enumerate(poses):
        now_ns = step * 100_000_000
        timestamp_ns = now_ns
        position = LocalPosition(pose.x, pose.y, 'demo_world', yaw_deg=pose.yaw_deg)
        if step == 5 and scenario == 'missing':
            position = None
        if step == 5 and scenario == 'stale':
            timestamp_ns = 0
            now_ns = 600_000_000
        alignment = calculate_alignment(pad, position, timestamp_ns)
        landed = step == 5
        vehicle = VehicleFeedback(
            timestamp_ns=now_ns, pose=pose, armed=True,
            airborne=not landed, grounded=landed, emergency_descent=False,
            landing_settled=landed, active_command_id='fixture-descent' if landed else None,
            active_kind='DESCEND_TO_DOCK' if landed else None,
            target=pad_pose if landed else None,
            status=CommandStatus.LANDED if landed else CommandStatus.IN_PROGRESS,
            arrived=landed, distance_to_target_m=None, horizontal_error_m=None,
            vertical_error_m=None, yaw_error_deg=None,
        )
        cart_moving = step == 5 and scenario == 'cart-moving'
        low = scenario == 'low-battery'
        safety = SafetyAssessment(
            permissions={'approach': not cart_moving, 'descent': not cart_moving,
                         'tracking': not low, 'hold': True},
            battery_low=low, reasons=('low_battery',) if low else (),
            timestamp_ns=now_ns,
        )
        inputs = replace(
            alignment.to_docking_input(), mission_state='DOCKING_APPROACH',
            flight_active=not landed, vehicle=vehicle,
            pad=PadObservation(pad_pose, now_ns), safety=safety,
            cart_moving=cart_moving, environment_valid=True,
            environment_timestamp_ns=now_ns, bird_detected=True, bird_valid=True,
            bird_timestamp_ns=now_ns,
        )
        update = controller.update(inputs, now_ns)
        write_docking_event(stream, inputs, update, alignment, pad.origin_id)
    return controller.state


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scenario', choices=SCENARIOS, default='success')
    parser.add_argument('--log', type=Path, help='Write diagnostic JSONL instead of stdout')
    args = parser.parse_args(argv)
    if args.log is None:
        state = run_demo(sys.stdout, args.scenario)
    else:
        with args.log.open('w', encoding='utf-8') as stream:
            state = run_demo(stream, args.scenario)
    print(f'Synthetic docking outcome: {state.value}', file=sys.stderr)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
