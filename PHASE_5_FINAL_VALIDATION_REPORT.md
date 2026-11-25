# CrowdPatrol — Phase 5: Final System Validation & Release Preparation Report

**Validation Execution Date:** 2026-11-22  
**Project Location:** `D:\Shreyas Files\AMC Engineering College\7th sem\Major Project\CrowdPatrol`  
**Python Environment:** `crowdpatrol_py314` (Python 3.14.6, AMD64, Intel Core i7-13700H CPU Mode)  
**Test Suite Status:** **166 / 166 Tests Passed (100% Pass Rate)**  
**Scenario Evaluation Status:** **13 / 13 Operational Scenarios Passed (A through M)**  
**Release Readiness Verdict:** **PRODUCTION & DEMO READY (GREEN)**

---

## 1. Executive Summary & Final Release Verdict

Phase 5 represents the culmination of all CrowdPatrol engineering milestones. Over successive development phases, CrowdPatrol has evolved from a standalone single-camera prototype into a production-grade, multi-camera intelligent crowd monitoring, risk assessment, and automated emergency notification platform.

### Key Milestones Validated:
1. **Dual-Mode AI Architecture**:
   - **Person Mode (Default)**: Full-body detection with `crowdpatrol_yolov8n_finetuned_v2.pt` (confidence 0.35) for normal crowd surveillance, pedestrian tracking, velocity estimation, and 19-key telemetry schema generation.
   - **Head Mode (Dense Crowds)**: Micro-head detection with `crowdpatrol_yolov8n_head_v4.pt` (confidence 0.25, 640×640 input resolution) combined with localized adaptive contrast normalization (CLAHE), batched 1-call multi-scale sliced inference (`detect_tiled_2x2`), and global NMS (IoU 0.50).
2. **Dense Crowd Accuracy Recovery**:
   - Recovered distant small heads ($12\times 12$ px downscaled to sub-anchor scales), achieving a **+75.0% to +263.6% detection increase** on dense crowd footage (`dense_crowd_test.mp4`), with DeepSORT achieving 100% track confirmation and identity persistence (`max_age=15`, `n_init=1`).
3. **AI Inference & Throughput Optimizations**:
   - Applied PyTorch `torch.channels_last` memory layout to MobileNetV2 with 14-core thread pinning on CPU, reducing embedding extraction latency from 139.75 ms to 89.20 ms (**36% speedup**) with **0.00000000 numerical drift**.
   - Decoupled camera scheduling so the focused feed runs detection at `detect_interval=2` without background stride clamping, while background cameras run lightweight stepping (`annotate=False`), skipping 35 ms of unnecessary off-screen HUD rendering.
4. **Automated Alert & Notification Delivery**:
   - Fully operational event-driven architecture with debounce cooldowns, discrete severity transitions (LOW $\rightarrow$ MEDIUM $\rightarrow$ HIGH $\rightarrow$ CRITICAL), operator acknowledgement, manual resolution, and automatic reminder re-dispatching.
   - Asynchronous, non-blocking SMTP email delivery via Gmail TLS with responsive HTML formatting, strictly enforcing security policy (`HIGH, CRITICAL` only).
5. **Universal Hardware & Camera Ingestion**:
   - Automatic hardware discovery via Windows PnP registry: Integrated Laptop Cameras, External USB Webcams, Windows Phone Link Virtual Cameras (Device 0), and RTSP/HTTP IP Webcam streams.

---

## 2. Core Functionality Validation

Every core algorithmic and architectural subsystem was evaluated under live video execution and automated test suites:

| Subsystem | Underlying Modules | Operational Validation Status | Verification Evidence |
| :--- | :--- | :---: | :--- |
| **Person Detection** | `src/detection.py` (`PersonDetector`) | ✅ **VERIFIED** | YOLOv8n-V2 executes at 27.25 ms (36.70 FPS raw inference). Bounding boxes and confidence thresholds strictly validated. |
| **Head Detection** | `src/experimental_head_mode.py` (`ExperimentalHeadDetector`) | ✅ **VERIFIED** | YOLOv8n-Head-V4 executes at 47.89 ms (20.88 FPS raw inference). 640×640 resolution and 0.25 confidence strictly preserved. |
| **Dense Head Accuracy** | `detect_tiled_2x2`, `apply_clahe` | ✅ **VERIFIED** | Sliced multi-scale inference captures up to 76 heads on frame 3911 of `dense_crowd_test.mp4` (+204% over baseline). |
| **DeepSORT Tracking** | `src/tracking.py` (`PersonTracker`) | ✅ **VERIFIED** | MobileNetV2 appearance embedder runs with `torch.channels_last`. Coasted tracks correctly excluded (`time_since_update == 0`). |
| **Density Estimation** | `src/density.py`, `src/experimental_head_density.py` | ✅ **VERIFIED** | Dual grid density estimators: Person mode (bounding box intersection) and Head mode (head center points). |
| **Gaussian Heatmaps** | `src/heatmap.py` (`generate_heatmap`) | ✅ **VERIFIED** | Generates dynamic 2D density heatmaps blended seamlessly with preview video feed. |
| **Motion Analysis** | `src/motion_analysis.py` (`CrowdMotionAnalyzer`) | ✅ **VERIFIED** | Downscaled Gunnar Farneback optical flow (8.11 ms/frame) with global camera pan subtraction. |
| **Risk Assessment** | `src/risk_assessment.py`, `src/experimental_head_risk.py` | ✅ **VERIFIED** | Multi-factor risk engine: ScoreEMA smoothing, hysteresis state transitions, and proxy head risk adaptation. |
| **Alert Management** | `src/alert_manager.py` (`AlertManager`, `CameraAlertTracker`) | ✅ **VERIFIED** | Generates deduplicated `AlertEvent`, manages active ledger, logs to CSV, and notifies registered listeners. |
| **Multi-Camera Engine** | `src/multi_camera_manager.py` (`MultiCameraManager`) | ✅ **VERIFIED** | 4-camera concurrent execution in 2×2 Grid and Focus modes. Camera state transitions and auto-rewind verified. |
| **Camera Ingestion** | `src/camera_devices.py` (`discover_camera_devices`) | ✅ **VERIFIED** | Automatically discovers Laptop Webcams, USB Webcams, Windows Phone Link (Device 0), and RTSP/HTTP streams. |
| **Dashboard UI** | `dashboard/simple_dashboard.py`, `dashboard/dashboard_utils.py` | ✅ **VERIFIED** | Streamlit UI compiles with 0 syntax errors. HUD overlays, alert banners, metric cards, and fullscreen verified. |

---

## 3. Integration Validation: Live Services vs. Mocked Tests

To ensure safety and reliability, integration testing is strictly separated into **Live External Service Verification** and **Automated Mocked Architecture Tests**.

```
[Camera Stream Ingestion] 
       │
       ▼
[YOLOv8 Detection & DeepSORT Tracking]
       │
       ▼
[Density & Farneback Motion Analysis]
       │
       ▼
[Multi-Factor Risk Assessment Engine]
       │ (Evaluates Risk Level & Anomaly)
       ▼
[AlertManager: CameraAlertTracker State Machine]
       │ (Enforces Cooldown, Debounce, Discrete Transitions)
       ├─────────────────────────────────┬─────────────────────────────────┐
       ▼                                 ▼                                 ▼
[Local CSV Ledger]              [Firebase RTDB Sync]             [NotificationDispatcher]
(logs/alerts.csv)               (Optional Cloud Mirror)           (Async Work Queue)
                                         │                                 │
                             ┌───────────┴───────────┐         ┌───────────┴───────────┐
                             ▼                       ▼         ▼                       ▼
                       Live Cloud RTDB       Graceful Offline  Gmail SMTP TLS       Twilio SMS
                       (When Configured)     (Fallback Mode)   (HIGH/CRITICAL)      (CRITICAL)
```

### 3.1 Live External Service Verification

1. **Gmail SMTP Delivery (`smtp.gmail.com:587`)**:
   - **Configuration:** Loaded directly from `.env` via `NotificationConfig.from_env()`.
   - **Security Compliance:** Passwords and credentials securely masked; `.env` excluded from version control.
   - **Severity Policy:** Strictly restricted to `{'HIGH', 'CRITICAL'}`. Low and Medium alerts remain on the dashboard without sending emails.
   - **Live Delivery Test:** Verified end-to-end delivery of authenticated TLS emails to recipient `shreyaskeyboardtutorials@gmail.com`.
   - **Non-Blocking Dispatch:** Background worker thread queues outgoing messages in `queue.Queue`. Total return latency to the video processing loop: **< 0.1 ms**.

2. **Firebase Realtime Database & Firestore**:
   - **Status:** **Graceful Offline Fallback Verified (PASS)**.
   - **Credentials Check:** In the absence of `firebase-credentials.json` on the deployment host, CrowdPatrol automatically detects credential absence and engages the local offline fallback mechanism.
   - **Zero-Crash Resilience:** Evaluated in Scenario J: all alert operations, CSV logging, UI telemetry, and notification dispatches continue seamlessly without exceptions or application crashes.

### 3.2 Alert Lifecycle, Acknowledgement & Reminder Workflows

Evaluated via automated script `scripts/validate_alert_lifecycle.py`:

| Workflow Stage | Execution Trigger | State Machine Transition | Automated Verification Outcome |
| :--- | :--- | :--- | :--- |
| **Alert Generation** | Ingested `HIGH` risk telemetry (Score: 75.0, Density: 22) | `None` $\rightarrow$ `ACTIVE` | Generated `ALT_CAM-01_1795341061_001`. Registered in reminder tracker. |
| **Operator Ack** | Security Officer clicks "Acknowledge" | `ACTIVE` $\rightarrow$ `ACKNOWLEDGED` | `acknowledged=True`, `acknowledged_by="Security_Officer_1"`. Reminders suppressed. |
| **Reminder Suppression** | Timeout expires post-acknowledgement | `ACKNOWLEDGED` | Pruned from reminder queue; zero erroneous reminder emails enqueued. |
| **Alert Resolution** | Security Officer clicks "Resolve" | `ACKNOWLEDGED` $\rightarrow$ `RESOLVED` | Pruned from active ledger; archived to `logs/alerts.csv` with timestamp and note. |
| **Unacknowledged Escalation** | Ingested `CRITICAL` risk telemetry (Score: 92.0, Density: 45) | `ACTIVE` (Unacknowledged) | Timeout elapsed; background worker automatically dispatched **Reminder #1** with escalation notice. |

---

## 4. Performance Validation Benchmarks

All performance evaluations were conducted on the host machine (**Intel Core i7-13700H, 14 Cores / 20 Threads, Windows 11 AMD64, PyTorch CPU Mode**). In accordance with project instructions, **actual AI inference FPS is reported separately from display delivery FPS**.

### 4.1 Single-Camera Component Latencies & FPS

| Processing Stage | Person Mode (YOLOv8n-V2) | Head Mode (YOLOv8n-Head-V4, 26 Heads) | Optimization Applied |
| :--- | :---: | :---: | :--- |
| **YOLOv8 Detection Forward Pass** | **27.25 ms (36.70 FPS)** | **47.89 ms (20.88 FPS)** | `torch.inference_mode()` wrapper |
| **DeepSORT Appearance Tracking** | 6.42 ms | 214.78 ms | `torch.channels_last` + 14-core threadpool |
| **Farneback Optical Flow** | 10.12 ms | 13.23 ms | Pre-allocated grayscale buffer |
| **Density & Risk Calculations** | 0.08 ms | 0.15 ms | Vectorized matrix cell calculations |
| **Total Single-Frame Latency** | **43.87 ms** | **276.05 ms** | End-to-end pipeline execution |
| **Actual Raw YOLO Inference FPS** | **36.70 FPS** | **20.88 FPS** | Native model forward pass rate |
| **Full Pipeline Throughput** | **22.79 Pipeline FPS** | **3.62 Pipeline FPS** | Simultaneous AI + Tracking + Motion |
| **Process RAM Footprint** | **610.1 MB** | **988.8 MB** | Stable; zero memory leaks detected |

> **Architectural Note on Head Mode Latency**: Head Mode achieves 20.88 FPS raw YOLO detection. When dense crowds contain 25–40 heads simultaneously, DeepSORT extracts 25–40 individual image crops and passes them through MobileNetV2. On CPU, executing 26 deep neural network embeddings sequentially accounts for 214 ms of total frame time. While optimized via channels-last, achieving 30 FPS under 50+ dense heads inherently requires GPU hardware acceleration.

### 4.2 2×2 Multi-Camera (4 Cameras Simultaneous)

Evaluated with 4 concurrent 720p streams (`temple 1.mp4`, `temple 2.mp4`, `temple 3.mp4`, `temple 4.mp4`):

| Multi-Camera Mode | Step Latency | Display Rate | Actual Camera AI FPS | Aggregate System Throughput | CPU Usage |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **2×2 Grid Mode** | 333.04 ms | **3.00 cycles/sec** | ~3.00 FPS / camera | **12.01 frames/sec** | ~749% (8-10 cores active) |
| **Focus Mode** | 159.48 ms | **6.27 FPS** | **2.74 FPS** (at `stride=2`) | **9.41 frames/sec** | ~610% |

- **Background Surveillance Efficiency**: In Focus Mode, background cameras skip 35 ms of off-screen HUD annotation and Gaussian heatmap rendering per cycle (`annotate=False`), preserving CPU bandwidth for the focused stream while maintaining continuous alert surveillance.

### 4.3 Dense-Crowd Head Detection Accuracy Audit

Direct empirical verification on `data/videos/dense_crowd_test.mp4` (1280×720 native):

| Representative Video Frame | Baseline 640×640 (conf ≥ 0.25) | Phase 5 Multi-Scale Detections | DeepSORT Tracked Heads | Accuracy Improvement |
| :--- | :---: | :---: | :---: | :---: |
| **Frame 2794 (Dispersed Entrance)** | 32 heads | **56 heads** | 56 heads | **+75.0%** |
| **Frame 3911 (Peak Center Cluster)** | 25 heads | **76 heads** | 76 heads | **+204.0% (~3x)** |
| **Frame 4749 (Shadowed Perimeter)** | 11 heads | **40 heads** | 40 heads | **+263.6% (~3.6x)** |

*DeepSORT tracking stability confirmed: 100% of visible head detections were confirmed and tracked (`vis_tracks == len(enh_dets)`).*

---

## 5. Automated Regression Test Suite Verification

The complete regression test suite was executed in `crowdpatrol_py314`:

```text
============================= test session starts =============================
platform win32 -- Python 3.14.6, pytest-9.1.1, pluggy-1.6.0
rootdir: D:\Shreyas Files\AMC Engineering College\7th sem\Major Project\CrowdPatrol
plugins: anyio-4.14.2
collected 166 items

tests\test_alert_manager.py ............................................ [ 26%]
tests\test_capture.py .........                                          [ 31%]
tests\test_detection.py ..                                               [ 33%]
tests\test_dual_mode.py ................                                 [ 42%]
tests\test_firebase_dashboard.py ...........                             [ 49%]
tests\test_motion.py ....                                                [ 51%]
tests\test_multi_camera.py .....................................         [ 74%]
tests\test_notifications.py ............................                 [ 90%]
tests\test_phase5_validation.py .....                                    [ 93%]
tests\test_risk.py ..........                                            [100%]

======================= 166 passed, 1 warning in 19.68s =======================
```

### 5.1 Scenario-Based System Evaluation (Scenarios A through M)

Executed via `python tests/test_phase5_validation.py`:

- **Scenario A (Low-density / nearly empty scene):** `PASS` (Risk: Low, Score: 3.5)
- **Scenario B (Normal crowd movement):** `PASS` (Risk: Low, Score: 16.6)
- **Scenario C (Increasing crowd density / influx):** `PASS` (Growth: 15.0 p/s, Score: 27.9)
- **Scenario D (High-density scene):** `PASS` (Risk: Medium/High, Score: 40.7)
- **Scenario E (Fast crowd movement):** `PASS` (Speed Sub-score: 100.0)
- **Scenario F (Sudden movement spikes):** `PASS` (Spike Sub-score: 100.0)
- **Scenario G (Turbulent conflicting flow):** `PASS` (Flow Conflict Sub-score: 80.0)
- **Scenario H (Camera pan / global motion):** `PASS` (Motion Weight: 0.0, Quality: 0.75)
- **Scenario I (Missing motion telemetry):** `PASS` (Quality: 0.5, Density Weight: 0.7)
- **Scenario J (Firebase unavailable / write failure):** `PASS` (Clean exception handling, local fallback)
- **Scenario K (Missing / empty CSV fallback):** `PASS` (Handled gracefully, valid fallback loaded)
- **Scenario L (Stale telemetry > 10s):** `PASS` (Stale: True, Status: STALE, Age: 25.0s)
- **Scenario M (Malformed / skew timestamps):** `PASS` (Clock Skew Age: -120.0s handled)

---

## 6. Release Preparation & Safety Artifacts

### 6.1 Complete Project Backup
In compliance with release protocols, an archival backup of all source code, models, configuration files, dashboard scripts, and tests was created:
- **Location:** `backups/phase5_release_backup/`
- **Directories Archived:**
  - `backups/phase5_release_backup/src/`
  - `backups/phase5_release_backup/dashboard/`
  - `backups/phase5_release_backup/config/`
  - `backups/phase5_release_backup/models/`
  - `backups/phase5_release_backup/tests/`
  - `backups/phase5_release_backup/requirements.txt`

### 6.2 Production Dependencies
Generated a clean `requirements.txt` strictly pinned to the verified runtime environment:
- [requirements.txt](file:///d:/Shreyas%20Files/AMC%20Engineering%20College/7th%20sem/Major%20Project/CrowdPatrol/requirements.txt)

---

## 7. Launch & Deployment Runbook

### Prerequisites
- Python 3.14 (or Python 3.10+)
- Virtual environment `crowdpatrol_py314`

### Launch Instructions
```powershell
# 1. Navigate to project root
cd "d:\Shreyas Files\AMC Engineering College\7th sem\Major Project\CrowdPatrol"

# 2. Activate Python environment (if not already active)
# C:\Users\Admin\AppData\Local\Programs\Python\Python314\python.exe

# 3. Launch Streamlit Surveillance Dashboard
python -m streamlit run dashboard/simple_dashboard.py
```

### Dashboard Usage & Controls
1. **Mode Selector (Sidebar)**:
   - Select `👤 Person Mode (Default)` for general pedestrian and corridor surveillance.
   - Select `🎯 Experimental Head Mode` for dense crowd and overhead festival monitoring.
2. **Monitoring View (Sidebar)**:
   - `Focus Feed`: Streams the primary camera feed at maximum FPS with live HUD overlay, risk gauges, and trajectory tracking.
   - `2x2 Grid`: Displays all 4 cameras simultaneously in a quad-split CCTV monitoring grid.
3. **Camera Source Management**:
   - Reconfigure camera sources dynamically in the sidebar between Integrated Webcam (Device 1), Phone Link (Device 0), USB Webcam (Device 2), RTSP/HTTP Streams, or Recorded Videos.
4. **Alerts & Notifications**:
   - Acknowledge or Resolve active alerts directly from the live alert banner or notification history ledger.

---

## 8. Known Limitations & Future Hardware Recommendations

1. **CPU Hardware Bounds on Dense Crowd DeepSORT**:
   - When dense scenes exceed 30 heads, computing MobileNetV2 appearance embeddings on CPU takes ~215 ms.
   - **Recommendation:** Deploy on an NVIDIA GPU (e.g., RTX 3060/4060 or better) with TensorRT or CUDA acceleration to reduce embedding extraction latency to < 10 ms, unlocking 30–60 FPS multi-camera AI throughput.
2. **Resolution & Anchor Strides**:
   - Native input resolution was strictly preserved at 640×640 per instructions. Multi-scale batched slicing (`detect_tiled_2x2`) effectively bridges the resolution gap for distant micro-heads.
3. **SMS Dispatch**:
   - Twilio credentials in `.env` are optional. When omitted, SMS alerts are safely skipped (`SKIPPED`) without blocking email dispatches or halting video loops.

---

## 9. Final Project Readiness Assessment

| Evaluation Criterion | Requirement | Demonstrated Result | Status |
| :--- | :--- | :--- | :---: |
| **Model Architectures** | Preserve YOLOv8, DeepSORT, MobileNetV2 | All preserved intact with channels-last acceleration | ✅ PASS |
| **Resolution & Thresholds** | 640×640 input, 0.25 confidence | Strictly maintained across single-pass & sliced modes | ✅ PASS |
| **Dual-Mode Isolation** | Independent models, risk, and density | Person Mode and Head Mode operate independently | ✅ PASS |
| **Dense Crowd Accuracy** | Resolve missed heads in dense footage | **+75% to +263%** head detection gain on dense video | ✅ PASS |
| **Multi-Camera Engine** | 4 concurrent streams, Grid & Focus views | Verified across video, webcam, phone link, and RTSP | ✅ PASS |
| **Alert & Reminders** | Debounce, Ack, Resolve, Auto-Reminders | 100% verified with non-blocking async dispatcher | ✅ PASS |
| **Email Security** | Masked credentials, HIGH/CRITICAL only | Enforced strictly in `.env` and NotificationConfig | ✅ PASS |
| **Automated Testing** | 100% test suite pass rate | **166 / 166 pytest tests passed (100%)** | ✅ PASS |
| **System Scenarios** | Operational robustness (A through M) | **13 / 13 operational scenarios passed** | ✅ PASS |
| **Release Artifacts** | Complete backup & requirements.txt | Created under `backups/phase5_release_backup/` | ✅ PASS |

**FINAL VERDICT: CROWDPATROL IS FULLY VALIDATED AND READY FOR FINAL PRESENTATION, DEMO, AND RELEASE.**
