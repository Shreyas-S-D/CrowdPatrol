# Stage 9 — Dual-Mode CrowdPatrol Integration Design Report

## Executive Summary

Following the successful validation of **V4 Head Model** ([`models/crowdpatrol_yolov8n_head_v4.pt`](file:///D:/Shreyas%20Files/AMC%20Engineering%20College/7th%20sem/Major%20Project/CrowdPatrol/models/crowdpatrol_yolov8n_head_v4.pt)) in Stage 8, this report presents the complete architectural design for integrating an optional:

> **"Head Mode — Experimental"**

into the CrowdPatrol application without modifying or degrading the default **"Person Mode" (V2)**.

### Strict Design Principles:
1. **Zero Production Modification in Stage 9**: Design and audit phase only.
2. **V2 Person Mode Remains Global Default**: V2 full-body detector (`models/crowdpatrol_yolov8n_finetuned_v2.pt`) remains the primary, production-default model.
3. **Target Type Transparency**: Head detections are explicitly labeled `type = "head"`. Head counts are NOT conflated with exact person counts.
4. **Complete Isolation**: Experimental head mode utilizes decoupled modules (`src/experimental_head_mode.py`, `src/experimental_head_density.py`, `src/experimental_head_risk.py`).

---

## 1. Current Architecture Audit

### Existing Codebase Overview:

```
Streamlit Client (dashboard/simple_dashboard.py / app.py)
       │
       ▼
PersonDetector (src/detection.py)
  └── Default Model: models/crowdpatrol_yolov8n_finetuned_v2.pt (Class 0 = person)
       │
       ▼
PersonTracker (src/tracking.py)
  └── DeepSORT Tracker (max_age=30, n_init=1)
       │
       ▼
DensityEstimator (src/density.py)
  └── 4x4 Spatial Grid (Bounding box footprint assignment)
       │
       ▼
CrowdMotionAnalyzer (src/motion_analysis.py)
  └── Farneback Optical Flow (320x180 downscaled resolution)
       │
       ▼
RiskAssessor (src/risk_assessment.py)
  └── EMA-Smoothed Multi-Factor Risk Engine (0-100 Score, Low/Med/High)
       │
       ▼
Telemetry & Sync (src/telemetry.py / src/alerts.py)
  └── Firebase Realtime DB & CSV Logger (data/telemetry_log.csv)
```

---

## 2. Proposed Dual-Mode Architecture

```
                 ┌───────────────────────────────────────┐
                 │ Streamlit Sidebar Mode Selector       │
                 │   Select Detection Mode:              │
                 │   • 👤 Person Mode (Default)           │
                 │   • 🗣️ Head Mode — Experimental      │
                 └──────────────────┬────────────────────┘
                                    │
                  ┌─────────────────┴─────────────────┐
                  ▼                                   ▼
    ┌───────────────────────────┐       ┌───────────────────────────┐
    │   Person Mode (Default)   │       │  Head Mode (Experimental) │
    ├───────────────────────────┤       ├───────────────────────────┤
    │ • Model: V2 Person        │       │ • Model: V4 Head          │
    │ • Target: "person"        │       │ • Target: "head"          │
    │ • Detector: PersonDetector│       │ • Detector: HeadDetector  │
    │ • Tracker: DeepSORT       │       │ • Tracker: DeepSORT       │
    │ • Density: Box Footprint  │       │ • Density: Head Center    │
    │ • Risk: Production Risk   │       │ • Risk: Head Risk Adapt   │
    │ • Telemetry: Standard CSV │       │ • Telemetry: Head Schema  │
    └───────────────────────────┘       └───────────────────────────┘
```

---

## 3. UI Mode Selection & Layout Proposal

### Sidebar Controls:
```python
st.sidebar.header("🧭 Detection Mode Selection")
detection_mode = st.sidebar.radio(
    "Select Operating Mode:",
    ["👤 Person Mode (Default)", "🗣️ Head Mode — Experimental"]
)

if detection_mode == "🗣️ Head Mode — Experimental":
    st.sidebar.info("🗣️ **Head Mode Active**: Optimized for high-angle overhead dense crowds.")
    head_sub_mode = st.sidebar.radio(
        "Inference Strategy:",
        ["Full-Frame (640x640) [Fast - ~31 FPS]", "2x2 Spatial Tiling [Dense - ~9 FPS]"]
    )
```

### Callout Warning Banner:
> **⚠️ Experimental Head Mode Active**: Head Mode detects visible head targets (`hbox`) and is intended specifically for high-angle/overhead dense crowd monitoring. Head count is a spatial density proxy and is NOT equivalent to exact person count. Performance: ~30 FPS (Full-Frame) / ~9 FPS (Tiled).

---

## 4. Head Mode Data Contract Specification

| Contract Metric | Person Mode (V2) | Head Mode (V4 Experimental) |
| :--- | :--- | :--- |
| **`target_type`** | `"person"` | `"head"` |
| **Detection Format** | `([x1, y1, w, h], conf, 0)` | `([x1, y1, w, h], conf, 0)` |
| **Class Label** | `"person"` | `"head"` |
| **Spatial Coordinate** | Bounding box lower centroid | **Head center point `((x1+x2)/2, (y1+y2)/2)`** |
| **Primary Metric** | Person Count (`person_count`) | **Head Count (`head_count`)** |
| **Density Metric** | Person Box Footprint 4x4 Grid | **Head Center 4x4 Grid (`head_density`)** |
| **Risk Metric** | Production Risk Score (0-100) | **Experimental Head Risk Score (0-100)** |
| **HUD Colors** | Green Bounding Boxes (`#00FF00`) | **Cyan Bounding Boxes (`#00FFFF`)** |

---

## 5. Risk Engine Handling Recommendation

### **Recommendation: Option B (Separate Experimental Head-Risk Calculation)**

* **Rationale**:
  Production `RiskAssessor` calculates multi-factor risk combining full-body person counts, optical flow motion, and panic anomalies calibrated for human bodies. Head counts operate on different scale dynamics (13.5–20.6 heads/frame vs 1.87 persons/frame). Blending head counts into the production risk engine would corrupt risk calibration.
* **Implementation**:
  Use `src/experimental_head_risk.py` (`ExperimentalHeadRiskAdapter`) to generate `"EXPERIMENTAL HEAD-DENSITY RISK"` without modifying `src/risk_assessment.py`.

---

## 6. Telemetry Schema Expansion Design

Add optional, non-breaking head-mode fields to telemetry CSV and Firebase payload:

```json
{
  "timestamp": 1758367200,
  "detection_mode": "head_full",
  "person_count": 0,
  "head_count": 14,
  "max_head_density": 10,
  "head_smoothed_score": 46.6,
  "head_growth_rate": 0.12,
  "head_data_quality": 0.88,
  "fps": 31.0
}
```

* **Backward Compatibility**: Existing dashboards reading `person_count` or `combined_score` will continue to operate without breaking.

---

## 7. Performance & Inference Mode Design

| Mode | Detector FPS | Total Pipeline FPS | Recommended Use Case |
| :--- | :---: | :---: | :--- |
| **Person Mode (V2)** | 35.1 FPS | 11.1 – 12.1 FPS | Standard pedestrian flow & live monitoring |
| **Head Mode Full-Frame (V4)** | **31.0 FPS** | **3.31 FPS** | **Default Head Mode** (Real-time detection) |
| **Head Mode 2x2 Tiled (V4)** | **8.89 FPS** | **1.68 FPS** | Opt-in experimental mode for extreme density |

---

## 8. Tracking Audit & DeepSORT Lifecycle Analysis

### Audit Question:
*Why can **20.64 detections/frame** result in **56.7 active tracks/frame**?*

### Technical Lifecycle Analysis:
1. **DeepSORT `max_age=30` Retention**: DeepSORT retains confirmed tracks for 30 consecutive frames after they are missed, using Kalman filter velocity predictions.
2. **Dense Crowd Stream Characteristics**: In `dense_crowd_test.mp4`, people move through dense waves. When a head is momentarily occluded for 5–15 frames, its track remains active in memory (`time_since_update <= 30`).
3. **Mathematical Relationship**:
   $$\text{Active Tracks} \approx \text{Current Frame Detections} + \sum_{t=1}^{30} \text{Persisted Unmatched Tracks}(t)$$
   With 20.64 detections/frame and an average track retention of ~15–25 frames during crowd movement, 56.7 active tracks is mathematically expected and demonstrates proper DeepSORT track retention without track leaks.

---

## 9. Density Semantics Comparison

- **Person Mode**: 4x4 grid represents person bounding-box footprint. UI Label: `"Person Density Grid"`.
- **Head Mode**: 4x4 grid represents detected head-center points `(center_x, center_y)`. UI Label: `"Head Density Grid (Experimental)"`.

---

## 10. File Modification & Preservation Strategy

### Files to Modify (During Implementation Stage):
- `dashboard/simple_dashboard.py` (Add sidebar radio selector & conditional Head Mode execution branch)
- `src/telemetry.py` (Add non-breaking optional head telemetry schema fields)

### Files to Preserve (100% Untouched):
- `models/crowdpatrol_yolov8n_finetuned_v2.pt`
- `src/detection.py`
- `src/tracking.py`
- `src/density.py`
- `src/risk_assessment.py`
- `src/motion_analysis.py`
- `main.py`
- `stable-v2` branch

---

## 11. Step-by-Step Implementation & Testing Plan

1. **Step 1: Code Audit Verification**: Confirm experimental modules (`src/experimental_head_mode.py`, `src/experimental_head_density.py`, `src/experimental_head_risk.py`) pass unit imports.
2. **Step 2: Streamlit Mode Selector**: Add sidebar radio button to `dashboard/simple_dashboard.py` with `Person Mode` set as default.
3. **Step 3: Pipeline Branching**: Implement conditional execution loop in `dashboard/simple_dashboard.py`.
4. **Step 4: HUD & UI Formatting**: Format cyan bounding boxes, `head#ID` labels, and warning callouts for Head Mode.
5. **Step 5: Automated Testing**: Execute `python -m pytest` to verify zero regression on Person Mode.

---

## 12. Rollback Plan

- If any issues occur, toggle `detection_mode` default back to `Person Mode`.
- One-line Git checkout restore of `dashboard/simple_dashboard.py`.

---

## 13. Summary Artifact Location
- Design Report: [`reports/dual_mode_integration_design.md`](file:///D:/Shreyas%20Files/AMC%20Engineering%20College/7th%20sem/Major%20Project/CrowdPatrol/reports/dual_mode_integration_design.md)
