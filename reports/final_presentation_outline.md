# CrowdPatrol: Final Presentation Slide Deck Outline (15 Slides)

---

## Slide 1: Title Slide
- **Title**: CrowdPatrol: YOLOv8 and DeepSORT-based Real-Time Crowd Monitoring and Risk Assessment for Public Safety Surveillance
- **Subtitle**: Major Project Final Defense — Academic Year 2025–2026
- **Team**: Team 21 | Department of Computer Science & Engineering, AMC Engineering College, Bengaluru
- **Guide**: [TO BE ADDED - Guide Name]
- **Suggested Visual**: CrowdPatrol Logo / System Architecture Overview Graphic
- **Speaker Notes**: "Good morning respected members of the panel and project guide. Today, Team 21 presents CrowdPatrol, our major project on automated crowd density and motion-anomaly monitoring."

---

## Slide 2: Problem Statement
- **Key Points**:
  - High-density public gatherings pose severe overcrowding and motion management risks.
  - Manual surveillance video wall monitoring leads to operator fatigue and delayed response.
  - Existing automated software evaluates static counts without analyzing movement dynamics or camera pan noise.
- **Suggested Visual**: Diagram illustrating operator fatigue vs. automated vision system.
- **Speaker Notes**: "Manual monitoring of security video walls is prone to human error. Existing tools count people but ignore velocity, directional conflict, and density growth rate."

---

## Slide 3: Motivation
- **Key Points**:
  - Need for real-time automated situational awareness in public surveillance.
  - Potential of deep learning object detectors (YOLOv8) combined with multi-object tracking (DeepSORT).
  - Ability of optical flow to extract spatial crowd motion vectors and acceleration spikes.
- **Suggested Visual**: Optical flow motion arrows overlay sample graphic.
- **Speaker Notes**: "Our motivation is to combine object detection with dense optical flow to provide structured, continuous risk indicators for surveillance operators."

---

## Slide 4: Project Objectives
- **Key Points**:
  - **Obj 1**: Detect and track persons in real time with persistent Track IDs.
  - **Obj 2**: Calculate grid-based spatial crowd density across a $4 \times 4$ layout.
  - **Obj 3**: Compute downscaled optical flow speed (`px/f`), cardinal heading, and acceleration spikes.
  - **Obj 4**: Implement a Phase 3 Multi-Factor Enhanced Risk Engine with camera-motion factor isolation.
  - **Obj 5**: Synchronize a 19-key telemetry payload to Firebase RTDB with an offline CSV fallback and Streamlit UI.
- **Suggested Visual**: System Objective Flowchart.
- **Speaker Notes**: "Our objective is to deliver a complete end-to-end monitoring pipeline from raw video input to a resilient web dashboard."

---

## Slide 5: Existing System vs. Limitations
- **Key Points**:
  - **Existing Systems**: Manual CCTV monitoring or basic single-threshold person counters.
  - **Limitations**:
    - High cognitive load on human operators.
    - Single-frame threshold flickering around warning boundaries.
    - Lack of background camera pan compensation.
    - Rigid cloud reliance with no offline fallback.
- **Suggested Visual**: Comparison table highlighting CrowdPatrol advantages.
- **Speaker Notes**: "Current counters flicker when density hovers at boundary values and break when a security camera pans. CrowdPatrol addresses these gaps directly."

---

## Slide 6: Proposed System: CrowdPatrol
- **Key Points**:
  - Decoupled 3-tier architecture: Processing Core $\to$ Cloud/Local Telemetry Sync $\to$ Streamlit Dashboard.
  - Downscaled Optical Flow ($320 \times 180$) running efficiently on CPU (~22.8 ms/frame).
  - Multi-Factor Risk Assessment Engine evaluating 6 active factors.
  - Deterministic camera-motion factor isolation when camera panning is detected.
  - Resilient offline CSV fallback during network dropouts.
- **Suggested Visual**: Block diagram of CrowdPatrol core pipeline.
- **Speaker Notes**: "CrowdPatrol uses downscaled optical flow for CPU efficiency, isolates camera motion automatically, and falls back to local CSV logging if the internet drops."

---

## Slide 7: System Architecture
- **Key Points**:
  - Video Input $\to$ YOLOv8 Person Detector (`yolov8n.pt`) $\to$ DeepSORT Tracker (Kalman filter).
  - Tracks $\to$ Density Estimator ($4 \times 4$ grid) + Crowd Motion Analyzer (Farneback flow).
  - Metrics $\to$ Enhanced Risk Assessor (EMA $\alpha=0.25$, Hysteresis $40/35$ & $70/65$).
  - Telemetry Snapshot (19 keys) $\to$ Firebase RTDB / CSV Fallback $\to$ Streamlit Dashboard.
- **Suggested Visual**: Detailed System Architecture Diagram (Figure 4.1).
- **Speaker Notes**: "Here is our full data pipeline. Notice how telemetry is decoupled from the visualization frontend, ensuring high stability."

---

## Slide 8: Technologies Used
- **Key Points**:
  - **Computer Vision & AI**: PyTorch, Ultralytics YOLOv8, DeepSORT, OpenCV.
  - **Data & Math**: NumPy, Pandas, Gunnar Farneback Optical Flow.
  - **Backend & Sync**: Firebase Realtime Database, Firestore, Python `csv`.
  - **Frontend UI**: Streamlit, Plotly, HTML5/CSS3 custom components.
- **Suggested Visual**: Logos of Python, PyTorch, OpenCV, Firebase, and Streamlit.
- **Speaker Notes**: "We built CrowdPatrol entirely in Python, utilizing PyTorch for detection, OpenCV for vision operations, Firebase for cloud sync, and Streamlit for UI."

---

## Slide 9: Core Methodology
- **Key Points**:
  - **Skipped-Frame Tracking**: Detect every 3rd frame; advance Kalman filter prediction on intermediate frames for high FPS.
  - **Spatial Median Subtraction**: Compute background vector $(V_{bg\_x}, V_{bg\_y}) = \text{median}(V_x, V_y)$ to remove camera movement.
  - **Density Growth Rate**: Measure influx rate in persons/second ($\max(0, \Delta d / \Delta t)$).
- **Suggested Visual**: Diagram explaining spatial median camera subtraction.
- **Speaker Notes**: "To maintain high FPS on CPU, we perform YOLO detection every 3rd frame while advancing Kalman predictions. Spatial median filtering isolates crowd flow from camera movement."

---

## Slide 10: Multi-Factor Risk Engine & Dashboard
- **Key Points**:
  - **6 Risk Factors**: Density ($35\%$), Density Growth ($15\%$), Motion Speed ($15\%$), Flow Conflict ($15\%$), Accel Spikes ($10\%$), Local Anomaly ($10\%$).
  - **Camera Motion Isolation**: Sets motion factors to $0\%$ weight when camera panning is detected, re-normalizing onto Density ($70\%$) and Growth ($30\%$).
  - **Hysteresis State Machine**: Prevents label flickering near threshold boundaries ($40/35$ and $70/65$).
  - **19-Key Telemetry Payload**: Transmits 16 primary fields + 3 compatibility aliases (`density`, `risk`, `anomaly`).
- **Suggested Visual**: Hysteresis State Transition Diagram.
- **Speaker Notes**: "Our Phase 3 risk engine evaluates 6 factors. When a camera pans, motion weights drop to zero so panning never inflates risk scores."

---

## Slide 11: Implementation Screenshots & UI
- **Key Points**:
  - **Annotated Stream**: YOLO bounding boxes, DeepSORT track IDs, $4 \times 4$ density grid, motion quiver vectors.
  - **Streamlit UI**: Risk meter, Data Quality score badge ($C_{\text{data}}$ %), Trend line charts, Alert history table.
  - **Status Indicators**: `CONNECTED`, `STALE` ($>10$s age warning), `OFFLINE_FALLBACK`.
- **Suggested Visual**: Annotated live feed screenshot & Streamlit dashboard layout.
- **Speaker Notes**: "This screenshot displays our live monitoring stream with motion quiver arrows alongside the Streamlit real-time dashboard."

---

## Slide 12: Testing & Experimental Results
- **Key Points**:
  - **Test Suite Results**: 57 total tests passed across 6 test suites (`100% PASS`).
  - **Scenario Testing**: 13 operational scenarios passed (Scenarios A through M).
  - **Measured Performance**:
    - Risk Engine Latency: **98.08 µs/assessment** (10,196 ops/sec).
    - Downscaled Optical Flow: **22.79 ms/frame**.
    - Full Pipeline Speed: **12.2 FPS** average on CPU (Min: 5.6 FPS).
- **Suggested Visual**: Summary Table of Scenario-Based Testing Results.
- **Speaker Notes**: "We validated CrowdPatrol across 57 automated test suites and 13 operational scenarios. On CPU execution, our pipeline runs at ~12.2 FPS."

---

## Slide 13: System Limitations
- **Key Points**:
  - **Image-Space Velocities**: Speed metrics expressed in `px/f`, not physical distance ($m/s$).
  - **Handheld Camera Shaking**: High vibration reduces flow quality ($C_{\text{data}} = 0.75$).
  - **CPU Boundaries**: Processing high-resolution video streams on CPU limits maximum FPS.
  - **Academic Prototype Scope**: System does not claim stampede prediction or guaranteed warning lead times.
- **Suggested Visual**: Icon summary of project limitations.
- **Speaker Notes**: "We report limitations transparently: velocities are measured in pixels per frame, severe camera shaking lowers data quality, and the system is an academic prototype."

---

## Slide 14: Future Scope
- **Key Points**:
  - **GPU Acceleration**: Deploy CUDA / TensorRT optimization for $> 30\text{+ FPS}$ throughput.
  - **Camera Calibration**: Implement perspective homography matrices for real-world physical speed ($m/s$).
  - **Edge Deployment**: Package monitoring core for NVIDIA Jetson / Raspberry Pi edge cameras.
- **Suggested Visual**: Roadmap diagram for future production enhancement.
- **Speaker Notes**: "In the future, adding TensorRT GPU acceleration and camera calibration matrices will allow physical speed conversion in meters per second."

---

## Slide 15: Conclusion & Q&A
- **Key Points**:
  - CrowdPatrol successfully demonstrates automated crowd density and motion-anomaly monitoring.
  - Achieved robust multi-factor risk scoring, deterministic camera motion isolation, and resilient offline CSV fallback.
  - All 57 tests and 13 scenarios passed with 100% verification.
- **Closing Statement**: "Thank you for your time and attention. We are ready to take your questions."
- **Speaker Notes**: "That concludes our presentation. We welcome your questions."
