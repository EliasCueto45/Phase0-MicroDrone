# Computer Vision — Phase 0

[Phase 0 scope: Start Here](../START_HERE.md)

## Purpose and scope

Produce timestamped observations for other modules to consume. Phase 0 is limited to synthetic frames, preprocessing, logging, and a simple detection stub, so work can proceed before Gazebo is ready.

CV owns observation production only. Navigation owns mission logic, docking owns alignment and descent logic, and safety owns permission and override decisions. CV does not select actions or issue movement commands.

## Inputs and outputs

- Inputs: generated test frames or saved synthetic fixtures, timestamps, and camera identity.
- Outputs: timestamp, camera ID, image dimensions, placeholder label/bounding box in documented pixel coordinates, and validity.
- Label stub output as synthetic. Include explicit empty/invalid cases and never present an old observation as current.
- A stub bounding box is not a measured 3D position and must not be used as one.

## First tasks

1. Create a repeatable synthetic frame source.
2. Add simple preprocessing with documented input/output formats.
3. Produce deterministic detection-stub observations, including empty and invalid cases.
4. Log frames and observations with timestamps and camera identity.
5. Agree the observation format with consuming modules and demonstrate publication using fixtures.

Keep forward-camera and downward-camera observations distinguishable through camera IDs. Other modules decide how to use these observations.

## Acceptance evidence

The required demo generates or reads synthetic frames, preprocesses them, and publishes/logs timestamped stub observations. Verify output formats, reproducibility, and empty/invalid cases. Consumers can test their interfaces without a working detector.

## Stretch and future work

2D marker detection is a stretch goal, not a dependency for Phase 0 completion. It may publish marker IDs and image corners through the observation interface. See the [OpenCV ArUco tutorial](https://docs.opencv.org/4.13.0/d5/dae/tutorial_aruco_detection.html).

Python and OpenCV are sufficient for the required Phase 0 pipeline; model training is not required.


