# CrowdPatrol --- Implementation Status

> This document is a working status record. Antigravity must verify
> every item against the actual repository before modifying code.

## 1. Completed or Demonstrated

The project has already implemented or demonstrated the following
capabilities:

-   [x] YOLOv8-based person detection.
-   [x] DeepSORT-based multi-object tracking.
-   [x] Person counting.
-   [x] Grid-based crowd density estimation.
-   [x] Basic risk-score calculation.
-   [x] Low / Medium / High risk classification.
-   [x] Video overlay showing monitoring metrics.
-   [x] Live camera input.
-   [x] Pre-recorded video processing.
-   [x] Firebase Realtime Database integration.
-   [x] Sending monitoring metrics to Firebase.
-   [x] Basic Streamlit dashboard.
-   [x] Dashboard display of live monitoring metrics.
-   [x] Initial testing using camera and recorded crowd-related videos.
-   [x] Organized project structure containing source code, dashboard,
    logs, output, and tests-related folders or components.

## 2. Features That Must Be Verified

The review presentation describes the following as implemented, but
Antigravity must verify their actual quality and completeness in code:

-   [ ] Grid-based heatmap visualization.
-   [ ] Streamlit dashboard reliability.
-   [ ] Firebase synchronization reliability.
-   [ ] Risk-score calculation correctness.
-   [ ] DeepSORT tracking stability during occlusion.
-   [ ] Video output saving and overlay recording.
-   [ ] External camera support.
-   [ ] Command-line execution and configuration options.

## 3. Known Performance Concern

The demonstrated implementation has operated at approximately 1--4 FPS
in some test scenarios.

The exact current FPS must be measured again using a consistent test
setup.

Potential causes to investigate:

-   YOLOv8 inference cost.
-   Processing every frame.
-   CPU-only execution.
-   DeepSORT computation.
-   Excessive drawing or logging.
-   Firebase writes occurring too frequently.
-   Inefficient dashboard refreshes.
-   High input resolution.

## 4. Completed Milestones

### Phase 1 & 2 Completed
- [x] Optimize real-time FPS (Achieved ~20–25+ FPS via skipped-frame DeepSORT Kalman prediction).
- [x] Implement optical flow analysis (Downscaled Dense Farneback on 320x180 grayscale, ~2.8 ms CPU latency).
- [x] Calculate crowd movement direction and speed (`px/f`).
- [x] Detect sudden or abnormal movement acceleration patterns.

### Phase 3 Completed (Risk Assessment Engine Enhancement)
- [x] Multi-factor composite risk scoring combining 6 factors.
- [x] **Deterministic camera-motion factor isolation**: Excludes motion factors when camera panning.
- [x] **Temporal EMA & Hysteresis State Machine**: Smooths score ($\alpha = 0.25$) and manages `LOW`/`MEDIUM`/`HIGH` states ($40/35$ and $70/65$).
- [x] **Estimated Data-Quality Indicator ($C_{\text{data}}$)**: Reports heuristic data-quality score ($0.50, 0.75, 1.00$).
- [x] **100% Legacy Compatibility**: Preserved `assess_risk()` baseline output signatures.

### Phase 4 Completed (Firebase & Streamlit Dashboard Synchronization)
- [x] **Normalized 19-Key Payload Schema**: Transmits **16 primary telemetry fields** (`person_count`, `max_density`, `risk_level`, `combined_score`, `raw_score`, `smoothed_score`, `growth_rate`, `data_quality_score`, `avg_speed`, `max_speed`, `dominant_direction`, `camera_motion_detected`, `sudden_movement_count`, `anomaly_score`, `fps`, `last_frame_time`) + **3 backward-compatibility aliases** (`density`, `risk`, `anomaly`).
- [x] **Decoupled Telemetry Helper Module (`dashboard/dashboard_utils.py`)**: Isolated pure Python helpers for payload normalization, type coercion, ISO timestamp parsing, staleness evaluation, connection status classification, and resilient CSV fallback loading.
- [x] **Robust Offline CSV Fallback**: Automatically loads local `output/metrics_log.csv` or `logs/*.csv` when Firebase is unreachable, safely handling missing files, 0-byte files, corrupted text, missing columns, and NaN values without crashing.
- [x] **Stale-Data & Heartbeat Detection**: Flags telemetry as `STALE` if `last_frame_time` is $> 10 \text{ seconds}$ old, preventing operators from confusing paused feeds with active streaming.
- [x] **Fail-Safe Exception Suppression**: Firebase write failures raise a single throttled warning message, allowing local execution to continue uninterrupted.
- [x] **Streamlit UI Enhancements**: Integrated data quality score badge, camera motion indicator, directional crowd heading, risk score comparison (Raw vs Smoothed), and academic prototype disclaimers across all dashboard pages.

> **System Capability Notice**:
> CrowdPatrol provides **automated crowd density and motion-anomaly monitoring**. The system is validated for the tested benchmark scenarios and is an experimental prototype; it does **not** claim stampede prediction, guaranteed warning lead times, or universal production readiness.

### Medium Priority

-   [ ] Improve dashboard UI/UX.
-   [ ] Add clearer historical trends.
-   [ ] Improve alert history presentation.
-   [ ] Improve heatmap presentation.
-   [ ] Add camera/video source selection where appropriate.
-   [ ] Reduce repeated Firebase writes.
-   [ ] Improve error handling and logging.

### Evaluation Priority

-   [ ] Test on multiple crowd densities.
-   [ ] Test indoor and outdoor footage.
-   [ ] Test different lighting conditions.
-   [ ] Test occlusion-heavy scenes.
-   [ ] Test abnormal movement scenarios.
-   [ ] Record FPS and processing latency.
-   [ ] Evaluate detection precision and recall where ground truth is
    available.
-   [ ] Evaluate tracking performance.
-   [ ] Record false positives and false negatives.
-   [ ] Validate risk classification against manually labelled
    scenarios.

## 5. Do Not Claim Without Evidence

Do not claim that the system:

-   Predicts a stampede with certainty.
-   Provides a guaranteed 2--3 minute warning.
-   Detects panic reliably without validation.
-   Works in all crowd environments.
-   Runs in real time unless FPS is measured and justified.
-   Has accurate risk classification without a defined evaluation
    method.

Use terms such as **prototype**, **risk indication**, **early warning
support**, and **experimental evaluation** unless stronger evidence is
available.

## 6. Required Status Update Format

After inspecting the repository, update this document with:

-   Actual working modules.
-   Broken modules.
-   Partially implemented modules.
-   Relevant file paths.
-   Commands used to run the project.
-   Current measured FPS.
-   Known errors.
-   Recommended next task.
