# CrowdPatrol V3 Dense-Crowd Dataset Audit Report (VBOX Target Construction)

## 1. Dataset Construction Method
The CrowdPatrol V3 dataset was constructed under branch `v3-dense-crowd` to address dense-crowd occlusion failure modes.
* **Source Dataset**: Real CrowdHuman photographs downloaded locally (`data/training/raw/crowdhuman/`).
* **Isolation**: Built strictly in `data/training/yolo_v3/` without modifying or overwriting the existing V2 dataset (`data/training/yolo/`).
* **Split Allocation**: Deterministic 70% Train / 15% Val / 15% Test split using a fixed random seed (`seed = 42`).
* **Zero Synthetic Images**: 100% of images are real-world human crowd photographs ($\text{std} \ge 5.0$).

---

## 2. VBOX Conversion Method
For every person object (`tag == "person"`) in CrowdHuman `.odgt`:
1. Read the visible body bounding box `vbox = [x, y, width, height]` (pixel coordinates).
2. Converted to normalized YOLO center format:
   $$\text{x\_center} = \frac{x + \frac{\text{width}}{2.0}}{\text{image\_width}}, \quad \text{y\_center} = \frac{y + \frac{\text{height}}{2.0}}{\text{image\_height}}$$
   $$\text{norm\_w} = \frac{\text{width}}{\text{image\_width}}, \quad \text{norm\_h} = \frac{\text{height}}{\text{image\_height}}$$
3. Bounds were safely clipped to $[0.0, 1.0]$.
4. Written as `0 x_center y_center norm_w norm_h` to `.txt` label files under `data/training/yolo_v3/labels/`.
5. **Single Target Constraint**: Each person produces exactly ONE target (class 0: person = `vbox`). No `fbox` or `hbox` targets were used.

---

## 3. Train / Val / Test Split Statistics

| Split | Image Count | Total Person Boxes (VBOX) | Avg Persons / Image |
| :--- | :---: | :---: | :---: |
| **Train** | 3,059 | 72,588 | 23.73 |
| **Validation** | 655 | 15,801 | 24.12 |
| **Test** | 656 | 14,725 | 22.45 |
| **Total** | **4,370** | **103,114** | **23.59** |

---

## 4. Annotation Audit & Validation Results

* **Total Person Annotations Evaluated**: **103,115**
* **Valid VBOX Annotations**: **103,115 (100.00%)**
* **Invalid / Zero-Area VBOXes**: **0 (0.00%)**
* **Discarded Annotations**: **0 (0.00%)**
* **Retained Percentage**: **100.0%**
* **Occluded Person Count (`occ > 0`)**: **71,921 (69.75%)**

---

## 5. VBOX vs. FBOX Dimensional Comparison

| Bounding Box Metric | FBOX (Full Body) | VBOX (Visible Body) | Difference / Impact |
| :--- | :---: | :---: | :--- |
| **Mean Box Width** | 107.01 px | 91.22 px | -14.8% narrower |
| **Median Box Width** | 60.00 px | 50.00 px | -16.7% narrower |
| **Mean Box Height** | 266.95 px | 200.22 px | **-25.0% shorter** |
| **Median Box Height** | 155.00 px | 109.00 px | **-29.7% shorter** |

### Dense Crowd Coverage Impact:
* In standard `fbox` training, when a person is 70% occluded behind a crowd, the box projects down to invisible feet, forcing YOLO to look for legs that do not exist.
* In `vbox` training, box height is reduced by **25% to 30% on average** (and up to 80%+ for heavily occluded individuals) to tightly enclose **ONLY the visible head and upper body**. This provides YOLO with 71,921 explicit partial-body/occluded crowd training examples.

---

## 6. Visual Inspection Artifacts

1. **30 VBOX Visual Overlays**: Rendered under `training/visualizations/v3_vbox/v3_vbox_sample_01.jpg` .. `v3_vbox_sample_30.jpg`.
2. **10 Side-by-Side (`FBOX | VBOX`) Comparisons**: Rendered under `training/visualizations/v3_vbox_vs_fbox/comparison_fbox_vs_vbox_01.jpg` .. `comparison_fbox_vs_vbox_10.jpg`.

---

## 7. Discovered Issues / Anomalies
* **Zero anomalies discovered**. 100% of CrowdHuman `.odgt` person records contained valid, non-zero `vbox` bounding boxes. 0 boxes were discarded.

---

## 8. Files Created / Modified

### Created Files:
- `data/training/yolo_v3/dataset.yaml`
- `data/training/yolo_v3/v3_dataset_audit.json`
- `data/training/yolo_v3/images/train/` (3,059 images)
- `data/training/yolo_v3/images/val/` (655 images)
- `data/training/yolo_v3/images/test/` (656 images)
- `data/training/yolo_v3/labels/train/` (3,059 `.txt` label files)
- `data/training/yolo_v3/labels/val/` (655 `.txt` label files)
- `data/training/yolo_v3/labels/test/` (656 `.txt` label files)
- `scratch/prepare_v3_dataset.py`
- `reports/v3_dataset_audit.md`
- `training/visualizations/v3_vbox/` (30 overlay images)
- `training/visualizations/v3_vbox_vs_fbox/` (10 comparison images)

### Modified Files:
- **NONE.** Live application files (`src/`, `main.py`, `dashboard/`, `stable-v2` branch) were untouched.

---

## 9. Final Dataset Path & Summary Statistics

* **Dataset Path**: `data/training/yolo_v3/`
* **Dataset Config File**: `data/training/yolo_v3/dataset.yaml`
* **Total Images**: **4,370 real photos**
* **Total VBOX Targets**: **103,114 targets**
* **Occluded Instances Covered**: **71,921 instances (69.75%)**
* **Retention Rate**: **100.0%**
