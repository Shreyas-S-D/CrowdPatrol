# Stage 11.9 — Head Overlay Ghost Tracks Fix Report

**Date**: 2026-09-20  
**Target Video**: `data/videos/dense_crowd_test.mp4` (300 frames evaluated)  
**Branch**: `v3-dense-crowd`  
**Purpose**: Eliminate ghost head boxes from the Head Mode video overlay by filtering the rendered tracks to currently matched/visible heads (`time_since_update == 0`).

---

## Executive Summary

Stage 11.9 fixes the misleading Head Mode visual clutter identified in Stage 11.8.5. 

Previously, `FrameAnnotator.draw_head_tracks()` rendered all active DeepSORT tracks (averaging ~60 drawn boxes/frame), which included an average of 46.34 coasted/ghost track predictions per frame.

By updating the Head Mode rendering pipeline to filter for visible tracks (`time_since_update == 0`), **the video overlay now renders ONLY currently matched visible heads (averaging ~13.66 boxes/frame in Full-Frame mode and ~20.75 boxes/frame in 2×2 Tiled mode)**. Ghost boxes have been 100% eliminated from the production/demo overlay, while internal DeepSORT tracking memory remains fully intact.

---

## 1. Root Cause & Problem Analysis

In Stage 11.8.5, an audit revealed that:
1. DeepSORT tracks were retained internally for up to `max_age=30` frames.
2. `PersonTracker.update()` returned `active_tracks` containing both currently updated tracks (`time_since_update == 0`) and coasted tracks (`time_since_update > 0`).
3. The Head Mode HUD overlay passed `current_tracks` (all active tracks) directly into `FrameAnnotator.create_head_dashboard_frame()`.
4. As a result, 137 cyan head boxes were drawn over the video frame in the manual test, even though only 14 heads were visually detected in that frame (`Visible Heads: 14`).

---

## 2. Before / After Semantics & Exact Filtering Condition

### Exact Filtering Condition:
```python
if track.time_since_update == 0:
    visible_tracks.append(trk_data)
```

### Before vs. After Semantics:

| Feature / Component | Before Stage 11.9 | After Stage 11.9 |
| :--- | :--- | :--- |
| **Overlay Rendered Collection** | All active tracks (`len ≈ 60.0/frame`) | Visible tracks only (`time_since_update == 0`, `len ≈ 13.66/frame`) |
| **Ghost / Coasted Boxes** | Rendered as solid cyan boxes | **100% Excluded from overlay** |
| **Head Density Map Source** | Calculated from all active tracks | Calculated from visible heads (`visible_tracks`) |
| **Thermal Heatmap Layer** | Generated from all active tracks | Generated from visible heads (`visible_tracks`) |
| **Sidebar Metrics** | `Visible Heads` vs `Active Head Tracks` | `Visible Heads` vs `Active Head Tracks` (Unchanged) |
| **DeepSORT Internal Memory** | Retained tracks for `max_age=30` | Retained tracks for `max_age=30` (**Unchanged**) |
| **Person Mode** | Production V2 person pipeline | **100% Untouched & Unchanged** |

---

## 3. Preservation of Tracking & Detector Isolation

- **DeepSORT Tracker Integrity**: No tracker parameters were modified (`max_age=30`, `n_init=1`, feature matching parameters remain identical). `PersonTracker.update()` and `PersonTracker.predict()` continue to maintain full internal tracking state and return `active_tracks` for tracking continuity.
- **Detector Pipeline Isolation**: V4 model weights (`models/crowdpatrol_yolov8n_head_v4.pt`), inference parameters, confidence thresholds (`conf=0.35`), and NMS thresholds remain completely unchanged.
- **Person Mode Baseline Isolation**: Person Mode (`models/crowdpatrol_yolov8n_finetuned_v2.pt`) continues to function independently with zero modifications to its detection, tracking, density, risk, or annotation code.

---

## 4. Visual Validation Results

Validated on 300 frames of `data/videos/dense_crowd_test.mp4`:

### Full-Frame Mode (640x640):
- **Visible Heads / Frame**: `mean = 13.66` (min = 1, max = 44)
- **Drawn Cyan Boxes / Frame**: `mean = 13.66` (min = 1, max = 44)
- **Active Head Tracks / Frame**: `mean = 60.00` (min = 2, max = 146)
- **Max Head Density / Frame**: `mean = 3.37` heads/cell
- **Head Risk Score**: `mean = 19.92` (dynamic range: 4.60 to 49.76)
- **Equality Check (`drawn_cyan_boxes == visible_tracks`)**: **`True` (100% of frames)**

### 2×2 Spatial Tiled Mode:
- **Visible Heads / Frame**: `mean = 20.75` (min = 0, max = 50)
- **Drawn Cyan Boxes / Frame**: `mean = 20.75` (min = 0, max = 50)
- **Active Head Tracks / Frame**: `mean = 119.48` (min = 39, max = 167)
- **Max Head Density / Frame**: `mean = 5.58` heads/cell
- **Head Risk Score**: `mean = 31.28` (dynamic range: 2.30 to 61.53)
- **Equality Check (`drawn_cyan_boxes == visible_tracks`)**: **`True` (100% of frames)**

### Sample Visual Diagnostic Output:
Sample annotated frames saved under:
- `training/visualizations/v4_forensic_audit/stage11_9_validation/full_frame/`
- `training/visualizations/v4_forensic_audit/stage11_9_validation/tiled_2x2/`

---

## 5. Automated Test Suite Verification

- **Command**: `pytest -q`
- **Result**: **51 passed**, 0 failed (1 deprecation warning from deep_sort_realtime)
- **New Unit Test Added**: `test_coasted_tracks_excluded_from_visible_tracks` in `tests/test_dual_mode.py` explicitly verifies that `PersonTracker.get_visible_tracks()` returns tracks with `time_since_update == 0` while excluding coasted tracks (`time_since_update > 0`).

---

## 6. Remaining Limitations & Considerations

1. **Transient Occlusion Visibility**: In skipped detection frames (when `detect_interval > 1`), cyan boxes momentarily unrender until the next detection update frame.
2. **Dense Crowd Model Limits**: V4 head detector in full-frame mode captures ~13.66 visible heads/frame and in 2×2 tiled mode captures ~20.75 visible heads/frame on overhead dense crowd video. This reflects true detector performance on small overhead heads (~15–35 px tall).

---

OVERLAY FIX COMPLETE — READY FOR REVIEW
