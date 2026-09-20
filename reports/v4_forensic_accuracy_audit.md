# Stage 11.6 — V4 Head Detection Accuracy Forensic Audit Report

## 1. Executive Findings

A forensic audit of the V4 Head Detection pipeline (`models/crowdpatrol_yolov8n_head_v4.pt`) was conducted on 300 frames of `data/videos/dense_crowd_test.mp4`.

### Key Discoveries & Diagnostic Explanations:
1. **Discrepancy Between Detector Output and "Tracked Heads" Metric**:
   - Raw V4 Detector produces an average of **13.52 head detections/frame**.
   - Live Dashboard displays **"Tracked Heads: ~60.0"** (mean active tracks: 60.00 / frame).
   - Out of 60.00 active tracks, only **13.66** are currently visible/matched in the frame (`time_since_update == 0`).
   - The remaining **46.34** tracks are *retained/coasted tracks* (`time_since_update > 0`) kept alive by DeepSORT's Kalman filter during `max_age=30` frames of occlusion/missed detection.
   - **Verdict**: The dashboard metric "Tracked Heads" represents **Option B: Active DeepSORT tracks including retained/coasted tracks (`max_age=30`)**, NOT current raw detections or pure visible head counts.

2. **Bounding Box Sanity**:
   - Raw V4 head bounding boxes are genuinely small and appropriate for head targets: **mean width = 31.9 px**, **mean height = 38.3 px**.
   - Only **0.02%** of boxes exceed 80 px in width and **0.35%** exceed 80 px in height.
   - Large cyan boxes on the dashboard UI are NOT coming from the detector; raw detector outputs are tightly centered on heads.

3. **HBOX Annotation Conversion**:
   - CrowdHuman `.odgt` source annotations (`hbox: [hx, hy, hw, hh]`) were converted to normalized YOLO format using $x_c = (hx + hw/2)/w_{img}$, $y_c = (hy + hh/2)/h_{img}$, $nw = hw/w_{img}$, $nh = hh/h_{img}$.
   - The mathematical conversion is 100% exact. Boxes were NOT enlarged or distorted during conversion.

4. **UI Metric Saturation (SCORE 50.0 & RISK: MEDIUM)**:
   - `ExperimentalHeadRiskAdapter` calculates $raw\_score = 0.5 \cdot \min(50, \frac{total\_heads}{25} \cdot 50) + 0.5 \cdot \min(50, \frac{max\_cell}{8} \cdot 50)$.
   - When active track count $total\_heads \ge 25$ AND peak cell density $max\_cell \ge 8$, both terms cap at $50.0$.
   - Consequently, the raw score evaluates to $0.5(50) + 0.5(50) = 50.0$, causing the score to saturate at **50.0** and yield **RISK: MEDIUM** continuously.

---

## 2. Raw Detection Statistics (300 Frames Audited)

* **Video**: `data/videos/dense_crowd_test.mp4`
* **Frames Audited**: 300
* **Total Raw Detections**: 4,055 boxes
* **Detections / Frame**:
  - Mean: **13.52** heads/frame
  - Median: **10.0** heads/frame
  - Min: 1 head/frame
  - Max: 45 heads/frame
  - Std Dev: 10.38
* **Confidence Distribution**:
  - Mean: **0.45**
  - Median: **0.43**
  - Min: 0.35 (configured threshold)
  - Max: 0.81
  - Percentiles: $p_{25} = 0.38$, $p_{50} = 0.43$, $p_{75} = 0.50$, $p_{90} = 0.57$

---

## 3. Tracking Statistics & Track Breakdown

| Track Category | Mean Count / Frame | Median Count / Frame | Description |
| :--- | :---: | :---: | :--- |
| **Raw V4 Detections** | 13.52 | 10.0 | Raw detector output before DeepSORT |
| **Visible / Matched Tracks** | **13.66** | **10.0** | DeepSORT tracks matched to current frame detections (`time_since_update == 0`) |
| **Retained / Coasted Tracks** | **46.34** | **31.0** | Unmatched tracks retained by Kalman filter (`1 <= time_since_update <= 30`) |
| **Total Active Tracks (`current_tracks`)** | **60.00** | **38.0** | Total tracks displayed on Dashboard (`Tracked Heads`) |
| **Total Track IDs Created** | 640 | N/A | Cumulative track IDs assigned across 300 frames |

---

## 4. Bounding Box Dimensions & Sanity Analysis

* **Box Width**:
  - Mean: **31.9 px** | Median: **29.9 px** | Min: 15.9 px | Max: 80.4 px
* **Box Height**:
  - Mean: **38.3 px** | Median: **35.5 px** | Min: 20.1 px | Max: 135.4 px
* **Box Area**:
  - Mean: **1,295.6 px²** | Median: **1,059.2 px²** | Min: 381.2 px² | Max: 7,759.8 px²
* **Oversized Box Ratio**:
  - Width > 80 px: **0.02%** (1 out of 4,055 boxes)
  - Height > 80 px: **0.35%** (14 out of 4,055 boxes)

---

## 5. NMS & Duplicate Detection Analysis

* **Overlapping Pairs Evaluated** (IoU > 0.05): 83 pairs across 300 frames.
* **Mean IoU of Overlapping Pairs**: 0.266
* **Pairs with IoU $\ge$ 0.30**: 29 pairs (34.9% of overlapping pairs)
* **Pairs with IoU $\ge$ 0.50**: 25 pairs (30.1% of overlapping pairs)

---

## 6. HBOX Label Conversion Audit

* **Source Format**: CrowdHuman `.odgt` `hbox: [hx, hy, hw, hh]` (top-left $x, y$, width $w$, height $h$).
* **Target Format**: YOLO normalized $0 \ \ x_c \ \ y_c \ \ w \ \ h$.
* **Audit Result**: Verified 100% mathematical fidelity across `data/training/yolo_v3_head/`.
* **Visual Audit Artifacts**: Generated 10 ground-truth vs prediction side-by-side comparison images under `training/visualizations/v4_forensic_audit/gt_vs_pred_sample_01.jpg` .. `10.jpg`.

---

## 7. DeepSORT Retention Mechanism Audit

When a head detection is missed in frame $T$:
1. DeepSORT advances the track's Kalman filter prediction for frame $T$.
2. Increments `time_since_update` by 1.
3. Keeps the track in `active_tracks` as long as `time_since_update <= max_age` (30 frames).
4. If no new detection matches the track for 30 consecutive frames (~3 to 10 seconds depending on frame skip), the track is deleted.

In a dense moving crowd, continuous transient occlusions cause tracks to accumulate in `retained_tracks`, creating an active track pool of ~60.0 tracks for ~13.52 real detections.

---

## 8. Head Density Calculation Audit

`HeadDensityEstimator` calculates spatial density as follows:
1. Receives `current_tracks` (active DeepSORT tracks).
2. Computes head center point $(cx, cy) = (\frac{x1+x2}{2}, \frac{y1+y2}{2})$.
3. Maps $(cx, cy)$ to 4x4 spatial grid cell index $(r, c) = (\lfloor \frac{cy}{cell\_h} \rfloor, \lfloor \frac{cx}{cell\_w} \rfloor)$.
4. `max_density` = peak cell head count = `np.max(density_map)`.

* **Mean Max Cell Density**: 11.46 heads/cell (peak 26 heads/cell).

---

## 9. Risk Score Audit

`ExperimentalHeadRiskAdapter` computes:
- `density_factor` = $\min(50.0, \frac{total\_heads}{25} \cdot 50)$
- `concentration_factor` = $\min(50.0, \frac{max\_cell}{8} \cdot 50)$
- `raw_score` = $0.5 \cdot density\_factor + 0.5 \cdot concentration\_factor$
- `smoothed_score` = EMA with $\alpha = 0.25$.

### Why UI Repeatedly Displayed `SCORE: 50.0`, `RISK: MEDIUM`, `Anomaly: 0.00`:
- **Score 50.0**: Saturated because $total\_heads \ge 25$ and $max\_cell \ge 8$.
- **Risk MEDIUM**: $25.0 \le 50.0 < 60.0 \implies$ MEDIUM.
- **Anomaly 0.00**: Anomaly score is computed by optical flow motion analyzer; in static/slow crowd scenes or when motion magnitude is low, anomaly score remains 0.00.

---

## 10. Visual Diagnostic Findings

20 raw diagnostic frames were generated under `training/visualizations/v4_forensic_audit/raw_v4_frame_005.jpg` .. `290.jpg` showing:
- **Red Boxes**: Raw V4 Detector detections.
- **Cyan Boxes**: DeepSORT active tracks.
- **Observation**: Red raw detector boxes are small (31.9 x 38.3 px) and tightly bound around visible heads. Cyan active track boxes stay on screen during brief occlusions due to DeepSORT track retention.

---

## 11. Known Limitations

1. **No Ground-Truth Annotations**: `dense_crowd_test.mp4` lacks frame-level ground-truth bounding box annotations. Absolute counting accuracy cannot be claimed.
2. **DeepSORT Track Retention Inflation**: `max_age=30` inflates active track count relative to instantaneous visible detections.
3. **Risk Score Saturation**: Head risk adapter caps at 50.0 for dense crowds exceeding 25 heads / 8 peak cell density.

---

## 12. Classification of V4 Head Detection

**V4 Head Detection is classified as:**
> **Experimentally useful as a head-based crowd monitoring prototype, but NOT quantitatively validated for absolute crowd count accuracy.**

---

## Final Decision

**NOT READY FOR COMMIT**
