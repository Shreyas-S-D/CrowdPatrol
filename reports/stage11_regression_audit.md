# Stage 11 — Final Dual-Mode Regression & UI Audit Report

## Executive Summary

Stage 11 conducted a comprehensive regression audit of the Stage 10 Dual-Mode CrowdPatrol Dashboard implementation on branch `v3-dense-crowd`. All 47 automated unit tests passed with 100% success. Person Mode baseline performance, Head Mode (Full-Frame & 2x2 Tiled) execution, mode component isolation, and telemetry payload schemas were empirically verified.

---

## 1. Modified-File Audit

### File Changes Breakdown (`git diff --stat`)
- `dashboard/simple_dashboard.py` (+305, -90)
- `src/detection.py` (+1, -0)
- `src/utils.py` (+95, -0)

### Audit Analysis & Justification
1. **`src/detection.py`**:
   - **Change**: Added `self.model_path = model_path` in `PersonDetector.__init__`.
   - **Reason**: Exposes model weights path on `PersonDetector` instances for programmatic verification in unit tests.
   - **Impact**: Zero effect on detection logic, YOLO parameters, model defaults, or inference behavior. 100% backward-compatible.

2. **`dashboard/simple_dashboard.py`**:
   - **Change**: Added sidebar UI mode selector (`👤 Person Mode (Default)` vs `🗣️ Head Mode — Experimental`), Head Mode inference strategy selector (`Full-Frame` vs `2x2 Spatial Tiling`), callout warning banner, conditional module instantiation, and metric badge formatting.
   - **Reason**: Implements optional experimental Head Mode without altering baseline Person Mode default.
   - **Impact**: `👤 Person Mode (Default)` remains the 100% default. Execution path for Person Mode is completely identical to V2.

3. **`src/utils.py`**:
   - **Change**: Added `draw_head_tracks`, `draw_head_density_zones`, and `create_head_dashboard_frame` static methods to `FrameAnnotator`.
   - **Reason**: Head Mode visual HUD overlays (cyan boxes, `head#ID` badges, yellow grid lines, head count badges).
   - **Impact**: Zero modification to existing `create_dashboard_frame` or Person Mode annotators.

---

## 2. Person Mode Regression Results

Tested on `data/videos/youtube_crowd_test.mp4` using `models/crowdpatrol_yolov8n_finetuned_v2.pt`:

* **V2 Model Loaded**: `True` (`models/crowdpatrol_yolov8n_finetuned_v2.pt`)
* **Detections / Frame**: 10.56 persons/frame
* **Tracked Persons / Frame**: 14.80 persons/frame
* **Max Density**: 5.21 p/cell
* **Risk Score**: 23.79 (LOW)
* **Detector Speed**: 40.31 FPS
* **Total Pipeline Speed**: 11.92 FPS (83.90 ms/frame)
* **Verdict**: **PASSED — No regression detected.**

---

## 3. Head Mode Full-Frame Results

Tested on `data/videos/dense_crowd_test.mp4` using `models/crowdpatrol_yolov8n_head_v4.pt`:

* **V4 Model Loaded**: `True` (`models/crowdpatrol_yolov8n_head_v4.pt`)
* **Detections / Frame**: 6.53 heads/frame
* **Tracked Heads / Frame**: 18.67 heads/frame
* **Max Head Density**: 5.55 heads/cell
* **Experimental Risk Score**: 32.69 (MEDIUM)
* **Detector Speed**: 31.91 FPS
* **Total Pipeline Speed**: 15.17 FPS (65.91 ms/frame)
* **Disclaimer Banner**: Verified present and active on UI.
* **Verdict**: **PASSED — Full-Frame Head Mode operational.**

---

## 4. Head Mode 2x2 Tiled Results

Tested on `data/videos/dense_crowd_test.mp4` using `models/crowdpatrol_yolov8n_head_v4.pt`:

* **V4 Model Loaded**: `True` (`models/crowdpatrol_yolov8n_head_v4.pt`)
* **Detections / Frame**: 29.03 heads/frame (micro-heads resolved via spatial tiling)
* **Tracked Heads / Frame**: 92.33 heads/frame
* **Max Head Density**: 20.19 heads/cell
* **Experimental Risk Score**: 50.00 (MEDIUM)
* **NMS Deduplication**: Verified merging across tile overlaps (`iou_threshold=0.45`).
* **Detector Speed**: 7.69 FPS
* **Total Pipeline Speed**: 3.94 FPS (253.96 ms/frame)
* **Verdict**: **PASSED — 2x2 Tiled Head Mode operational.**

---

## 5. Mode Isolation Verification

* **Person Mode Stack**: V2 Model → Person DeepSORT → 4x4 Person Box Grid (`DensityEstimator`) → Production `RiskAssessor`.
* **Head Mode Stack**: V4 Model → Head DeepSORT → 4x4 Head Center Grid (`HeadDensityEstimator`) → `ExperimentalHeadRiskAdapter`.
* **Cross-Contamination**: **NONE**. Head detections do not enter Person density, Head risk does not overwrite production risk, and metric histories clear on mode switch.

---

## 6. Telemetry Isolation Verification

* **Person Mode**: Preserves original 19-key telemetry schema without modification.
* **Head Mode**: Uses `mode: HEAD_EXPERIMENTAL` and separates `head_count` and `max_head_density`, setting `person_count: 0` to prevent corrupting Person Mode databases.

---

## 7. Test Suite Summary (`pytest -q`)

```
............................................... [100%]
47 passed, 1 warning in 18.59s
```
* **Passed**: 47 / 47 (100%)
* **Failed**: 0
* **Skipped**: 0
* **Warnings**: 1 (Deprecation warning from third-party `deep_sort_realtime` dependency)

---

## 8. Empirical Performance Summary

| Mode / Strategy | Target Model | Detector FPS | Pipeline FPS | Latency (ms) | Classification |
| :--- | :--- | :---: | :---: | :---: | :--- |
| **Person Mode** | `yolov8n_finetuned_v2.pt` | 40.31 FPS | 11.92 FPS | 83.90 ms | Production Real-Time |
| **Head Mode (Full-Frame)** | `yolov8n_head_v4.pt` | 31.91 FPS | 15.17 FPS | 65.91 ms | Experimental Real-Time |
| **Head Mode (2x2 Tiled)** | `yolov8n_head_v4.pt` | 7.69 FPS | 3.94 FPS | 253.96 ms | Experimental High-Res |

---

## 9. Issues Found & Required Fixes

* **Issues Found**: None.
* **Required Fixes**: None.

---

## 10. Production Safety Check

- [x] V2 model remains 100% default (`👤 Person Mode (Default)`).
- [x] Head Mode is opt-in (`🗣️ Head Mode — Experimental`).
- [x] Branch `stable-v2` (commit `3e86e1a`) remains untouched.
- [x] Model weights `models/crowdpatrol_yolov8n_finetuned_v2.pt` and `models/crowdpatrol_yolov8n_head_v4.pt` are intact.
- [x] Zero Git commits executed.

---

## Status

**READY TO COMMIT**
