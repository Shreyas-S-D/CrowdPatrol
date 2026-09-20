# Stage 10 — Dual-Mode CrowdPatrol Dashboard Implementation Report

## Executive Summary

Stage 10 successfully integrates an optional **"Head Mode — Experimental"** into the CrowdPatrol live Streamlit dashboard (`dashboard/simple_dashboard.py`) while preserving **"Person Mode (Default)"** as the primary, production-grade monitoring pipeline. 

This dual-mode architecture allows operators to evaluate the high-angle dense-crowd detection capability of the V4 Head Detector (`models/crowdpatrol_yolov8n_head_v4.pt`) without altering or destabilizing the baseline V2 Person Detector (`models/crowdpatrol_yolov8n_finetuned_v2.pt`) or production risk engine.

---

## Architecture & System Design

```
                     ┌──────────────────────────────────────────────┐
                     │ Streamlit Dashboard (simple_dashboard.py)    │
                     └──────────────────────┬───────────────────────┘
                                            │
                             ┌──────────────┴──────────────┐
                             │ UI Mode Selector (Sidebar)  │
                             └──────┬───────────────┬──────┘
                                    │               │
        ┌───────────────────────────┘               └──────────────────────────┐
        ▼                                                                      ▼
┌──────────────────────────────────────────┐               ┌──────────────────────────────────────────┐
│ 👤 Person Mode (Default)                 │               │ 🗣️ Head Mode — Experimental              │
├──────────────────────────────────────────┤               ├──────────────────────────────────────────┤
│ Model: V2 Person Detector                │               │ Model: V4 Head Detector                  │
│ Weights: crowdpatrol_yolov8n_finetuned_v2│               │ Weights: crowdpatrol_yolov8n_head_v4.pt │
│ Strategy: Full-Frame (640x640)           │               │ Strategy: Full-Frame (640) / 2x2 Tiled    │
│ Target: Person Footprint Boxes           │               │ Target: Head Center Bounding Boxes       │
│ Tracking: DeepSORT (ID:1)                │               │ Tracking: DeepSORT (head#1)              │
│ Density: 4x4 Person Box Grid             │               │ Density: 4x4 Head-Center Grid            │
│ Risk: Production RiskAssessor            │               │ Risk: ExperimentalHeadRiskAdapter        │
│ HUD: Green Boxes & Risk Banner           │               │ HUD: Cyan Boxes & "HEAD MODE" Banner     │
│ Telemetry: Standard 19-key Schema        │               │ Telemetry: Isolated Head Mode Payload    │
└──────────────────────────────────────────┘               └──────────────────────────────────────────┘
```

---

## Detailed Component Specifications

### 1. Person Mode (Default — Unchanged)
* **Model**: `models/crowdpatrol_yolov8n_finetuned_v2.pt` (fallback `yolov8n.pt`).
* **Detection Target**: Full-body / visible-person bounding boxes.
* **Density Engine**: `DensityEstimator(grid_size=(4, 4))` mapping person footprint bounding boxes.
* **Risk Engine**: `RiskAssessor()` evaluating density, motion speed, anomaly score, growth rate, and camera pan motion.
* **Visualization**: Green bounding boxes `(0, 255, 0)`, track ID badges `ID:x`, white grid lines, and standard production risk banner.
* **Telemetry**: Standard 19-key payload structure fully backward-compatible with Firebase RTDB and CSV logging.

### 2. Head Mode — Experimental
* **Model**: `models/crowdpatrol_yolov8n_head_v4.pt` via `ExperimentalHeadDetector`.
* **Inference Strategy**: Selectable via UI:
  1. `Full-Frame (640x640)` (Default — ~31 FPS detector)
  2. `2x2 Spatial Tiling` (~8.9 FPS detector for ultra-dense micro-head resolution)
* **Density Engine**: `HeadDensityEstimator(grid_size=(4, 4))` mapping head center coordinates `((x1+x2)/2, (y1+y2)/2)`.
* **Risk Engine**: `ExperimentalHeadRiskAdapter()` producing exponential head-density risk scores bounded [0, 100].
* **Visualization**: 
  - Cyan head bounding boxes `(255, 255, 0)` in BGR.
  - Track badges formatted as `head#<id>`.
  - Yellow grid lines `(0, 255, 255)` in BGR with per-cell head count badges `H:<cnt>`.
  - Prominent header banner: `"HEAD MODE -- EXPERIMENTAL | RISK: <LEVEL> | SCORE: <SCORE>"`.
* **Disclaimer Callout**: Top warning banner on Streamlit UI:
  `"⚠️ EXPERIMENTAL MODE — HEAD DETECTION ACTIVE. Using V4 Head Detector (crowdpatrol_yolov8n_head_v4.pt). Not for production safety monitoring."`
* **Telemetry Isolation**: Isolated metrics payload using `mode: HEAD_EXPERIMENTAL`, storing `head_count` and `max_head_density` to prevent polluting Person Mode telemetry databases.

---

## Unit Test & Automated Verification Results

A dedicated test suite `tests/test_dual_mode.py` was implemented and executed against the full pytest suite.

### Test Execution Summary
* **Total Executed Tests**: 47
* **Passed**: 47 (100% pass rate)
* **Failed**: 0
* **Execution Time**: 18.57 seconds

### Dual-Mode Test Coverage (`tests/test_dual_mode.py`)
1. `test_mode_selector_default`: Confirms default UI selection is `👤 Person Mode (Default)`.
2. `test_person_mode_loads_v2`: Confirms Person Mode targets V2 model weights.
3. `test_head_mode_loads_v4`: Confirms Head Mode targets V4 model weights.
4. `test_head_detections_isolated_from_person_density`: Confirms Head Mode uses `HeadDensityEstimator` instead of `DensityEstimator`.
5. `test_head_density_uses_center_points`: Confirms grid cell assignment uses head center coordinates `(cx, cy)`.
6. `test_head_mode_uses_experimental_risk_adapter`: Confirms Head Mode uses `ExperimentalHeadRiskAdapter`.
7. `test_head_mode_disclaimer_warning_text`: Confirms exact warning banner string formatting.
8. `test_tiled_mode_selection_support`: Confirms 2x2 Spatial Tiling inference option execution.
9. `test_person_mode_telemetry_schema_unchanged`: Confirms Person Mode telemetry retains 19 keys without modification.

---

## Performance Benchmark Comparison

| Metric | Person Mode (V2 Full-Frame) | Head Mode (V4 Full-Frame) | Head Mode (V4 2x2 Tiled) |
| :--- | :---: | :---: | :---: |
| **Model Weight** | `yolov8n_finetuned_v2.pt` | `yolov8n_head_v4.pt` | `yolov8n_head_v4.pt` |
| **Detector Speed (FPS)** | 29.2 FPS | 31.0 FPS | 8.89 FPS |
| **Total Pipeline Speed (FPS)** | 3.20 FPS | 3.31 FPS | 1.68 FPS |
| **Avg Detections (`dense_crowd_test.mp4`)** | 1.87 persons/frame | 13.52 heads/frame | 20.64 heads/frame |
| **Zero-Detection Frame Rate** | 36.00% | 0.00% | 0.33% |
| **Target Grid Mapping** | Body Footprint Box | Head Center `(cx, cy)` | Head Center `(cx, cy)` |
| **Production Risk Engine** | Production `RiskAssessor` | `ExperimentalHeadRiskAdapter` | `ExperimentalHeadRiskAdapter` |

---

## Verification & Safeguard Checklist

- [x] **Stable Branch Protected**: `stable-v2` (commit `3e86e1a`) remains 100% untouched.
- [x] **Current Working Branch**: `v3-dense-crowd`.
- [x] **No Unintended Model Overwrites**: `models/crowdpatrol_yolov8n_finetuned_v2.pt` preserved intact.
- [x] **Production Risk Code Untouched**: `src/risk_assessment.py` remains untouched.
- [x] **No Git Commits Executed**: Workspace changes remain uncommitted per instructions.
