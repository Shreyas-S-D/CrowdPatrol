# Phase 13 — Multi-Camera Crowd Monitoring Implementation Report

**CrowdPatrol: Autonomous Multi-Camera CCTV Command Center**  
**Date**: September 20, 2026  
**Branch**: `multi-camera-command-center`  
**Status**: COMPLETE (Verified & Tested)

---

## 1. Executive Summary & Objectives

In real-world security operations, surveillance agencies monitor multiple CCTV streams concurrently across high-risk urban venues, transit hubs, and stadium gates. Single-camera monitoring limits situational awareness to isolated physical locations.

Phase 13 and 13.3 extend CrowdPatrol from single-stream processing into an academic **Multi-Camera CCTV Command Center Prototype with Flexible Camera Source Inputs**. The system supports multi-channel stream ingestion from recorded video files, local USB/built-in webcams, and remote RTSP IP cameras, isolated spatial-temporal analytics, real-time command center grid rendering, overall system risk aggregation, and camera-namespaced telemetry export.

### Core Architectural Mandates:
1. **Flexible Source Ingestion**: Supports three distinct camera input types per camera channel:
   - `video`: Recorded MP4/AVI/MOV video file paths (automatically loops at EOF).
   - `webcam`: Local USB / Built-in camera device index integer e.g., `0`, `1`, `2` (does NOT rewind at EOF).
   - `rtsp`: IP camera RTSP stream URL e.g., `rtsp://...` (does NOT rewind at EOF).
2. **Shared YOLO Model Inference**: Instantiates a single YOLO object detection model shared across all active camera channels, preventing redundant memory allocation and optimizing CPU/RAM throughput.
3. **Strict State Isolation**: Maintains completely independent DeepSORT tracking states, 4x4 spatial density matrices, optical flow motion fields, and risk assessors per camera. Zero cross-camera track leakage occurs.
4. **Command Center 2×2 Grid UI**: Integrates a responsive 2×2 live video preview grid in `dashboard/simple_dashboard.py` with per-camera HUD overlays, JPEG stream compression, source type badges (`📁 RECORDED VIDEO`, `📷 WEBCAM`, `🌐 IP CAMERA`), and real-time status cards.
5. **Highest-Risk System Aggregation**: Evaluates system-wide risk status dynamically, where the overall command center alert status is driven by the camera stream reporting the highest risk level.
6. **Namespaced Telemetry**: Exports camera-attributed telemetry to both CSV logs (`camera_id`, `camera_name`, `source_type`) and Firebase Realtime Database (`cameras/<camera_id>/...`).

---

## 2. Multi-Camera Architecture & Flexible Source Design

```
                          COMMAND CENTER
                                 │
                   ┌─────────────┼─────────────┐
                   │             │             │
               CAM-01         CAM-02        CAM-03 ...
                   │             │             │
                Source        Source        Source
                  /             /             /
             Webcam / Video / RTSP   Webcam / Video / RTSP
                   │             │             │
                   ▼             ▼             ▼
             Detection ──> Tracking ──> Density ──> Risk
                   │             │             │
                   └─────────────┼─────────────┘
                                 ▼
                          Central Dashboard
                                 │
                          Firebase / CSV
```

### Shared YOLO Model vs Isolated Camera States
Running four separate YOLO model instances in Python would consume over 4 GB of RAM and severely bottleneck CPU throughput. `MultiCameraManager` initializes a single instance of `PersonDetector` (V2) or `ExperimentalHeadDetector` (V4) on startup. 

During execution, `step_camera(camera_id)` passes the current video frame of the designated camera to the shared detector, while passing raw detections to that camera's isolated `PersonTracker`, `DensityEstimator`, `CrowdMotionAnalyzer`, and `RiskAssessor`.

---

## 3. Camera Configuration Specification

The multi-camera topology is defined declaratively in `config/cameras.json`:

```json
{
  "cameras": [
    {
      "id": "CAM-01",
      "name": "Main Sidewalk / Entrance",
      "source_type": "video",
      "source": "data/videos/youtube_crowd_test.mp4",
      "enabled": true
    },
    {
      "id": "CAM-02",
      "name": "Overhead Dense Crowd Zone",
      "source_type": "video",
      "source": "data/videos/dense_crowd_test.mp4",
      "enabled": true
    },
    {
      "id": "CAM-03",
      "name": "Street Crossing Plaza",
      "source_type": "video",
      "source": "data/videos/real_crowd_video_1.mp4",
      "enabled": true
    },
    {
      "id": "CAM-04",
      "name": "Commercial Concourse",
      "source_type": "video",
      "source": "data/videos/real_crowd_video_2.mp4",
      "enabled": true
    }
  ]
}
```

---

## 4. Operational Risk Aggregation Logic

Security command centers operate on a "worst-case alert" protocol. `MultiCameraManager.get_overall_system_risk()` calculates the global risk state across all online feeds:

$$\text{Overall System Risk} = \max_{c \in \text{Online Cameras}} \left( \text{RiskLevel}(c) \right)$$

If any single camera enters `HIGH` risk, the top command banner transitions to a red alert detailing the critical stream ID, camera name, and risk score.

---

## 5. Telemetry Schema & Firebase Integration

Each camera channel generates namespaced telemetry payloads:

- **Local CSV Logging**: `camera_id`, `camera_name`, and `source_type` prepended to CSV metric rows.
- **Firebase RTDB**: Written under path `cameras/<camera_id>`:

```json
{
  "camera_id": "CAM-02",
  "camera_name": "Overhead Dense Crowd Zone",
  "source_type": "video",
  "source": "data/videos/dense_crowd_test.mp4",
  "status": "ONLINE",
  "mode": "PERSON",
  "person_count": 42,
  "max_density": 8,
  "risk_level": "HIGH",
  "risk_score": 82.4,
  "avg_speed": 1.4,
  "dominant_direction": "SOUTH-EAST",
  "fps": 18.2,
  "last_frame_time": "2026-09-20T15:20:00.000"
}
```

---

## 6. Verification & Test Suite Summary

Multi-camera functionality was thoroughly verified with automated unit tests in `tests/test_multi_camera.py`:

- `test_camera_config_file_exists`: Validates `cameras.json` structure.
- `test_multi_camera_manager_init`: Verifies instantiation of all 4 streams.
- `test_video_source_configuration`: Verifies video source opening and configuration.
- `test_webcam_source_configuration`: Verifies webcam index source configuration.
- `test_rtsp_source_configuration`: Verifies RTSP stream URL configuration.
- `test_invalid_video_path_handling`: Verifies clean error handling on missing video files.
- `test_invalid_webcam_index_handling`: Verifies clean error handling on invalid webcam indices.
- `test_failed_rtsp_connection_handling`: Verifies clean error handling on unreachable RTSP URLs.
- `test_mixed_source_types_across_cameras`: Verifies manager parsing across mixed input types.
- `test_independent_camera_capture_state`: Verifies isolated OpenCV VideoCapture objects.
- `test_video_eof_looping`: Verifies recorded video streams rewind automatically at EOF.
- `test_live_camera_does_not_rewind_at_eof`: Verifies webcam/RTSP live streams do NOT rewind at stream end.
- `test_one_failed_camera_does_not_stop_other_cameras`: Verifies camera connection failure isolation.
- `test_camera_state_isolation`: Verifies tracker and density state isolation.
- `test_overall_system_risk_aggregation`: Verifies highest risk level selection.
- `test_camera_telemetry_payload_schema`: Validates namespaced telemetry output.
- `test_detection_mode_switching`: Tests dynamic switching between Person Mode and Head Mode.
- `test_step_camera_with_mock_frame`: Verifies pipeline execution on synthetic video frames.

### Test Results:
`pytest -q` → **70 passed, 0 failed** (100% test suite pass rate).
