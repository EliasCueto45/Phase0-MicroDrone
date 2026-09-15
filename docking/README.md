# Docking — Phase 0

[Central proposal](../README.md)

## Purpose

Return to and land on a stationary marked pad in simulation. “Docking” means landing within an agreed tolerance; charging, magnetic contact, and moving-platform landing are outside the required demonstration.

Motion/navigation owns the docking sequence, CV owns marker observations, and simulation owns the pad and evaluation scenario.

## Inputs and outputs

- Inputs: estimated vehicle state, timestamped marker-relative pose, known pad configuration, safety constraints.
- Outputs: alignment/descent targets through motion and safety, docking state, completion/failure status, and logs.
- Define conversions from camera-relative observations into the command frame before integration.

## First tasks

1. Define approach, search, align, descend, complete, and abort transitions.
2. Return to a known pad vicinity using navigation.
3. Use marker observations for final alignment.
4. Define limits, alignment tolerance, detection freshness, and descent conditions.
5. Handle marker loss and aborts with safety.
6. Measure landing position error over repeated trials.

Ensure the simulated camera can see the marker during the intended sequence. Distinguish navigating to known pad coordinates from demonstrating visual alignment.

## Acceptance evidence

The drone approaches, aligns, and lands within the agreed tolerance. Logs show observations and transition reasons. Tests include lost/stale markers and low-battery behavior. A land command alone does not count as confirmed landing; define completion using vehicle status and evaluation data.

Implementation files and run commands have not yet been created.
