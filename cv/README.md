# Computer Vision — Phase 0

[Central proposal](../START_HERE.md)

## Purpose and scope

Provide camera processing and marker observations for simulated docking. Start with saved images/video so development can proceed before Gazebo is ready.

Required work: frame input, preprocessing, ArUco marker detection, marker-relative pose estimation, and logging. Generic bird detection is a possible stretch task pending the scope decision in the central proposal. Species training, threat interpretation, and deterrence selection are outside this team's required work.

## Inputs and outputs

- Inputs: saved or simulated camera frames, timestamps, camera calibration, known marker dimensions.
- Outputs: marker ID, image corners, optional relative pose, coordinate frame, timestamp, and validity.
- Publish an explicit missing/invalid observation when detection fails. Do not reuse an old pose as though it were current.
- Pose estimation requires camera intrinsics and marker dimensions; a bounding box alone is not a 3D position.

## First tasks

1. Define a frame-source interface for files and future simulated cameras.
2. Detect and annotate markers in a small repeatable image/video fixture set.
3. Agree the observation format with navigation and docking.
4. Add calibrated pose estimation and document camera-frame conventions.
5. Connect the pipeline to Gazebo frames.
6. Evaluate distance, viewing angle, lighting, occlusion, and marker loss.

Choose camera placement with docking in mind: the marker must remain visible during the planned approach and descent.

## Acceptance evidence

The first demo reads saved inputs and logs timestamped results, including no-marker cases. Integration then demonstrates observations from the simulated camera. Report detection rate and pose error where reference data is available; document the evaluated conditions.

OpenCV is the initial tool. PyTorch is optional, not required for marker detection. See the [OpenCV ArUco tutorial](https://docs.opencv.org/4.13.0/d5/dae/tutorial_aruco_detection.html).

Implementation files and run commands have not yet been created.
