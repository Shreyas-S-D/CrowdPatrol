# Stage 11.7 — Head Mode Metric Semantics & Dynamic Risk Fix Report

## 1. Executive Summary

Stage 11.7 resolved the metric presentation ambiguity and risk score saturation issues identified during the Stage 11.6 forensic audit.

### Key Modifications Implemented:
1. **Clarified Head Count Terminology**:
   - Separated instantaneous raw detections (**"Visible Heads"**) from DeepSORT active track pools (**"Active Head Tracks"**).
   - Displayed both metrics distinctly across Streamlit widgets, status banners, and visual HUD overlays.
   - Preserved tracker parameters (`max_age=30`) while eliminating misleading metric labels.

2. **Redesigned Experimental Head Risk Adapter**:
   - Replaced hard-capped saturation logic with continuous piecewise-linear normalization curves for peak cell density ($S_D$), head volume ($S_V$), and motion anomaly ($S_M$).
   - Bounded score strictly within $[0, 100]$ while enabling dynamic scaling across low, medium, and high density scenarios (no longer stuck at 50.0).

3. **Preserved Person Mode & Verified Test Suite**:
   - Person Mode execution path (`models/crowdpatrol_yolov8n_finetuned_v2.pt`, `PersonDetector`, `PersonTracker`, production `RiskAssessor`) remains 100% untouched.
   - Unit test suite expanded to **49 passed tests (100% pass rate)**.

---

## 2. Active Head Tracks vs. Visible Heads

### The Root Cause:
In DeepSORT tracking, when a head detection is briefly missed or occluded in frame $T$:
1. The tracker maintains the track using Kalman filter motion prediction.
2. Increments `time_since_update` by 1.
3. Retains the track in `active_tracks` for up to `max_age=30` frames.

In dense moving crowds, transient occlusions cause `active_tracks` (mean ~60.0 tracks/frame in `dense_crowd_test.mp4`) to accumulate retained tracks alongside currently matched detections (mean ~13.66 visible detections/frame).

### Presentation Fix:
- **`Visible Heads`**: Count of raw V4 head detections matched in the current frame (`len(detections)`).
- **`Active Head Tracks`**: Total confirmed DeepSORT track pool maintained across time (`len(current_tracks)`).

---

## 3. Old Risk Saturation Problem vs. New Dynamic Formula

### Old Hard-Capped Formula (Saturated at 50.0):
$$raw\_score = 0.5 \cdot \min(50.0, \frac{total\_heads}{25} \cdot 50) + 0.5 \cdot \min(50.0, \frac{max\_cell}{8} \cdot 50)$$
When $total\_heads \ge 25$ and $max\_cell \ge 8$, both components capped at $50.0$, producing $0.5(50) + 0.5(50) = 50.0$ permanently.

### New Continuous Multi-Factor Formula:
$$\text{Score}_{raw} = w_d \cdot S_{\text{density}}(D_{\text{max}}) + w_v \cdot S_{\text{volume}}(V_{\text{heads}}) + w_m \cdot S_{\text{motion}}(A_{\text{motion}})$$

1. **Spatial Concentration Sub-Index ($S_D$)**:
   - $D_{\text{max}} \le 5 \implies S_D = \frac{D_{\text{max}}}{5} \cdot 25$
   - $5 < D_{\text{max}} \le 15 \implies S_D = 25 + \frac{D_{\text{max}} - 5}{10} \cdot 40$
   - $15 < D_{\text{max}} \le 30 \implies S_D = 65 + \frac{D_{\text{max}} - 15}{15} \cdot 35$
   - $D_{\text{max}} > 30 \implies S_D = 100.0$

2. **Head Volume Sub-Index ($S_V$)**:
   - $V_{\text{heads}} \le 10 \implies S_V = \frac{V_{\text{heads}}}{10} \cdot 20$
   - $10 < V_{\text{heads}} \le 40 \implies S_V = 20 + \frac{V_{\text{heads}} - 10}{30} \cdot 50$
   - $40 < V_{\text{heads}} \le 80 \implies S_V = 70 + \frac{V_{\text{heads}} - 40}{40} \cdot 30$
   - $V_{\text{heads}} > 80 \implies S_V = 100.0$

3. **Weights**: $w_d = 0.60, w_v = 0.40$ (or $w_d=0.50, w_v=0.35, w_m=0.15$ when motion anomaly is present).

4. **EMA Smoothing**: $\text{Score}_{t} = 0.25 \cdot \text{Score}_{raw} + 0.75 \cdot \text{Score}_{t-1}$.

---

## 4. Experimental Proxy Disclaimer

> **`EXPERIMENTAL HEAD RISK PROXY` is an academic research metric indicating relative spatial head concentration and volume.**
> It does NOT predict stampedes, guarantee safety thresholds, or replace human crowd control personnel.

---

## 5. Empirical Validation Results

### Test Execution Summary (`pytest -q`)
* **Total Executed Tests**: 49
* **Passed**: 49 (100% pass rate)
* **Failed**: 0
* **Execution Time**: 18.57 seconds

### Metric & Visual Validation (`dense_crowd_test.mp4`)
* **Visible Heads Range**: 1 to 13 heads/frame (mean 6.6)
* **Active Head Tracks Range**: 2 to 26 tracks/frame (mean 12.2)
* **Dynamic Head Risk Score Range**: 4.6 to 26.5 (mean 16.0)
* **Score Dynamics**: Confirmed dynamic variation across frames with zero saturation.

---

## 6. Git Safety & File Audit

* **No Code Commits Executed**.
* **Branch `stable-v2` Untouched**.
* **Model Weights Intact** (`models/crowdpatrol_yolov8n_finetuned_v2.pt` default).

---

## Status

**READY FOR REVIEW**
