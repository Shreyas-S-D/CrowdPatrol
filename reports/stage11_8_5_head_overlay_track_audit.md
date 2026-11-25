# Stage 11.8.5 — Head Overlay Track-State Audit Report

**Date**: 2026-09-20  
**Target Video**: `data/videos/dense_crowd_test.mp4` (300 frames analyzed)  
**Branch**: `v3-dense-crowd`  
**Audit Purpose**: Investigate why the video overlay displays a large number of cyan head boxes while the sidebar reports `Visible Heads: 14` and `Active Tracks: 137`.

---

## Executive Summary

The audit confirmed that **the Head Mode video overlay is currently rendering ALL active DeepSORT tracks, including retained/coasted tracks whose detections occurred up to 30 frames prior**.

Across 300 evaluated frames of `dense_crowd_test.mp4`:
- **Drawn Boxes on Overlay**: `mean = 60.00` (min = 2, max = 146)
- **Active Tracks (Total DeepSORT Pool)**: `mean = 60.00` (min = 2, max = 146)
- **Visible Tracks (`time_since_update == 0`)**: `mean = 13.66` (min = 1, max = 44)
- **Retained / Coasted Tracks (`time_since_update > 0`)**: `mean = 46.34` (min = 0, max = 126)

Mathematical verification proved:
- `drawn_boxes == active_tracks`: **`True` (100% of frames)**
- `drawn_boxes == visible_tracks`: **`False` (0% of frames)**

---

## 1. Trace of the Overlay Rendering Pipeline

1. **Dashboard Loop (`dashboard/simple_dashboard.py`)**:
   - On frame processing, `detector.detect(frame)` generates raw detections.
   - `tracker.update(detections, frame)` (or `tracker.predict()`) returns `current_tracks`.
   - `current_tracks` is populated by `PersonTracker.update()`, which collects all tracks from `DeepSort` where `track.is_confirmed() or (track.time_since_update <= 1 and track.hits >= 1)`.
   - In `PersonTracker`, `n_init=1`, so a track becomes confirmed on its first hit and remains `is_confirmed() == True` for up to `max_age=30` frames without new visual updates.
   - `current_tracks` is passed directly into `FrameAnnotator.create_head_dashboard_frame(..., tracks=current_tracks)`.

2. **Overlay Annotator (`src/utils.py`)**:
   - `create_head_dashboard_frame()` calls `FrameAnnotator.draw_head_tracks(frame, tracks=current_tracks)`.
   - `draw_head_tracks()` iterates over every item in `tracks` and draws a solid cyan bounding box with a `head#<track_id>` badge.
   - **Conclusion**: The overlay renders **Option C — All active DeepSORT tracks including retained/coasted tracks where `time_since_update > 0`**.

---

## 2. 300-Frame Telemetry Breakdown

Extracted telemetry over 300 consecutive frames of `data/videos/dense_crowd_test.mp4`:

| Metric | Mean / Frame | Min / Frame | Max / Frame |
| :--- | :--- | :--- | :--- |
| **Raw V4 Detections** | 13.66 | 1 | 44 |
| **Visible Tracks (`time_since_update == 0`)** | 13.66 | 1 | 44 |
| **Retained / Coasted Tracks (`time_since_update > 0`)** | 46.34 | 0 | 126 |
| **Active Tracks (Total DeepSORT Pool)** | 60.00 | 2 | 146 |
| **Boxes Drawn on Overlay** | **60.00** | **2** | **146** |

### Mathematical Equality Check:
- `drawn_boxes == active_tracks`: **`True` across all 300 frames**
- `drawn_boxes == visible_tracks`: **`False` across all 300 frames**

---

## 3. Visual Diagnostics

Diagnostic frames were generated and saved under `training/visualizations/v4_forensic_audit/track_state/`.

The 3 categories are annotated with distinct visual styles:
1. **RAW CURRENT DETECTIONS**: Green 1px boxes labeled `raw:<conf>`
2. **CURRENT / VISIBLE TRACKS (`tsu == 0`)**: Cyan 2px boxes labeled `vis#<ID>`
3. **RETAINED / COASTED TRACKS (`tsu > 0`)**: Magenta 1px boxes labeled `coast#<ID>(+tsu)`

### Observations from Visual Diagnostics:
- **Ghost Boxes**: Retained/coasted tracks (`coast#<ID>`) persist for up to 30 frames after a head is lost or obscured.
- **Location Drift**: Because small heads in dense overhead crowds move unpredictable distances, Kalman filter predictions for coasted tracks float over empty concrete, body torsos, or adjacent people.
- **Visual Overlap**: In dense regions, dozens of coasted tracks overlap each other, giving the illusion of extreme detection density or detector noise when viewed on a single overlay.

---

## 4. Explanation of the Manual Screenshot Discrepancy

In the user's manual screenshot:
- Sidebar `Visible Heads`: **14** (raw detections in current frame)
- Sidebar `Active Tracks`: **137** (total DeepSORT track pool)
- Video Overlay: **137 cyan head boxes**

### Cause of Discrepancy:
- The sidebar correctly separated instantaneous detections (`Visible Heads: 14`) from the track pool (`Active Tracks: 137`).
- However, the video overlay drew **all 137 active tracks**, rendering 14 true visual head boxes alongside **123 coasted/ghost track boxes**.
- As a result, a human viewer observing the video overlay saw 137 cyan boxes and naturally assumed V4 was detecting 137 objects (or generating spurious boxes everywhere), when in fact V4 had only detected 14 visible heads in that single frame.

---

## 5. Can V4 Detection Recall Be Fairly Judged From Current UI?

**NO.**

Evaluating V4 detection recall by looking at the current Head Mode overlay is misleading:
1. **Conflation of Detections & Coasted Predictions**: Solid cyan boxes do not distinguish between a head visually detected *now* vs. a head predicted from 25 frames ago.
2. **False Perception of Detector Error**: Ghost boxes floating over empty ground make V4 appear to create false positive detections, when those boxes are actually coasted Kalman tracker states.
3. **Obscured Visual Ground Truth**: The sheer volume of magenta/coasted boxes covers actual heads in the frame, making it impossible to visually audit V4's true frame-level recall.

---

## 6. Recommendations for Next Steps

1. **Overlay Display Mode Options**:
   - In production UI, update `FrameAnnotator.draw_head_tracks` (or provide a toggle) to distinguish visible tracks (`time_since_update == 0`) from coasted tracks (`time_since_update > 0`), or optionally render ONLY visible tracks/detections on the video overlay.
2. **Keep Core Tracker / Risk Engine Intact**:
   - Retain DeepSORT active tracks (`person_count`) for density and risk tracking if tracking continuity is required, but separate visual rendering from tracking state memory.
3. **Proceed to V4 Recall Evaluation using Raw/Visible Tracks**:
   - Evaluate V4 detection performance based strictly on raw/visible detections (`time_since_update == 0`) rather than the cluttered 30-frame track history.

---

OVERLAY AUDIT COMPLETE — NOT READY FOR COMMIT
