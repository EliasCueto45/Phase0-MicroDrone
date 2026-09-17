# Computer Vision — Phase 0

[Team onboarding: Start Here](../START_HERE.md)

## Architecture authority

This guide implements the final Phase 0 Architecture Clarification for CV. That clarification supersedes the initial proposal and the README changes committed on September 11 and September 16. Where older onboarding material differs, the final clarification takes precedence.

## Purpose and scope

Produce timestamped observations for other modules to consume. Phase 0 is limited to synthetic frames, preprocessing, logging, and a simple detection stub, so work can proceed before Gazebo is ready.

CV owns observation production only. Navigation owns mission logic, docking owns alignment and descent logic, and safety owns permission and override decisions. CV does not select actions or issue movement commands.

## Camera configuration

| Camera ID | Role | Phase 0 implementation |
| --- | --- | --- |
| `front` | Forward sensing and the general CV pipeline | Synthetic frames, preprocessing, and timestamped detection stubs |
| `downward` | Observations supporting alignment and descent | Synthetic frames and explicitly synthetic alignment inputs |

The front/rear concept is retired. A rear camera has no role in Phase 0 or Phase 1. The downward camera is required for Phase 1 marker detection and pose estimation, but Phase 0 does not require either capability.

No IR or depth sensors are used in Phase 0. Synthetic alignment values are test fixtures, not measurements from a depth sensor or a pose estimator.

## Inputs and outputs

- Inputs: generated test frames or saved synthetic fixtures, timestamps, and camera identity.
- Outputs: timestamp, camera ID, image dimensions, placeholder label/bounding box in documented pixel coordinates, and validity.
- Label stub output as synthetic. Include explicit empty/invalid cases and never present an old observation as current.
- A stub bounding box is not a measured 3D position and must not be used as one.

Use `front` and `downward` consistently for camera identity. Document image dimensions and bounding-box conventions, including any changes made by preprocessing. Keep synthetic alignment fixtures separate from image-space detection boxes, with explicit units, frame, timestamp, source, and validity agreed with docking.

## Cart occupancy and size-class observations

The cart-sensor observation contract must represent occupancy and these size classes:

| Size class | Meaning |
| --- | --- |
| `SMALL` | Bird-scale object |
| `LARGE` | Human-scale object |

In Phase 0, supply these observations through deterministic synthetic fixtures. Size class is prescribed by the fixture; a pixel bounding box alone does not establish physical object size or identity. The cart sensor's physical implementation is not specified here.

Include timestamp, source ID, occupancy, size class, validity, and a synthetic-source flag. For an empty fixture, report unoccupied with no size class. For invalid or unavailable input, report invalid rather than silently treating it as unoccupied or `SMALL`.

The consuming decision module applies the architecture rule: only bird-scale (`SMALL`) objects may trigger deterrence; `LARGE` objects, including humans, do not trigger it. CV reports observations and does not trigger deterrence. A `SMALL` observation is not an unconditional action command and does not bypass safety or mission rules.

## Integration boundaries

- **Docking:** Phase 0 uses synthetic alignment inputs. Landing is evaluated against a defined tolerance. The planned larger pad uses magnetic capture for final mechanical alignment; CV is not responsible for precise pin alignment or mechanical capture.
- **Cart motion:** if the cart moves, the mission must return toward the docking station or enter a defined safe state. Docking on a moving platform is excluded from both Phase 0 and Phase 1. Returning toward the station is not permission to land while it is moving. Mission, docking, and safety modules own this response; CV must not infer cart motion from an occupancy label.
- **Sensing rotation:** the drone performs a controlled yaw rotation during sensing to improve coverage for both cameras and future sensors. Either direction is acceptable. Motion/navigation owns rotation commands; CV continues publishing timestamped, camera-identified observations during the sequence.

## First tasks

1. Create a repeatable synthetic frame source.
2. Add simple preprocessing with documented input/output formats.
3. Produce deterministic detection-stub observations for both camera IDs, including empty and invalid cases.
4. Add synthetic cart occupancy fixtures for `SMALL`, `LARGE`, unoccupied, and invalid input.
5. Agree the synthetic alignment-input contract with docking; do not implement pose estimation.
6. Log frames and observations with timestamps, source identity, validity, and synthetic-source flags.
7. Demonstrate publication to consuming modules using repeatable fixtures, including a simulated sensing-rotation sequence.

Keep forward-camera and downward-camera observations distinguishable through camera IDs. Other modules decide how to use these observations.

## Acceptance evidence

The required demo generates or reads synthetic frames, preprocesses them, and publishes/logs timestamped stub observations. Verify:

- The same fixture and frame index reproduce the same pixels and observation metadata.
- Front and downward outputs retain distinct camera IDs.
- Occupancy fixtures cover both size classes, empty scenes, and invalid input.
- Synthetic alignment inputs remain distinguishable from image-space detections and real measurements.
- Timestamps and source IDs remain meaningful across the simulated sensing sequence.
- No CV output directly issues mission, docking, deterrence, or safety commands.

Consumers can test their interfaces without a working detector. Integration tests owned by the consuming modules should verify that `LARGE` observations do not trigger deterrence and that cart motion never permits moving-platform docking.

## Standardized environment

| Component | Team baseline |
| --- | --- |
| Operating system | Ubuntu 24.04 Noble |
| Autopilot | PX4 1.17 |
| Simulated world | Gazebo Harmonic |
| Module communication bridge | ROS 2 Jazzy |

The table records the agreed architecture, not a verified installation procedure. Offline synthetic-frame work can proceed with Python and OpenCV while the shared environment is finalized.

## Stretch and future work

2D marker detection is a stretch goal, not a dependency for Phase 0 completion. It may publish marker IDs and image corners through the observation interface. See the [OpenCV ArUco tutorial](https://docs.opencv.org/4.13.0/d5/dae/tutorial_aruco_detection.html).

Pose estimation begins in Phase 1, using the downward camera. It is not a Phase 0 deliverable. Further work will be scoped separately.

Python and OpenCV are sufficient for the required Phase 0 pipeline; model training is not required.
