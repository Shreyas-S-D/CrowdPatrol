# CROWDPATROL: YOLOv8 AND DEEPSORT-BASED REAL-TIME CROWD MONITORING AND RISK ASSESSMENT FOR PUBLIC SAFETY SURVEILLANCE

---

## PROJECT TITLE PAGE

**PROJECT TITLE**: CrowdPatrol: YOLOv8 and DeepSORT-based Real-Time Crowd Monitoring and Risk Assessment for Public Safety Surveillance  
**DEGREE**: Bachelor of Engineering (B.E.) in Computer Science and Engineering / AI & ML  
**INSTITUTION**: AMC Engineering College, Bengaluru  
**AFFILIATION**: Visvesvaraya Technological University (VTU), Belagavi  
**ACADEMIC YEAR**: 2025–2026  
**TEAM MEMBERS**: Team 21  
**PROJECT GUIDE**: [TO BE ADDED - Guide Name & Designation]  
**HEAD OF DEPARTMENT**: [TO BE ADDED - HOD Name]  

---

## CERTIFICATE

This is to certify that the Major Project report entitled **"CrowdPatrol: YOLOv8 and DeepSORT-based Real-Time Crowd Monitoring and Risk Assessment for Public Safety Surveillance"** is a bona fide work carried out by Team 21 in partial fulfillment for the award of the degree of Bachelor of Engineering in Computer Science and Engineering of Visvesvaraya Technological University, Belagavi, during the academic year 2025–2026.

**Signature of Guide**: \_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_  
**Signature of HOD**: \_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_  
**Signature of Principal**: \_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_  

**External Examiners**:
1. Name & Signature: \_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_
2. Name & Signature: \_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

---

## DECLARATION

We, the students of Team 21, Department of Computer Science and Engineering, AMC Engineering College, declare that the project work entitled **"CrowdPatrol: YOLOv8 and DeepSORT-based Real-Time Crowd Monitoring and Risk Assessment for Public Safety Surveillance"** has been executed independently under the guidance of [TO BE ADDED - Guide Name]. We have not submitted this report for the award of any other degree or diploma to any other university or institute.

**Date**: September 15, 2026  
**Place**: Bengaluru  

---

## ACKNOWLEDGEMENT

We express our deep sense of gratitude to our Management, Principal, and Head of Department for providing state-of-the-art laboratory infrastructure and encouragement. We extend our heartiest thanks to our project guide [TO BE ADDED - Guide Name] for constant guidance, technical feedback, and continuous support throughout the project lifecycle.

---

## ABSTRACT

Public safety surveillance in high-density gathering places (festivals, transit hubs, stadiums, public events) requires automated situational awareness to detect crowd congestion and sudden movement anomalies. Manual video wall monitoring by security operators suffers from cognitive fatigue and delayed response. 

**CrowdPatrol** is an experimental academic prototype designed for automated crowd density and motion-anomaly monitoring using computer vision and deep learning. The system integrates YOLOv8 person detection, DeepSORT multi-object tracking, $4 \times 4$ spatial grid density estimation, downscaled Dense Farneback Optical Flow motion analysis ($320 \times 180$), and a Phase 3 Multi-Factor Enhanced Risk Assessment Engine. 

The risk engine evaluates 6 distinct factors: Spatial Density ($35\%$), Density Growth Rate ($15\%$), Optical Flow Speed ($15\%$), Flow Turbulence/Conflict ($15\%$), Acceleration Spikes ($10\%$), and Localized Velocity Anomalies ($10\%$). To isolate global camera movement during camera panning, the system implements **deterministic camera-motion factor isolation**, setting optical flow factor weights to zero and re-normalizing onto density and growth. Temporal smoothing via Exponential Moving Average ($\alpha = 0.25$) and a Hysteresis State Machine ($40/35$ and $70/65$ thresholds) eliminates single-frame label flickering.

Telemetry is normalized into a **19-key payload** (16 primary fields + 3 backward-compatibility aliases) and synchronized over Firebase Realtime Database with a 1-second write throttle. An offline CSV fallback (`load_offline_csv_fallback`) ensures the Streamlit dashboard continues rendering live metrics during network outages. On a CPU-only test environment, the isolated risk engine executes in **98.08 µs/assessment** (10,196 ops/sec), and the full end-to-end pipeline operates at **~12.2 FPS** (Min: 5.6 FPS). Across 57 total test suites (including 13 operational scenarios), CrowdPatrol achieved a 100% verification pass rate.

*Keywords*: Computer Vision, YOLOv8, DeepSORT, Optical Flow, Crowd Density Estimation, Risk Assessment, Hysteresis, Firebase, Streamlit.

---

## TABLE OF CONTENTS

- Certificate
- Declaration
- Acknowledgement
- Abstract
- Table of Contents
- List of Figures
- List of Tables
- Abbreviations

1. **Chapter 1: Introduction**
   - 1.1 Background
   - 1.2 Problem Statement
   - 1.3 Motivation
   - 1.4 Objectives
   - 1.5 Scope & Disclaimers
   - 1.6 Key Technical Contributions
2. **Chapter 2: Literature Survey**
   - 2.1 Existing Crowd Monitoring Approaches
   - 2.2 Deep Learning Object Detection (YOLOv8)
   - 2.3 Multi-Object Tracking (DeepSORT & Kalman Filtering)
   - 2.4 Density Estimation Techniques
   - 2.5 Motion Analysis via Optical Flow (Farneback)
   - 2.6 Risk Assessment Strategies
   - 2.7 Identified Research Gaps
3. **Chapter 3: System Analysis**
   - 3.1 Existing Manual System Analysis
   - 3.2 Limitations of Existing Systems
   - 3.3 Proposed CrowdPatrol Architecture
   - 3.4 Functional Requirements
   - 3.5 Non-Functional Requirements
   - 3.6 Feasibility Analysis (Technical, Operational, Economic)
4. **Chapter 4: System Design**
   - 4.1 System Architecture Diagram
   - 4.2 Data Flow Diagram (DFD Level 0, 1, 2)
   - 4.3 Module Decomposition & Dependencies
   - 4.4 Telemetry Database Schema (19 Keys: 16 Primary + 3 Aliases)
   - 4.5 Hysteresis State Machine Design
   - 4.6 Dashboard & Fallback Architecture
5. **Chapter 5: Methodology**
   - 5.1 Video/Camera Stream Acquisition
   - 5.2 YOLOv8 Person Detection Pipeline
   - 5.3 DeepSORT Multi-Object Tracking & Kalman Prediction
   - 5.4 Spatial Grid Density Estimation ($4 \times 4$)
   - 5.5 Heatmap Generation
   - 5.6 Downscaled Optical Flow & Spatial Median Camera Subtraction
   - 5.7 Multi-Factor Enhanced Risk Scoring Formula
   - 5.8 Exponential Moving Average (EMA) & Hysteresis State Transitions
   - 5.9 Firebase Realtime Database Telemetry Synchronization
   - 5.10 Resilient Offline CSV Fallback Loading
6. **Chapter 6: Implementation**
   - 6.1 Hardware and Software Requirements
   - 6.2 Directory Structure & Module Responsibilities
   - 6.3 Core Processing Loop (`main.py`)
   - 6.4 Telemetry Helper Module (`dashboard/dashboard_utils.py`)
   - 6.5 Streamlit Client Implementation (`simple_dashboard.py` & `app.py`)
   - 6.6 Exception Suppression & Type Coercion Safety
7. **Chapter 7: Results and Discussion**
   - 7.1 Experimental Setup & Environment
   - 7.2 Unit & Integration Test Results (29 Test Suites)
   - 7.3 Scenario-Based Validation Results (13 Scenarios A–M)
   - 7.4 Performance Benchmarks (Latency & FPS)
   - 7.5 Camera Motion Factor Isolation Verification
   - 7.6 Dashboard & Firebase Sync Verification
8. **Chapter 8: Limitations and Future Scope**
   - 8.1 Image-Space Velocity Units (`px/f`)
   - 8.2 Extreme Camera Shaking & Visual Occlusions
   - 8.3 CPU Execution Boundaries
   - 8.4 Future GPU Acceleration (CUDA / TensorRT)
   - 8.5 Camera Calibration for Physical Velocity ($m/s$)
9. **Chapter 9: Conclusion**
- **References**
- **Appendices**
  - Appendix A: Execution Commands
  - Appendix B: Selected Source Code Snippets

---

## LIST OF FIGURES

- Figure 4.1: High-Level System Architecture of CrowdPatrol
- Figure 4.2: Data Flow Diagram (DFD Level 1) for Video Telemetry
- Figure 4.3: Hysteresis State Machine Transition Diagram
- Figure 5.1: Grid Cell Spatial Slicing ($4 \times 4$)
- Figure 5.2: Optical Flow Directional Vector Arrow Overlay
- Figure 7.1: Benchmark Processing Latency Breakdown

---

## LIST OF TABLES

- Table 4.1: Telemetry Payload Schema (16 Primary Fields + 3 Aliases)
- Table 5.1: Risk Factor Sub-Scores, Caps, and Default Weights
- Table 5.2: Hysteresis State Transition Logic
- Table 7.1: Scenario-Based Testing Results Matrix (Scenarios A through M)
- Table 7.2: Component Latency & Pipeline FPS Measurements

---

## ABBREVIATIONS

- **AI**: Artificial Intelligence
- **API**: Application Programming Interface
- **CNN**: Convolutional Neural Network
- **CSV**: Comma-Separated Values
- **DFD**: Data Flow Diagram
- **EMA**: Exponential Moving Average
- **FCM**: Firebase Cloud Messaging
- **FPS**: Frames Per Second
- **IoU**: Intersection over Union
- **JSON**: JavaScript Object Notation
- **NMS**: Non-Maximum Suppression
- **OLS**: Optical Flow Speed
- **Re-ID**: Re-Identification
- **RTDB**: Realtime Database
- **UI/UX**: User Interface / User Experience
- **VTU**: Visvesvaraya Technological University
- **YOLO**: You Only Look Once

---

# CHAPTER 1: INTRODUCTION

### 1.1 Background
Public safety at mass gatherings (religious events, music concerts, transit terminals, sports arenas) is an imperative concern for municipal authorities and surveillance teams. Overcrowding can lead to excessive physical pressure, flow turbulence, or localized motion anomalies. Automated visual monitoring systems provide real-time metrics to aid surveillance operators.

### 1.2 Problem Statement
Traditional CCTV monitoring relies on security officers watching multiple video streams simultaneously. Human attention degrades rapidly due to cognitive fatigue, leading to missed overcrowding indicators. Existing automated software often relies solely on static person counts, neglecting crowd movement velocity, spatial density rate of change, and flow turbulence.

### 1.3 Motivation
Combining modern deep-learning object detectors (YOLOv8) with multi-object tracking (DeepSORT) and optical flow motion estimation enables real-time extraction of both spatial density and kinematic motion dynamics.

### 1.4 Objectives
1. Implement real-time person detection and multi-person tracking.
2. Estimate localized spatial crowd density across a $4 \times 4$ grid.
3. Compute dense optical flow movement magnitude (`px/f`), cardinal heading, and acceleration spikes.
4. Implement a multi-factor risk assessment engine featuring density growth rate, camera motion factor isolation, EMA smoothing, and hysteresis thresholding.
5. Synchronize telemetry to Firebase Realtime Database with an offline CSV fallback and Streamlit UI.

### 1.5 Scope & Disclaimers
CrowdPatrol is an **experimental academic prototype** designed for automated crowd density and motion-anomaly monitoring. System outputs represent relative metric indications for tested benchmark scenarios. The system **does not claim stampede prediction, guaranteed warning lead times, or universal production readiness**.

### 1.6 Key Technical Contributions
- **Deterministic Camera-Motion Isolation**: When global background motion is detected (`camera_motion_detected = True`), motion-derived sub-scores are excluded from scoring, preventing camera panning from inflating risk labels.
- **Normalized 19-Key Telemetry Payload**: Schema incorporating 16 primary fields and 3 backward-compatibility aliases.
- **Resilient Offline CSV Fallback**: Streamlit dashboard automatically displays local CSV metrics during Firebase outages.

---

# CHAPTER 2: LITERATURE SURVEY

### 2.1 Existing Crowd Monitoring Approaches
Early crowd analysis relied on traditional hand-crafted features (HOG, SIFT) coupled with SVMs. These methods lacked robustness against scale variation and heavy inter-person occlusion.

### 2.2 Object Detection (YOLOv8)
Ultralytics YOLOv8 employs an anchor-free split head architecture, enabling fast single-pass bounding box regression and classification.

### 2.3 Multi-Object Tracking (DeepSORT)
DeepSORT extends SORT by incorporating a deep appearance descriptor alongside Kalman filter state prediction $(x, y, a, h, \dot{x}, \dot{y}, \dot{a}, \dot{h})$, preserving track identities across occlusions.

### 2.4 Density Estimation
Grid-based spatial binning divides frames into discrete spatial zones, counting centroids per cell to identify high-density clusters.

### 2.5 Optical Flow (Farneback)
Gunnar Farneback's dense optical flow approximates pixel neighborhood transformations using polynomial expansion, computing dense motion vectors $(V_x, V_y)$ between consecutive frames.

### 2.6 Risk Assessment Strategies
Traditional risk models used single static thresholds. CrowdPatrol introduces temporal EMA smoothing and hysteresis logic to prevent single-frame label flickering.

### 2.7 Identified Research Gaps
- Lack of camera motion isolation in optical flow metrics.
- Label instability near threshold boundaries in single-frame risk models.
- Rigid cloud dependencies without offline local fallback options.

---

# CHAPTER 3: SYSTEM ANALYSIS

### 3.1 Existing Manual System Analysis
Surveillance centers rely on operators visually scanning video feeds, resulting in delayed intervention during crowd congestion.

### 3.2 Limitations of Existing Systems
- Operator fatigue and cognitive overload.
- Absence of real-time movement speed and directional conflict metrics.
- Vulnerability to network disconnections.

### 3.3 Proposed CrowdPatrol Architecture
A decoupled 3-tier architecture: Processing Core (`main.py`), Cloud/Local Storage (`Firebase` / `MetricsLogger`), and Visualization Frontend (`Streamlit`).

### 3.4 Functional Requirements
- **FR-1**: Detect persons with confidence $\ge 0.3$.
- **FR-2**: Track persons across frames with persistent Track IDs.
- **FR-3**: Compute $4 \times 4$ grid density map and peak cell count.
- **FR-4**: Calculate optical flow vectors, downscaling to $320 \times 180$ for low CPU overhead.
- **FR-5**: Subtract background camera motion using spatial median filtering.
- **FR-6**: Calculate multi-factor risk score $S_{\text{raw}} \in [0, 100]$ and smooth via EMA ($\alpha = 0.25$).
- **FR-7**: Synchronize 19-key payload to Firebase RTDB and fallback to CSV when offline.

### 3.5 Non-Functional Requirements
- **NFR-1 (Performance)**: Maintain $\ge 10$ FPS processing speed on CPU.
- **NFR-2 (Reliability)**: Zero crashes during network outages or corrupted CSV logs.
- **NFR-3 (Usability)**: Clear visual status badges and disclaimers on dashboard.

### 3.6 Feasibility Analysis
- **Technical**: Utilizes open-source Python libraries (OpenCV, PyTorch, Streamlit).
- **Operational**: Runs on standard PC hardware with webcam or video files.
- **Economic**: Zero software licensing costs.

---

# CHAPTER 4: SYSTEM DESIGN

### 4.1 System Architecture
```
[Video / Camera Input] ──► [YOLOv8 Detection] ──► [DeepSORT Tracker]
                                                         │
[Streamlit Dashboard] ◄── [Firebase RTDB / CSV] ◄── [Risk Assessor + Optical Flow]
```

### 4.2 Data Flow Diagram (DFD Level 1)
Video frames enter `PersonDetector` $\to$ bounding boxes pass to `PersonTracker` $\to$ tracks pass to `DensityEstimator` & `CrowdMotionAnalyzer` $\to$ metrics pass to `RiskAssessor` $\to$ normalized payload stored in `FirebaseAlertManager` / `MetricsLogger`.

### 4.3 Telemetry Database Schema (19 Payload Keys)
Primary keys: `person_count`, `max_density`, `risk_level`, `combined_score`, `raw_score`, `smoothed_score`, `growth_rate`, `data_quality_score`, `avg_speed`, `max_speed`, `dominant_direction`, `camera_motion_detected`, `sudden_movement_count`, `anomaly_score`, `fps`, `last_frame_time`.  
Aliases: `density`, `risk`, `anomaly`.

### 4.4 Hysteresis State Machine Design
```
Low Risk  : < 35.0  (Up to Medium at >= 40.0; Direct to High at >= 70.0)
Medium    : 35.0 - 69.9 (Down to Low at < 35.0; Up to High at >= 70.0)
High Risk : >= 65.0 (Down to Medium at < 65.0; Direct to Low at < 35.0)
```

---

# CHAPTER 5: METHODOLOGY

### 5.1 YOLOv8 Detection
Executes single-pass person detection (`cls == 0`). NMS removes overlapping bounding boxes.

### 5.2 DeepSORT Tracking
State prediction via Kalman filter. CNN embedding cosine distance matches candidate detections to confirmed tracks.

### 5.3 Density Estimation
Centroid $(x_c, y_c) = \left(\frac{x_1+x_2}{2}, \frac{y_1+y_2}{2}\right)$ mapped to grid cell $(r, c) = \left(\lfloor \frac{y_c}{\text{cell\_h}} \rfloor, \lfloor \frac{x_c}{\text{cell\_w}} \rfloor\right)$.

### 5.4 Downscaled Optical Flow & Spatial Median Camera Subtraction
Frame converted to $320 \times 180$ grayscale. Farneback flow computed. Global camera displacement estimated via spatial median:

$$V_{bg\_x} = \text{median}(V_x), \quad V_{bg\_y} = \text{median}(V_y)$$

Corrected flow: $V_{x}' = V_x - V_{bg\_x}$, $V_{y}' = V_y - V_{bg\_y}$.

### 5.5 Multi-Factor Risk Scoring Formula
$$S_{\text{raw}} = \sum_{i \in \text{Active}} w_i' \cdot N_i(f_i)$$

Active factors re-normalized to sum to $1.00$. When camera panning is detected (`camera_motion_detected = True`), motion factors are set to $0.0$ weight and active weights become Density ($70\%$) and Density Growth ($30\%$).

---

# CHAPTER 6: IMPLEMENTATION

### 6.1 Requirements
- Python 3.10+, PyTorch, OpenCV, Streamlit, firebase-admin, NumPy, Pandas.

### 6.2 Primary Modules
- `main.py`: Core pipeline orchestration loop.
- `src/risk_assessment.py`: Enhanced risk engine, EMA, Hysteresis.
- `src/motion_analysis.py`: Optical flow analyzer.
- `dashboard/dashboard_utils.py`: Telemetry normalization & CSV fallback.

### 6.3 Command Execution
```bash
# Monitoring Core
py -3 main.py --source 0 --detect-interval 3 --alerts

# Dashboard UI
py -3 -m streamlit run dashboard/simple_dashboard.py
```

---

# CHAPTER 7: RESULTS AND DISCUSSION

### 7.1 Experimental Setup
Evaluated on Windows 11 AMD64 CPU environment using synthetic crowd sequences and benchmark scripts.

### 7.2 Scenario-Based Test Results (Scenarios A through M)
All 13 operational scenarios passed at 100% success rate:
- **Scenario A (Low Density)**: Risk = `Low`, Score = `3.5` `[PASS]`
- **Scenario C (Density Influx)**: Growth = `15.0 p/s`, Score increased `[PASS]`
- **Scenario H (Camera Pan)**: Motion factors isolated, $C_{\text{data}} = 0.75$ `[PASS]`
- **Scenario J (Firebase Outage)**: Local execution continued seamlessly `[PASS]`
- **Scenario K (CSV Fallback)**: Corrupt CSV handled cleanly, valid row loaded `[PASS]`

### 7.3 Latency & FPS Measurements
- **Isolated Risk Engine**: **98.08 µs/assessment** (10,196 ops/sec).
- **Downscaled Optical Flow**: **22.79 ms/frame**.
- **End-to-End Pipeline**: **12.2 FPS** average (Min: 5.6 FPS, Max: 15.0 FPS on CPU).

---

# CHAPTER 8: LIMITATIONS AND FUTURE SCOPE

### 8.1 Limitations
- Motion speeds reported in image pixel space (`px/f`).
- Extreme camera vibration lowers optical flow quality ($C_{\text{data}} = 0.75$).
- Experimental prototype scope: no stampede prediction or guaranteed warning times claimed.

### 8.2 Future Scope
- CUDA / TensorRT GPU acceleration ($> 30\text{+ FPS}$).
- Monocular camera intrinsics and perspective homography calibration ($m/s$).

---

# CHAPTER 9: CONCLUSION

CrowdPatrol successfully demonstrates an automated crowd density and motion-anomaly monitoring system. By combining YOLOv8, DeepSORT, downscaled optical flow, and a Phase 3 multi-factor risk engine with camera motion isolation, the prototype delivers robust situational metrics across tested scenarios.

---

# REFERENCES

1. J. Redmon et al., "You Only Look Once: Unified, Real-Time Object Detection," CVPR, 2016.
2. N. Wojke, A. Bewley, and D. Paulus, "Simple Online and Realtime Tracking with a Deep Association Metric," ICIP, 2017.
3. G. Farneback, "Two-Frame Motion Estimation Based on Polynomial Expansion," SCIA, 2003.

---

# APPENDICES

### Appendix A: Commands
```bash
# Run unit test suite
py -3 tests/test_phase5_validation.py
```
