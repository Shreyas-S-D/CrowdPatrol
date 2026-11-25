# CrowdPatrol V3 Dense-Crowd Detector Training Results

## 1. Executive Summary
Under branch `v3-dense-crowd`, Stage 3 training of the **V3 Dense-Crowd Person Detector** (`models/crowdpatrol_yolov8n_dense_v3.pt`) has been completed successfully. The model was trained specifically on CrowdHuman **VBOX (Visible Body)** annotations to improve detection performance in heavily occluded and dense pedestrian scenes.

---

## 2. Environment Information
* **Operating System**: Windows 11
* **CPU / Device**: 13th Gen Intel Core i7-13700H (CPU execution)
* **Python Version**: 3.14.6
* **PyTorch Version**: 2.14.0+cpu
* **Ultralytics Version**: 8.4.152

---

## 3. Dataset & VBOX Strategy
* **Dataset Config Path**: `data/training/yolo_v3/dataset.yaml`
* **Source Dataset**: Real CrowdHuman dataset (4,370 total real photographs, 0 synthetic images).
* **Target Annotations**: **VBOX (Visible Body Bounding Boxes)**.
* **VBOX Rationale**: Standard full-body (`fbox`) targets extend to unobservable feet when people are occluded in dense crowds, forcing detectors to search for non-existent body parts. VBOX targets tightly bound only the visible portions of the head and upper body, providing **71,921 explicit occluded-person instances** (69.75% of dataset) for training.
* **Dataset Splits**:
  * **Train**: 3,059 images (sub-sampled with `fraction=0.35` -> 1,071 training images)
  * **Val**: 655 images (15,800 VBOX instances)
  * **Test**: 656 images (14,725 VBOX instances)

---

## 4. Training Configuration & Hyperparameters
* **Base Weights**: `yolov8n.pt` (Stock baseline COCO weights, NOT V2 model)
* **Epochs**: 3
* **Input Resolution (`imgsz`)**: 480
* **Batch Size**: 16
* **Dataset Fraction**: 0.35 (1,071 train images)
* **Initial Learning Rate (`lr0`)**: 0.01
* **Seed**: 42
* **Device**: `cpu`
* **Output Run Directory**: `training/runs/v3_vbox/crowdpatrol_v3_train/`

---

## 5. Training Duration & Best Epoch
* **Total Training Duration**: **750.90 seconds (12.51 minutes)**
* **Best Epoch**: **Epoch 3** (validation metrics peaked at Epoch 3)

---

## 6. Final Validation Metrics

| Metric | Score | Percentage |
| :--- | :---: | :---: |
| **Precision** | **0.6581** | **65.81%** |
| **Recall** | **0.4639** | **46.39%** |
| **mAP@50** | **0.5312** | **53.12%** |
| **mAP@50-95** | **0.2842** | **28.42%** |

---

## 7. Visual Sanity Check Findings
* **Artifact Directory**: `training/visualizations/v3_training_results/`
* **Output Images**: `v3_sanity_check_01.jpg` through `v3_sanity_check_10.jpg` (10 real CrowdHuman test images evaluated).
* **Key Visual Observations**:
  1. **Tight Visible-Body Boxes**: Bounding boxes tightly wrap visible heads and shoulders without extending into occluded lower bodies.
  2. **Multi-Person Disambiguation**: Overlapping individuals in crowded groups are detected as distinct visible-body instances rather than merged into a single wide box.
  3. **Low False Positives**: Non-human background elements (buildings, vehicles, trees) are correctly ignored.

---

## 8. Model Weights & Summary File Locations
* **Final Model Path**: `models/crowdpatrol_yolov8n_dense_v3.pt`
* **Training Summary Record**: `training/v3_training_summary.json`
* **Run Weights**: `training/runs/v3_vbox/crowdpatrol_v3_train/weights/best.pt`

---

## 9. Model & Application Isolation Summary
* **Branch**: `v3-dense-crowd`
* **Protected Checkpoint**: `stable-v2` branch (commit `3e86e1a`) remains completely unchanged.
* **V2 Model Intact**: `models/crowdpatrol_yolov8n_finetuned_v2.pt` was not modified or overwritten.
* **Production Application**: `src/detection.py`, `main.py`, and `dashboard/` continue to point to V2. V3 has not been set as default.

---

V3 training complete — awaiting controlled V2 vs V3 evaluation.
