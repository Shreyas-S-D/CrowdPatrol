# CrowdPatrol Multi-Camera Command Center Architecture

**Technical Architectural Specification**  
**Project**: CrowdPatrol Autonomous Crowd Monitoring  
**Phase**: 13 & 13.3 — Multi-Camera CCTV Command Center  
**Date**: September 20, 2026  

---

## 1. Tactical Overview

CrowdPatrol Multi-Camera Command Center scales autonomous crowd monitoring from single-channel video analysis to a multi-stream surveillance command center. The system ingests concurrent video streams from multiple CCTV channels (recorded video files, USB/built-in webcams, and remote RTSP IP camera streams), executes AI object detection and spatial-temporal tracking, and aggregates risk assessments across all streams into a unified control dashboard.

---

## 2. Component Class Diagram & Data Flow

```mermaid
classDiagram
    class MultiCameraManager {
        +Path config_path
        +String detection_mode
        +String device
        +int detect_interval
        +Dict cameras
        +Detector shared_detector
        +load_camera_config()
        +set_detection_mode(new_mode)
        +start_all_cameras()
        +stop_all_cameras()
        +step_camera(camera_id)
        +step_all()
        +get_overall_system_risk()
        +get_camera_telemetry_payload(camera_id)
    }

    class CameraState {
        +String id
        +String name
        +Variant source
        +String source_type
        +bool enabled
        +VideoCapture cap
        +String status
        +String error_message
        +PersonTracker tracker
        +DensityEstimator density_estimator
        +CrowdMotionAnalyzer motion_analyzer
        +RiskAssessor risk_assessor
        +int frame_count
        +float risk_score
        +String risk_level
        +open_source()
        +close_source()
        +reset_pipeline()
    }

    class SharedYOLODetector {
        +detect(frame) Detections
    }

    MultiCameraManager "1" *-- "many" CameraState : manages
    MultiCameraManager "1" o-- "1" SharedYOLODetector : uses for inference
```

---

## 3. High-Level System Architecture

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

---

## 4. Frame Processing Sequence Diagram

The following sequence illustrates a single processing tick across four camera channels:

```mermaid
sequenceDiagram
    autonumber
    participant UI as Command Center UI
    participant MCM as MultiCameraManager
    participant YOLO as Shared YOLO Detector
    participant C1 as CameraState (CAM-01)
    participant C2 as CameraState (CAM-02)

    UI->>MCM: step_all()
    
    rect rgb(30, 40, 60)
        note over MCM,C1: Step Channel CAM-01
        MCM->>C1: step_camera("CAM-01")
        C1->>C1: Read Frame
        alt Frame interval == detect_interval
            C1->>YOLO: detect(frame)
            YOLO-->>C1: Raw Detections
            C1->>C1: tracker.update(detections)
        else Non-detection frame
            C1->>C1: tracker.predict()
        end
        C1->>C1: Calculate Density & Motion
        C1->>C1: Assess Risk & Annotate HUD
        C1-->>MCM: Annotated Frame
    end

    rect rgb(40, 30, 60)
        note over MCM,C2: Step Channel CAM-02
        MCM->>C2: step_camera("CAM-02")
        C2->>C2: Read Frame
        alt Frame interval == detect_interval
            C2->>YOLO: detect(frame)
            YOLO-->>C2: Raw Detections
            C2->>C2: tracker.update(detections)
        else Non-detection frame
            C2->>C2: tracker.predict()
        end
        C2->>C2: Calculate Density & Motion
        C2->>C2: Assess Risk & Annotate HUD
        C2-->>MCM: Annotated Frame
    end

    MCM->>MCM: get_overall_system_risk()
    MCM-->>UI: Frames Dict & System Risk Status
    UI->>UI: Render 2x2 Grid & Update System Risk Banner
```

---

## 5. State Isolation & Security

To prevent cross-camera state contamination:

1. **Tracker Isolation**: Every `CameraState` owns its own `PersonTracker` instance with its own Kalman filter matrices and DeepSORT track ID counter. Track IDs generated in `CAM-01` are completely isolated from `CAM-02`.
2. **Density Grid Isolation**: Each camera calculates an independent 4x4 spatial density grid normalized to its own frame resolution.
3. **Motion Vector Isolation**: Optical flow grid matrices (`grid_matrix`) are computed on consecutive frames of that specific stream only.
4. **Telemetry Namespacing**: Telemetry data exported to Firebase and CSV includes explicit `camera_id` tags (`CAM-01` to `CAM-04`), enabling isolated analytics in downstream security platforms.
5. **Credential Safety**: No RTSP passwords, camera credentials, or API keys are stored in source control or JSON configuration files.

---

## 6. Scaling Strategy for Production RTSP Deployments

While the academic prototype defaults to local test MP4 video files, the architecture is designed for direct RTSP surveillance stream deployment:

- **RTSP Connection Handling**: `VideoProcessor.get_video_source()` natively supports RTSP URLs (e.g., `rtsp://admin:pass@192.168.1.100:554/stream1`).
- **Fail-Safe Connection Isolation**: If an RTSP or webcam stream drops, `CameraState` transition to `CONNECTION FAILED` or `OFFLINE` status without crashing remaining operational camera feeds.
- **Hardware Acceleration**: For multi-camera setups exceeding 8 channels, setting `device="cuda"` leverages GPU batching for `SharedYOLODetector.detect()`.
