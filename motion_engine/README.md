# Motion Engine — Phase 0

[Phase 0 scope: Start Here](../START_HERE.md)

## Purpose

Translate permitted high-level movement targets into PX4 external-control commands. PX4 supplies low-level flight stabilization in simulation. Building a replacement flight PID or directly driving motors is not required for this semester.

## Inputs and outputs

- Inputs: navigation/docking targets, estimated vehicle state, safety decisions.
- Outputs: bounded PX4 position or velocity targets and yaw commands; command/status logs.
- Define units, coordinate frames, command expiration, and external-control lifecycle before connecting modules.
- Log requested and sent targets separately from observed vehicle motion.

## First tasks

1. Establish a PX4 connection and read status/telemetry.
2. Reproduce takeoff, hold, and landing in the stock simulation.
3. Define a bounded command interface with navigation and safety.
4. Handle rejected commands, stale requests, and loss of the control connection.
5. Execute waypoint and docking targets through the same interface.

Maintain the command stream required by the selected PX4 interface and verify its loss-of-control behavior. Start from the [PX4 offboard example](https://docs.px4.io/main/en/ros2/offboard_control), using documentation matching the pinned release.

## Acceptance evidence

A repeatable flight script takes off, holds, and lands while recording targets and telemetry. Tests demonstrate bounds enforcement, command expiration, and the chosen abort behavior.

A controlled mission abort and motor termination are distinct actions. Do not implement one ambiguous “kill switch” for both.

Implementation files and run commands have not yet been created.
