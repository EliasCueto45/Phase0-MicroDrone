# Safety Layer — Phase 0

[Central proposal](../START_HERE.md)

## Purpose

Enforce application-level constraints on simulated mission commands from the first flight milestone. PX4's own failsafes remain active. Simulation tests demonstrate behavior under specified conditions; they do not establish hardware safety.

Motion/navigation leads implementation, with CV and simulation supplying observation failure cases and test scenarios.

## Inputs and outputs

- Inputs: vehicle-state freshness, requested targets, configured limits/geofence, simulated battery status, operator abort, and docking/vision validity.
- Outputs: permitted action or override, reason, timestamp, and event logs.
- All mission and docking targets pass through enforcement before being sent to PX4.
- Missing or stale required inputs must have explicit behavior.

## First tasks

1. Define position/velocity limits, geofence, and state/command timeouts.
2. Define controlled abort behavior for each flight state.
3. Reject or constrain invalid targets before transmission.
4. Inject stale telemetry, command loss, and low battery in simulation.
5. Test marker loss during docking with the docking team.

Distinguish a controlled abort (such as hold or land under specified conditions) from motor termination. Document when each action is available. Avoid blanket rules that disable stabilization while demanding a controlled landing.

Threat interpretation and anti-habituation randomization do not belong in safety enforcement. Human-detection behavior is not a required CV capability this semester; any synthetic occupancy test must be labeled as such.

## Acceptance evidence

Each scenario records the input condition, expected response, observed response, and timing. Agree thresholds and pass/fail criteria before testing. Verify that ordinary mission commands cannot override an active constraint.

Implementation files and run commands have not yet been created.
