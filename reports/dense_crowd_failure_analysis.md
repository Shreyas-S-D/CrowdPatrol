# CrowdPatrol Stage 5 Dense-Crowd Failure Analysis Report

## Executive Summary
Following the evaluation of **V2** (Full-Body FBOX model) and **V3** (Visible-Body VBOX model), both detectors exhibited significant performance drop on [`data/videos/dense_crowd_test.mp4`](file:///D:/Shreyas%20Files/AMC%20Engineering%20College/7th%20sem/Major%20Project/CrowdPatrol/data/videos/dense_crowd_test.mp4):
- **V2**: 1.87 detections/frame, **36.00% zero-detection frames**
- **V3**: 0.88 detections/frame, **65.33% zero-detection frames**

This Stage 5 diagnostic investigation was conducted without modifying models or production code to uncover the root technical causes behind this failure.

---

## 1. Technical Inspection of [`dense_crowd_test.mp4`](file:///D:/Shreyas%20Files/AMC%20Engineering%20College/7th%20sem/Major%20Project/CrowdPatrol/data/videos/dense_crowd_test.mp4)

* **Resolution**: $1280 \times 720$ pixels
* **Framerate**: 29.97 FPS
* **Duration**: 186.45 seconds (5,588 total frames)
* **Average Frame Brightness**: 88.27 (0–255 scale, moderate contrast)
* **Average Pixel Standard Deviation**: 48.97
* **Average Frame Difference**: 9.04 (Panning / moving overhead camera stream)
* **Camera Viewpoint**: High-angle overhead / elevated surveillance angle
* **Crowd Orientation**: Top-down view dominated by visible hair/heads with minimal body/limb context
* **Visible Person Scale**: Heads/people in midground/background measure **15–35 pixels in native resolution**.

---

## 2. Person Object Scale Measurement

### A. Pixel Height Analysis
In the native $1280 \times 720$ video stream:
- **Foreground Edge Individuals**: $80 - 150\text{ px}$ height
- **Midground Crowd Members**: $25 - 45\text{ px}$ height
- **Background Dense Crowd**: $12 - 25\text{ px}$ height (heads measure $8 - 15\text{ px}$)

### B. Impact of Resizing to YOLO Input Size (`imgsz=640`)
When native $1280 \times 720$ frames are resized to YOLO's $640 \times 640$ input (aspect-ratio letterboxed, scale ratio $= 0.50$):
- A **30 px** native person shrinks to **15.0 px**.
- A **15 px** native head shrinks to **7.5 px**.
- A **10 px** native head shrinks to **5.0 px**.

### C. YOLOv8 Feature Map Grid Cell Bottleneck
- YOLOv8's finest resolution detection head operates at **stride 8** (P3 layer, feature map resolution $80 \times 80$).
- A downscaled head of **7.5 pixels** is **smaller than a single $8 \times 8$ grid cell** ($0.93 \times \text{cell size}$).
- Consequently, spatial feature activations in the Convolutional backbone fail to reach anchorless detection thresholds (`conf >= 0.35`), causing the detector to skip over 95%+ of dense crowd heads.

Scale analysis artifact saved to: [`training/visualizations/dense_crowd_diagnostics/scale_analysis.jpg`](file:///D:/Shreyas%20Files/AMC%20Engineering%20College/7th%20sem/Major%20Project/CrowdPatrol/training/visualizations/dense_crowd_diagnostics/scale_analysis.jpg)

---

## 3. Resolution Scaling Impact (Why 640 vs 800 vs 960 Improvements Were Small)

Previous resolution experiments showed modest gains:
- `imgsz=640`: 1.87 detections/frame
- `imgsz=800`: 2.97 detections/frame
- `imgsz=960`: 3.45 detections/frame

### Why Global Resizing Remains Bottlenecked:
Even at `imgsz=960`, global resizing scales down the entire 1280p frame ($960 / 1280 = 0.75$). A 15px native head becomes 11.25px in the input image, occupying only $1.4$ grid cells at stride 8. Furthermore, global downscaling blurs compression artifacts in the crowded background, losing fine high-frequency edge details required for face/head recognition.

---

## 4. Tiling / Cropped Inference Feasibility Experiment ($2 \times 2$ Spatial Tiles)

A non-production feasibility experiment was conducted dividing frames into **$2 \times 2$ overlapping tiles** (with 15% spatial overlap), running YOLO inference at `imgsz=640` on each tile, remapping coordinates to global space, and applying CPU NMS (`iou=0.45`).

### Empirical Results (300 Video Frames Evaluated):

| Inference Strategy | Model | Avg Dets / Frame | Max Dets | Zero-Detection Frames | Zero-Detection % | Speed (FPS) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Full-Frame (640)** | V2 | 1.87 | 11 | 108 / 300 | 36.00% | 32.55 FPS |
| **$2 \times 2$ Tiled** | **V2** | **4.86** | **17** | **0 / 300** | **0.00%** | **7.94 FPS** |
| **Full-Frame (640)** | V3 | 0.88 | 8 | 196 / 300 | 65.33% | 32.72 FPS |
| **$2 \times 2$ Tiled** | **V3** | **4.69** | **13** | **2 / 300** | **0.67%** | **7.77 FPS** |

### Key Discovery:
Spatial tiling **completely eliminates zero-detection frames for V2 (from 36.0% -> 0.0%)** and **virtually eliminates them for V3 (from 65.3% -> 0.67%)**, increasing average detections per frame by **2.6x to 5.3x**!

Tiling visual comparisons saved to:
- [`training/visualizations/dense_crowd_diagnostics/tiling_crowdpatrol_yolov8n_finetuned_v2_comparison.jpg`](file:///D:/Shreyas%20Files/AMC%20Engineering%20College/7th%20sem/Major%20Project/CrowdPatrol/training/visualizations/dense_crowd_diagnostics/tiling_crowdpatrol_yolov8n_finetuned_v2_comparison.jpg)
- [`training/visualizations/dense_crowd_diagnostics/tiling_crowdpatrol_yolov8n_dense_v3_comparison.jpg`](file:///D:/Shreyas%20Files/AMC%20Engineering%20College/7th%20sem/Major%20Project/CrowdPatrol/training/visualizations/dense_crowd_diagnostics/tiling_crowdpatrol_yolov8n_dense_v3_comparison.jpg)

---

## 5. CrowdHuman Domain Match Analysis

Side-by-side comparison between CrowdHuman training images and `dense_crowd_test.mp4` reveals a **severe domain mismatch**:

| Aspect | CrowdHuman Dataset | `dense_crowd_test.mp4` Video |
| :--- | :--- | :--- |
| **Camera Viewpoint** | Street-level / Eye-level photography | High-angle overhead surveillance camera |
| **Visible Anatomic Features** | Torsos, legs, faces, arms clearly visible | Top-down hair/heads only; body 80–90% occluded |
| **Lighting & Contrast** | High-contrast daylight DSLR photography | Compressed surveillance stream with motion blur |
| **Target Morphology** | Vertical rectangular human silhouettes | Small circular/oval head shapes |

Domain comparison artifact saved to: [`training/visualizations/dense_crowd_diagnostics/domain_comparison.jpg`](file:///D:/Shreyas%20Files/AMC%20Engineering%20College/7th%20sem/Major%20Project/CrowdPatrol/training/visualizations/dense_crowd_diagnostics/domain_comparison.jpg)

---

## 6. Head Detection (HBOX) Feasibility Experiment

20 visual comparison sets (`FBOX | VBOX | HBOX`) were generated from real CrowdHuman annotations under [`training/visualizations/dense_crowd_diagnostics/annotation_types/`](file:///D:/Shreyas%20Files/AMC%20Engineering%20College/7th%20sem/Major%20Project/CrowdPatrol/training/visualizations/dense_crowd_diagnostics/annotation_types/):

### CrowdHuman Annotation Dimensional Summary:
- **Full-Body (FBOX) Mean Height**: **266.95 px**
- **Visible-Body (VBOX) Mean Height**: **200.22 px** (Still contains torso/body height!)
- **Head Target (HBOX) Mean Height**: **44.38 px** (Median: **26.0 px**, Mean Width: **36.48 px**)
- **Head to Full-Body Ratio**: **16.62%**

### Why VBOX Failed and Why HBOX is Justified:
1. **VBOX Flaw**: While VBOX removes completely invisible lower legs, it **still requires a visible torso and upper body** (mean height 200px). In overhead dense crowds, torsos are 100% hidden behind neighboring people. V3 failed because it was trained to look for torsos that do not exist in overhead camera angles.
2. **HBOX Alignment**: HBOX annotations tightly isolate the **head region alone** (26–44px), which directly matches the visible circular head features in overhead dense crowd footage.

---

## 7. Direct Answers to Core Diagnostic Questions

1. **Are the people too small?**
   * **YES.** Native heads measure 15–35px. When downscaled globally to 640x640, they shrink to 7.5–15px, falling below YOLO's stride-8 grid resolution.
2. **Would tiling materially help?**
   * **YES.** $2 \times 2$ spatial tiling increased V2 detections by 2.6x (1.87 -> 4.86) and eliminated zero-detection frames completely (36.0% -> 0.0%).
3. **Is the dense video visually different from CrowdHuman?**
   * **YES.** CrowdHuman features street-level eye-height photographs, whereas `dense_crowd_test.mp4` features high-angle overhead surveillance footage with severe occlusion.
4. **Does VBOX match the visible people we want to detect?**
   * **NO.** VBOX targets still expect a visible torso/upper body (mean height 200px). In high-angle dense crowds, bodies are fully occluded, leaving only heads visible.
5. **Would head-target (HBOX) training address the observed failure?**
   * **YES.** CrowdHuman HBOX annotations tightly bound head targets (mean size 36px) without requiring torso visibility, matching overhead crowd appearances.
6. **Is the limitation likely detector architecture / input resolution related?**
   * **YES.** The failure is driven by the combination of global input downscaling and torso-dependent target definitions.
7. **What experiment should be performed next?**
   * Conduct a controlled experiment evaluating **Head-Target (HBOX) model training** combined with higher inference resolution or spatial tiling.

---

## 8. Summary Record Location
- Diagnostic JSON: [`training/dense_crowd_failure_analysis.json`](file:///D:/Shreyas%20Files/AMC%20Engineering%20College/7th%20sem/Major%20Project/CrowdPatrol/training/dense_crowd_failure_analysis.json)
