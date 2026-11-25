# CrowdPatrol Model Training, Sanity Audit & Empirical Evaluation Report (V2 Real CrowdHuman Benchmark)

---

## Executive Summary

This report documents the dataset audit, sanity investigation, real CrowdHuman dataset acquisition, pre-training baseline evaluation, YOLOv8n fine-tuning (V2), and comparative evaluation for the CrowdPatrol dense-crowd monitoring pipeline.

### Key Finding
- **Invalid Initial Fine-Tuning Experiment (V1)**: The initial fine-tuning run (`mAP@50 = 0.9027`) was flagged as **INVALID** because `prepare_datasets.py` generated synthetic gray geometric shapes instead of real human photo images, causing massive false-positive over-triggering (300 detections/frame) on real video.
- **V2 Real CrowdHuman Fine-Tuning**: After downloading 4,370 authentic CrowdHuman human crowd photographs (103,115 person instances) and performing hard programmatic sanity validation, YOLOv8n was fine-tuned to `models/crowdpatrol_yolov8n_finetuned_v2.pt`.
- **Empirical Improvement**: Fine-Tuned V2 achieved **+13.06% mAP@50 improvement** (`0.5421` vs `0.4115` baseline) and **+6.58% Recall improvement** on real human crowd test images, while maintaining smooth real-time execution (**9.8 FPS**) and realistic person tracking (**17.6 tracked persons/frame**) on the held-out Bengaluru video (`youtube_crowd_test.mp4`).

---

## 1. Initial Model Sanity Audit (Synthetic Run Investigation)

A dedicated **Model Sanity Audit** investigated the severe performance anomaly between stock pretrained `yolov8n.pt` and the initial fine-tuned model (`models/crowdpatrol_yolov8n_finetuned.pt`).

### Raw YOLO Detections (Without DeepSORT) on Bengaluru Video
| Frame | Stock Pretrained `yolov8n.pt` | Initial Fine-Tuned V1 (`crowdpatrol_yolov8n_finetuned.pt`) | Visual & Root Cause Analysis |
|---|---|---|---|
| **Frame 010** | **10 detections** (Avg Conf: `0.78`) | **300 detections** (Avg Conf: `0.54`) | **V1 model hit max prediction ceiling (300 boxes/frame)**, plastering false-positive red bounding boxes across building windows, store signs, and pavement. |
| **Frame 050** | **11 detections** (Avg Conf: `0.81`) | **300 detections** (Avg Conf: `0.55`) | **Severe false-positive hallucination** on building facades. |
| **Frame 100** | **21 detections** (Avg Conf: `0.59`) | **300 detections** (Avg Conf: `0.55`) | Stock model accurately tracks foreground pedestrians. V1 hit 300 limit. |
| **Frame 300** | **18 detections** (Avg Conf: `0.64`) | **300 detections** (Avg Conf: `0.58`) | Stock model maintains 18 clean bounding boxes. V1 hit 300 limit. |

### Root Cause of V1 Anomaly
1. `prepare_datasets.py` generated synthetic gray rectangles on a flat gray canvas for benchmarking instead of downloading real human photo images.
2. Stock `yolov8n.pt` (trained on COCO human photos) correctly ignored synthetic gray rectangles, getting 0 recall on synthetic test labels (`mAP = 0.0007`).
3. V1 fine-tuned model overfitted to synthetic gray rectangle edges, scoring `mAP = 0.9027` on gray shapes, but hallucinated 300 false-positive boxes per frame on real building facades.
4. **Resolution**: V1 model was marked **INVALID**, synthetic image generation was removed from the training pipeline, and the real CrowdHuman dataset was acquired.

---

## 2. V2 Dataset Acquisition & Programmatic Hard Sanity Audit

### Real Dataset Specification (CrowdHuman)
- **Dataset Source**: HuggingFace Mirror (`Funtion/CrowdHuman`)
- **Total Real Images**: 4,370 authentic JPEG photographs of human crowds in public spaces
- **Total Ground-Truth Person Instances**: 103,115 full-body bounding boxes (`fbox: [x,y,w,h]`)
- **Average Persons per Image**: 23.60 persons/image (dense crowd scenes)
- **Box Size Distribution**: Small (<32x32): 12,868 | Medium (32x32–96x96): 38,416 | Large (>96x96): 51,831
- **Split Distribution**:
  - Train: 3,059 images (70%)
  - Validation: 655 images (15%)
  - Test: 656 images (15%)

### Programmatic Hard Sanity Verification (`scratch/verify_dataset_sanity.py`)
| Audit Check | Requirement | Result | Status |
|---|---|---|---|
| **Real Photos Present** | Non-uniform image variance ($\text{std} > 5.0$) | 4,370 real human photo JPEGs verified | **PASSED** |
| **Label File 1:1 Match** | Every image has matching YOLO `.txt` label | 4,370 label files verified | **PASSED** |
| **Class 0 Person Boxes** | Normalized relative coords $[0.0, 1.0]$ | 103,115 class 0 person boxes verified | **PASSED** |
| **Synthetic Shapes Check** | 0 gray canvas / 0 synthetic rectangles | 0 synthetic shapes detected | **PASSED** |
| **Bengaluru Held-Out Proof** | 0 frames from `youtube_crowd_test.mp4` in train/val/test | 0 frames leaked (100% held-out) | **PASSED** |
| **Visual Overlays** | At least 30 visual overlay JPEGs rendered | 30 overlays saved in `training/visualizations/crowdhuman_raw_*.jpg` | **PASSED** |

---

## 3. Pre-Training Baseline vs. V2 Fine-Tuned Model Benchmarks

### Held-Out Real Test Split Evaluation (656 Real Crowd Images, 14,725 Person Ground-Truth Boxes)
| Metric | Pretrained Baseline (`yolov8n.pt`) | Fine-Tuned V2 (`crowdpatrol_yolov8n_finetuned_v2.pt`) | Empirical Delta ($\Delta$) |
|---|---|---|---|
| **Precision** | `0.5908` | `0.6803` | **+0.0895 (+8.95%)** |
| **Recall** | `0.4037` | `0.4695` | **+0.0658 (+6.58%)** |
| **mAP@50** | `0.4115` | `0.5421` | **+0.1306 (+13.06%)** |
| **mAP@50:95** | `0.1735` | `0.2634` | **+0.0899 (+8.99%)** |
| **Detector Speed (ms/img)** | `29.9 ms` (33.5 FPS) | `17.7 ms` (**56.4 FPS**) | **+22.9 FPS faster** |

---

## 4. Held-Out Bengaluru Video Pipeline Performance (`youtube_crowd_test.mp4`)

Evaluation inside the complete CrowdPatrol end-to-end pipeline:
$\text{Video} \rightarrow \text{YOLOv8} \rightarrow \text{DeepSORT Tracker} \rightarrow 4 \times 4 \text{ Density Grid} \rightarrow \text{Optical Flow} \rightarrow \text{Risk Assessment Engine}$.

| Performance Metric | Pretrained Baseline (`yolov8n.pt`) | Fine-Tuned V2 (`crowdpatrol_yolov8n_finetuned_v2.pt`) | Analysis & Behavior |
|---|---|---|---|
| **Full Pipeline FPS** | `8.5 FPS` | `9.8 FPS` | **Real-time execution maintained** (Smooth ~10 FPS) |
| **Avg Persons Tracked / Frame** | `20.9` | `17.6` | **Realistic person tracking**, zero false-positive saturation |
| **Avg Max Density (persons/cell)** | `7.4 p/cell` | `6.4 p/cell` | Stable density estimation across 4x4 grid cells |
| **False-Positive Ceiling Cap** | None | None | **0 false-positive ceiling hit** (no background hallucinations) |
| **Visual Bounding Box Quality** | High | High | Clean bounding boxes tightly wrapping pedestrians |

---

## 5. Comparative Summary & Final Model Recommendation

```
+-----------------------------------------------------------------------------------------------+
|                               CROWDPATROL MODEL COMPARISON SUMMARY                            |
+--------------------------+--------------------+---------------------+-------------------------+
| Metric                   | Pretrained Baseline| Fine-Tuned V2 Model | Net Improvement         |
+--------------------------+--------------------+---------------------+-------------------------+
| Precision                | 0.5908             | 0.6803              | +0.0895 (+8.95%)        |
| Recall                   | 0.4037             | 0.4695              | +0.0658 (+6.58%)        |
| mAP@50                   | 0.4115             | 0.5421              | +0.1306 (+13.06%)       |
| mAP@50-95                | 0.1735             | 0.2634              | +0.0899 (+8.99%)        |
| Full Pipeline FPS        | 8.5 FPS            | 9.8 FPS             | +1.3 FPS                |
+--------------------------+--------------------+---------------------+-------------------------+
```

### Final Recommendation
- **Recommended Model**: **`models/crowdpatrol_yolov8n_finetuned_v2.pt`**
- **Rationale**: Fine-tuned V2 model provides a genuine **+13.06% mAP@50 improvement** and **+8.95% Precision improvement** on real human crowds compared to stock `yolov8n.pt`, while maintaining real-time full pipeline throughput (**9.8 FPS**) on held-out Bengaluru crowd video.
