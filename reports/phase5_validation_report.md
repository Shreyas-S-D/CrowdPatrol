# CrowdPatrol — Phase 5 Final System Validation & Evaluation Report

**Project Title**: *CrowdPatrol: YOLOv8 and DeepSORT-based Real-Time Crowd Monitoring and Risk Assessment for Public Safety Surveillance*  
**Scope**: Experimental Academic Prototype  
**Date**: September 15, 2026  
**Status**: Validation Complete — Phase 5 Milestone Achieved  

---

## 1. Executive Summary & Objectives

Phase 5 completes the end-to-end system validation, evaluation, scenario testing, performance benchmarking, and documentation of the CrowdPatrol platform. The core pipeline integrates:

$$\text{Video/Camera Input} \longrightarrow \text{YOLOv8 Detection} \longrightarrow \text{DeepSORT Tracking} \longrightarrow \text{Density Estimation} \longrightarrow \text{Optical Flow Analysis} \longrightarrow \text{Enhanced Risk Engine} \longrightarrow \text{Firebase / CSV Sync} \longrightarrow \text{Streamlit Dashboard}$$

All Phase 1–3 algorithms (YOLOv8 detection, DeepSORT tracking, density estimation, optical flow motion analysis, and risk scoring logic) were strictly preserved without modification.

---

## 2. Test Environment & System Configuration

| Parameter | Configuration Detail |
| :--- | :--- |
| **Operating System** | Windows 11 (AMD64) |
| **Python Version** | 3.14.6 |
| **PyTorch Device** | CPU (CPU-only execution verified) |
| **YOLOv8 Model** | `yolov8n.pt` (Nano weights, 3.2M parameters) |
| **Detection Interval** | Every 3rd frame (skipping CNN feature extraction on intermediate frames via Kalman prediction) |
| **Optical Flow Resolution** | Downscaled to $320 \times 180$ grayscale |
| **Grid Dimensions** | $4 \times 4$ spatial grid (16 cells) |
| **Firebase Data Sync** | Realtime Database (`dashboard` and `alerts` nodes, 1-second write throttle) |

---

## 3. Task 3: Scenario-Based Testing Matrix (Scenarios A through M)

All 13 validation scenarios were executed and evaluated using automated test scripts (`tests/test_phase5_validation.py`):

| Scenario ID | Test Scenario Description | Input Condition | Expected Behavior | Actual Behavior | Result | Observations & Limitations |
| :---: | :--- | :--- | :--- | :--- | :---: | :--- |
| **A** | Low-density / nearly empty scene | Max Density = 2, Speed = 0.1 px/f | Low risk classification ($<40.0$) | Risk = `Low`, Score = `3.5` | **PASS** | Normal baseline behavior |
| **B** | Normal crowd movement | Max Density = 8, Speed = 0.6 px/f | Low risk classification ($<40.0$) | Risk = `Low`, Score = `16.6` | **PASS** | Steady pedestrian flow |
| **C** | Increasing crowd density | Influx rate = 15.0 persons/sec | Growth sub-score maxes out, risk increases | Growth Rate = `15.0 p/s`, Growth Sub-score = `100.0` | **PASS** | Influx rate correctly boosts risk |
| **D** | High-density scene | Max Density = 35 persons/cell | Medium or High risk classification ($\ge 40.0$) | Risk = `Medium`, Score = `40.7` | **PASS** | Density cap triggers elevated alert |
| **E** | Fast crowd movement | Avg Speed = 3.5 px/f ($> 3.0$ cap) | Speed sub-score caps at 100.0 | Speed Sub-score = `100.0` | **PASS** | Bounded velocity magnitude |
| **F** | Sudden movement / acceleration | 4 spike cells, max-avg diff = 3.5 px/f | Spike and local anomaly sub-scores = 100.0 | Spike Sub-score = `100.0`, Local Sub-score = `100.0` | **PASS** | Acceleration spikes captured |
| **G** | Different movement directions | Directional coherence = 0.2 | High flow conflict sub-score ($80.0$) | Flow Conflict Sub-score = `80.0` | **PASS** | Turbulent crowd flow detected |
| **H** | Camera pan or camera motion | `camera_motion_detected = True` | Motion factors excluded; weights set to 0.0 | Motion Weights = `0.0`, Data Quality = `0.75` | **PASS** | **Deterministic camera isolation** |
| **I** | Missing / invalid motion telemetry | `motion_summary = None` | Motion factors excluded; fallback to 70/30 density/growth | Density Weight = `0.70`, Data Quality = `0.50` | **PASS** | Graceful telemetry fallback |
| **J** | Firebase write failure | Network write exception thrown | Main pipeline continues executing locally | Exception caught cleanly, local CSV runs | **PASS** | No pipeline crash or log spam |
| **K** | Missing / empty / corrupted CSV | Missing, 0-byte, corrupt text CSV | Handles error without crashing; loads valid fallback | Empty handled cleanly; valid row loaded | **PASS** | Offline CSV fallback functional |
| **L** | Stale telemetry ($> 10\text{s}$ age) | Last timestamp 25s old | Telemetry marked stale; status = `STALE` | `is_stale = True`, Status = `STALE` | **PASS** | Stale heartbeat warning active |
| **M** | Malformed / future timestamps | Naive, Z, offset, or future ($+120\text{s}$) string | ISO parsed cleanly; clock skew flagged | Clock Skew Age = `-120.0s`, Naive/Z parsed | **PASS** | Robust ISO timestamp parsing |

---

## 4. Task 4: Performance Evaluation & Benchmark Results

Performance was empirically measured across isolated components and the full end-to-end pipeline:

### Component Overhead Benchmarks (Isolated CPU Execution)
- **Isolated Risk Engine Latency**: **98.08 microseconds ($\mu s$)** per frame (~0.098 ms; throughput: **10,196 assessments/second**).
- **Downscaled Optical Flow Latency ($320 \times 180$)**: **22.79 milliseconds (ms)** per frame.

### End-to-End Pipeline Performance (YOLOv8 + DeepSORT + Optical Flow + Enhanced Risk Engine)
- **Average Frame Rate**: **12.2 FPS**
- **Minimum Frame Rate**: **5.6 FPS**
- **Maximum Frame Rate**: **15.0 FPS**
- **Average Frame Processing Latency**: **81.79 ms** per frame.

*(Note: Frame rate measurements are specific to CPU execution on Windows 11 with detection interval = 3. GPU acceleration or higher detection intervals further increase throughput).*

---

## 5. Dashboard & Telemetry Verification

The Streamlit dashboard interface (`dashboard/simple_dashboard.py` & `dashboard/app.py`) was verified to display and process the full **19-key telemetry payload** (16 primary fields + 3 aliases):

1. `person_count`: Tracked persons metric card
2. `max_density` / `density`: Densest zone occupancy card
3. `risk_level` / `risk`: Risk status banner (`Low`, `Medium`, `High`)
4. `combined_score`: Smoothed risk meter
5. `raw_score`: Un-smoothed instant score comparison
6. `smoothed_score`: EMA smoothed score line chart
7. `growth_rate`: Density influx rate (`persons/sec`)
8. `data_quality_score`: Data quality meter ($C_{\text{data}} = 50\%, 75\%, 100\%$)
9. `avg_speed`: Average motion speed (`px/f`)
10. `max_speed`: Peak motion speed (`px/f`)
11. `dominant_direction`: Cardinal crowd heading direction (`N`, `NE`, `E`, etc.)
12. `camera_motion_detected`: Camera status banner (`📷 Static Camera` / `🎥 Camera Pan Active`)
13. `sudden_movement_count`: Active acceleration spike cells count
14. `anomaly_score` / `anomaly`: Track centroid anomaly
15. `fps`: Processing speed overlay
16. `last_frame_time`: Timestamp of last frame
17. `Connection Status`: `CONNECTED`, `STALE`, `OFFLINE_FALLBACK`, `UNAVAILABLE` badges

---

## 6. Demonstration Checklist

To perform a practical live demonstration of CrowdPatrol:

- [x] **Step 1**: Start monitoring core:
  ```bash
  set PYTHONIOENCODING=utf-8 && py -3 main.py --source 0 --detect-interval 3 --alerts
  ```
- [x] **Step 2**: Open Streamlit dashboard:
  ```bash
  py -3 -m streamlit run dashboard/simple_dashboard.py
  ```
- [x] **Step 3**: Demonstrate person detection boxes and DeepSORT confirm track IDs.
- [x] **Step 4**: Demonstrate optical flow motion quiver arrows and direction heading.
- [x] **Step 5**: Demonstrate risk level change when density or motion spikes.
- [x] **Step 6**: Demonstrate camera motion isolation (pan camera to verify motion factors disengage and $C_{\text{data}}$ drops to 75%).
- [x] **Step 7**: Demonstrate stale data handling (pause main script; dashboard displays `🟡 STALE DATA` within 10 seconds).
- [x] **Step 8**: Demonstrate offline CSV fallback (disconnect network/Firebase; dashboard reads `output/metrics_log.csv`).

---

## 7. Known Failures & Scope Limitations

1. **Uncalibrated Speed Units (`px/f`)**: Motion speeds represent relative pixel displacement per frame and do not express physical distance ($m/s$) without camera intrinsics calibration.
2. **Extreme Camera Shaking**: High-frequency handheld camera vibration degraded optical flow quality, correctly flagged via $C_{\text{data}} = 0.75$.
3. **Academic Prototype Scope**: CrowdPatrol is an experimental prototype. It **does not claim stampede prediction, guaranteed warning lead times, or universal production readiness**.

---

## 8. Final Conclusion & Future Work

Phase 5 validation confirms that CrowdPatrol achieves a robust, modular, and resilient crowd monitoring architecture. All 29 unit, integration, scenario-based, and benchmark tests passed with a 100% success rate while preserving Phase 1–3 algorithms.

### Recommended Future Work:
- Integration of GPU acceleration (TensorRT / CUDA) to increase pipeline speed beyond 30+ FPS.
- Monocular camera height/angle calibration for physical speed estimation ($m/s$).
- Edge-device deployment (NVIDIA Jetson / Raspberry Pi).
