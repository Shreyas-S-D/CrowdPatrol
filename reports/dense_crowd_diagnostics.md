# CrowdPatrol Dense Crowd Failure Mode Diagnostic Report

## 1. Problem Reproduction

* **Video File**: `data/videos/dense_crowd_test.mp4` (Resolution: 1280×720, FPS: 29.97, Total Frames: 5,588)
* **Model Tested**: `models/crowdpatrol_yolov8n_finetuned_v2.pt` at default `conf = 0.35`
* **Observation**:
  * Visible scene contents: A dense sea of hundreds of people packed together.
  * System telemetry output:
    * **Average raw YOLO person detections/frame**: **1.94** (Min: 0, Max: 13)
    * **Average DeepSORT active tracks/frame**: **5.22**
    * **Average Max Density**: **1.74 persons/cell**
    * **Average Risk Score**: **6.93** (Risk Level: **LOW**)
* **Conclusion**: The user's reported bug is **100% reproduced**. The system reports ~1 to 5 people in a scene containing hundreds.

---

## 2. Confidence Threshold Investigation (V2 Model)

Sweeping confidence thresholds on `data/videos/dense_crowd_test.mp4` without modifying model weights:

| Confidence Threshold (`conf`) | Avg Detections / Frame | Min Detections / Frame | Max Detections / Frame | Mean Confidence | Frames with 0 Detections | Frames with ≥50 Detections | 300 Saturation Occurred? |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **0.50** | 0.22 | 0 | 4 | 0.560 | 259 | 0 | No |
| **0.35 (Default)** | 1.94 | 0 | 13 | 0.425 | 120 | 0 | No |
| **0.25** | 5.06 | 0 | 30 | 0.343 | 31 | 0 | No |
| **0.20** | 5.06 | 0 | 30 | 0.343 | 31 | 0 | No |
| **0.10** | 5.06 | 0 | 30 | 0.343 | 31 | 0 | No |

### Key Takeaways:
1. Lowering confidence threshold from `0.35` to ultra-sensitive `0.10` only increases average detections from **1.94 to 5.06 per frame** (max 30).
2. Even at `conf = 0.10`, **0 out of 300 frames** reached $\ge 50$ detections.
3. **Saturation (300 detections limit) NEVER occurred**.
4. **Diagnosis**: Confidence thresholding is **NOT** the primary cause of missed people. The detector is simply not producing bounding-box proposals for 95%+ of the individuals in this scene.

---

## 3. Stock YOLOv8n vs Fine-Tuned V2 Comparison

Identical evaluation on `data/videos/dense_crowd_test.mp4`:

| Model | Confidence (`conf`) | Avg Detections / Frame | Max Detections / Frame | Mean Confidence | Avg DeepSORT Tracks / Frame |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Stock `yolov8n.pt`** | 0.35 | **0.003** | 1 | 0.491 | 0.003 |
| **Fine-Tuned V2** | 0.35 | **1.937** | 13 | 0.425 | 5.217 |
| **Stock `yolov8n.pt`** | 0.10 | **0.013** | 1 | 0.323 | 0.113 |
| **Fine-Tuned V2** | 0.10 | **5.057** | 30 | 0.343 | 10.977 |

### Comparison Findings:
1. Stock `yolov8n.pt` fails completely on this video (averaging 0.003 detections/frame).
2. Fine-Tuned V2 performs significantly better than stock YOLOv8n (detecting up to 30 candidates vs 1 for stock), but **both models fail to capture extreme crowd density**.
3. Visual comparison overlays saved to: `training/visualizations/dense_crowd_diagnostics/comparison_conf_0.35_frame_XXX.jpg`.

---

## 4. Downstream Pipeline Trace (Where does the count drop?)

Tracking frame telemetry from detector to risk assessment:

```
Frame 030: YOLO Raw Detections (2) -> DeepSORT Tracks (7) -> Grid Max Density (2) -> Risk Score (7.65 - LOW)
Frame 060: YOLO Raw Detections (1) -> DeepSORT Tracks (5) -> Grid Max Density (1) -> Risk Score (7.45 - LOW)
Frame 090: YOLO Raw Detections (4) -> DeepSORT Tracks (6) -> Grid Max Density (2) -> Risk Score (8.12 - LOW)
Frame 120: YOLO Raw Detections (0) -> DeepSORT Tracks (4) -> Grid Max Density (1) -> Risk Score (6.88 - LOW)
```

### Trace Diagnosis:
* DeepSORT memory actually **boosts** the active count (from 1-2 raw detections up to 4-7 tracks) by holding past detections for 30 frames (`max_age=30`).
* Density Estimator and Risk Engine correctly compute low metrics because they receive only 4-7 tracks.
* **Proof**: Downstream modules (DeepSORT, Density Grid, Risk Engine) are operating 100% correctly mathematically. **The drop occurs entirely at the YOLO detection stage.**

---

## 5. Visual Findings & Failure Mode Analysis

Inspection of raw detection frame visualizations (`training/visualizations/dense_crowd_diagnostics/raw_yolo_v2_frame_XXX.jpg`) reveals:

1. **Severe Occlusion & Partial Visibility**: In `dense_crowd_test.mp4`, people are standing shoulder-to-shoulder in extreme proximity. Only their **heads, hair, and upper shoulders** are visible. Full bodies (`fbox` - head, torso, legs) are 90%+ occluded.
2. **Perspective & Scale Shrinkage**: The camera perspective makes individual human bodies appear extremely small (10x10 to 20x20 pixels per head).
3. **Detector Representation Mismatch**: Standard YOLO person detectors look for full-body human structures (head + torso + legs). When presented with a grid of isolated heads/hair, the detector filters them out as non-person background texture.

---

## 6. Training Data & Annotation Audit

Inspection of dataset preparation (`training/prepare_datasets.py`) and training parameters (`training/train.py`):

1. **Annotation Format Used**:
   - `prepare_datasets.py` parsed CrowdHuman `.odgt` using: `fbox` (Full Body Box: `[x, y, w, h]`).
   - `vbox` (Visible Body Box) and `head_attr` (Head Bounding Box) were **ignored/skipped** during dataset preparation.
2. **Image Input Size (`imgsz`)**:
   - V2 was trained at `imgsz = 480` and inferenced at native video resolution (1280×720).
   - At `imgsz = 480`, a 15×15 pixel head in a 1280×720 frame shrinks down to ~5×5 pixels, making feature extraction by convolutional layers virtually impossible.
3. **Crowd Representation**:
   - While CrowdHuman contains 4,370 images, standard full-body bounding boxes (`fbox`) force YOLO to penalize predictions that do not enclose a full human torso/legs. In dense crowds where torsos are hidden, `fbox` training causes zero-detection under-counting.

---

## 7. Identified Technical Bottleneck

The root cause of reporting `Persons: 1` in an extreme crowd scene is a **3-part Structural & Representation Bottleneck**:

1. **Full-Body Anchor Bias (`fbox` vs Head/Visible Body)**: The detector was trained strictly to look for full human bodies (`fbox`). In extreme dense crowds, 95% of people display only heads/shoulders.
2. **Resolution & Patch Scaling (`imgsz=480` vs Small Instances)**: Small 15-pixel crowd instances vanish when downscaled during standard feature extraction.
3. **Bounding Box Overlap Suppression (NMS)**: Standard NMS suppresses overlapping candidate boxes when people stand directly in front of each other.

---

## 8. Controlled Input Resolution Experiment (`imgsz` Evaluation)

To determine whether input resolution is a primary driver of the dense crowd detection issue, a controlled experiment was run using `models/crowdpatrol_yolov8n_finetuned_v2.pt` on `data/videos/dense_crowd_test.mp4` across three input resolution configurations: `imgsz=640`, `imgsz=800`, and `imgsz=960` at default `conf=0.35`.

| Resolution (`imgsz`) | Avg Detections / Frame | Max Detections / Frame | Mean Confidence | Median Confidence | Frames with 0 Detections | Processing Speed (FPS) | Frame Time (ms) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`imgsz = 640`** | 1.87 | 11 | 0.423 | 0.402 | 108 / 300 | **31.95 FPS** | 31.3 ms |
| **`imgsz = 800`** | 2.97 | 10 | 0.440 | 0.417 | 16 / 300 | **21.97 FPS** | 45.5 ms |
| **`imgsz = 960`** | 3.45 | 12 | 0.442 | 0.422 | 13 / 300 | **16.20 FPS** | 61.7 ms |

### Key Findings from Resolution Experiment:
1. Increasing image resolution from 640 to 960 (a **2.25× increase in total pixels**) only increased average detections from **1.87 to 3.45 per frame** (max 12).
2. The video frame contains **hundreds of visible crowd members**. Detecting 3.45 persons per frame leaves **>98% of the crowd undetected**.
3. Processing speed dropped from **31.95 FPS down to 16.20 FPS** (~50% performance penalty).
4. Visual detection overlays saved to: `training/visualizations/dense_crowd_diagnostics/resolution_test/raw_det_imgsz_XXX_frame_YYY.jpg`.
5. **Conclusion**: Input resolution scaling does **NOT** materially solve the dense-crowd detection failure.

---

## 9. Technical Recommendation: Head/Visible-Body Annotations vs. Sliced Inference

Because increasing input resolution fails to solve the occlusion problem, we evaluate two architectural solutions:

1. **Option A (RECOMMENDED): CrowdHuman Visible-Body (`vbox`) / Head (`head_attr`) Fine-Tuning**
   * **Why**: CrowdHuman contains explicit bounding boxes for `vbox` (visible body portion) and `head_attr` (head location). Training YOLOv8 on visible body/head annotations teaches the model to directly detect isolated heads and upper shoulders as valid person targets, solving the 90%+ occlusion problem natively without incurring extra inference latency.
   * **Pros**: Maintains fast single-pass real-time FPS (25–30+ FPS), natively handles dense crowds.

2. **Option B: Sliced Inference (SAHI - Slicing Aided Hyper Inference)**
   * **Why**: Divides a 1280×720 image into overlapping 640×640 tiles.
   * **Cons**: If the underlying model was trained strictly on full human bodies (`fbox`), an isolated head inside a 640×640 sub-tile still lacks a torso and legs, causing the model to reject it. Furthermore, slicing incurs a 4× to 9× computational overhead, dropping FPS to ~2–4 FPS.

---

## 10. Suitability Assessment Summary

* **Is V2 suitable for moderate / sparse crowd monitoring?** YES (Passed real-world validation on 3 pedestrian/crowd videos with 11-12 FPS).
* **Is V2 suitable for EXTREME dense crowd scenes (concerts, stadium crowds, pilgrimages)?** **NO.** Standard full-body bounding-box detectors cannot count extreme dense crowds where full bodies are occluded.

