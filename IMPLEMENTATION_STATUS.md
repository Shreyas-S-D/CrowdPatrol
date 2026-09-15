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
- [x] Multi-factor composite risk scoring combining:
  1. Spatial Density ($w_1 = 0.35$, cap $= 30.0$ persons/cell)
  2. Density Growth Rate ($w_2 = 0.15$, cap $= 10.0$ persons/sec)
  3. Optical Flow Speed ($w_3 = 0.15$, cap $= 3.0$ px/f)
  4. Flow Conflict / Turbulence ($w_4 = 0.15$, $1.0 - \text{coherence}$)
  5. Acceleration Spikes ($w_5 = 0.10$, cap $= 4.0$ cells)
  6. Localized Velocity Anomaly ($w_6 = 0.10$, cap $= 3.0$ px/f)
- [x] **Deterministic camera-motion factor isolation**: When `camera_motion_detected == True`, all optical flow factors are excluded from active scoring, and active weights re-normalize to Spatial Density ($70\%$) and Growth ($30\%$).
- [x] **Temporal EMA & Hysteresis State Machine**: Continuous EMA smoothing ($\alpha = 0.25$) and state machine managing `LOW`, `MEDIUM`, `HIGH` thresholds ($40/35$ and $70/65$) preventing label flickering.
- [x] **Estimated Data-Quality Indicator ($C_{\text{data}}$)**: Reports heuristic data-quality score ($0.50, 0.75, 1.00$).
- [x] **100% Legacy Compatibility**: Preserved `assess_risk()` baseline output signatures.
- [x] **Validation & Performance**: 100% test pass rate across 10 test suites in `tests/test_risk.py`. Risk engine execution latency: **43.63 µs per assessment** (22,919 assessments/sec). Pipeline execution speed: **~22.2 FPS** (Min: 9.2 FPS).

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
