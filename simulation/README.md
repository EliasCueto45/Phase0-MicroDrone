# Simulation and Integration — Phase 0

[Central proposal](../START_HERE.md)

## Purpose

Provide a reproducible environment for camera processing, waypoint flight, safety tests, and return-to-pad behavior. The proposed simulator is Gazebo with PX4 SITL, replacing the earlier Webots outline.

This folder currently contains documentation and placeholders. No project world, launcher, or verified installation procedure exists yet.

## Candidate environment

- Ubuntu 24.04
- ROS 2 Jazzy
- Gazebo Harmonic
- A pinned compatible PX4 release
- Python and OpenCV for application modules

Validate the combination on a reference machine, then record exact versions, dependency installation, launch commands, and known platform limitations. Use upstream instructions matching the selected release, not a mixture of release and development-branch examples.

References:
- [PX4 Gazebo simulation](https://docs.px4.io/v1.17/en/sim_gazebo_gz/index)
- [PX4 ROS 2 integration](https://docs.px4.io/main/en/ros2/user_guide)
- [PX4 offboard control example](https://docs.px4.io/main/en/ros2/offboard_control)

## Setup sequence

1. Launch an existing PX4 quadrotor model in a simple Gazebo world.
2. Verify vehicle status, takeoff, hold, and landing.
3. Expose timestamped telemetry to the application.
4. Expose camera frames and calibration data through the chosen Gazebo/ROS 2 bridge.
5. Add a stationary landing pad with an ArUco marker.
6. Check camera placement for marker visibility during approach and descent.
7. Document a clean-checkout setup and have another member reproduce it.

Keep the initial world simple. A stock vehicle validates software integration; it is not evidence that future MDL hardware has matching flight performance.

## Shared integration responsibilities

- Agree simulation time, message timestamps, topic names, and coordinate frames.
- Keep reference ground truth available for evaluation without silently substituting it for perception or estimated state.
- Provide repeatable mission/reset procedures and record scenario configuration.
- Add controlled cases for marker loss, stale telemetry, command loss, geofence violations, and low battery.
- Track third-party model, texture, and fixture sources/licenses.

CV can work on saved images and motion/navigation can test with fake telemetry while this setup proceeds.

## Acceptance evidence

**First milestone:** a second member follows the instructions, launches the stock simulation, reads telemetry, and views a camera frame.

**Semester milestone:** repeatable waypoint flight and marker-assisted landing on a stationary pad, with logs, landing-error measurements, and defined failure outcomes.

Detailed cart scenery and moving-dock abort scenarios are stretch work. Physical charging and moving-platform landing are not required.
