# CrowdPatrol Stage 4 Controlled Evaluation: V2 vs. V3 Model Benchmark

## Executive Summary

A controlled empirical evaluation was conducted on branch `v3-dense-crowd` comparing:
- **V2 Baseline Model**: [`models/crowdpatrol_yolov8n_finetuned_v2.pt`](file:///D:/Shreyas%20Files/AMC%20Engineering%20College/7th%20sem/Major%20Project/CrowdPatrol/models/crowdpatrol_yolov8n_finetuned_v2.pt) (Trained on CrowdHuman FBOX full-body targets)
- **V3 Candidate Model**: [`models/crowdpatrol_yolov8n_dense_v3.pt`](file:///D:/Shreyas%20Files/AMC%20Engineering%20College/7th%20sem/Major%20Project/CrowdPatrol/models/crowdpatrol_yolov8n_dense_v3.pt) (Trained on CrowdHuman VBOX visible-body targets)

Both models were evaluated under identical inference parameters (`conf=0.35`, `imgsz=640`, device=`cpu`) across 5 real crowd videos totaling **1,500 video frames**.

---

## 1. Evaluation Goal
The objective was to determine whether V3's VBOX training strategy (tight visible-body target bounding boxes) successfully resolves the dense-crowd detection drop observed on [`data/videos/dense_crowd_test.mp4`](file:///D:/Shreyas%20Files/AMC%20Engineering%20College/7th%20sem/Major%20Project/CrowdPatrol/data/videos/dense_crowd_test.mp4) without degrading performance on normal crowd scenes.

---

## 2. Raw YOLO Detector Performance (Without DeepSORT)

### A. Primary Dense Crowd Test Video ([`dense_crowd_test.mp4`](file:///D:/Shreyas%20Files/AMC%20Engineering%20College/7th%20sem/Major%20Project/CrowdPatrol/data/videos/dense_crowd_test.mp4)) — 300 Frames

| Metric | V2 (FBOX Baseline) | V3 (VBOX Dense) | Delta ($\Delta$) & Status |
| :--- | :---: | :---: | :--- |
| **Average Detections / Frame** | **1.87** | **0.88** | **-52.9%** (Detections decreased) |
| **Median Detections / Frame** | **1.0** | **0.0** | Drop to zero median |
| **Maximum Detections (Single Frame)** | **11** | **8** | Lower peak detection count |
| **Minimum Detections (Single Frame)** | 0 | 0 | Both drop to 0 on distant frames |
| **Zero-Detection Frames** | **108 / 300** | **196 / 300** | **+88 more zero-detection frames** |
| **Zero-Detection Frame Percentage** | **36.00%** | **65.33%** | **+29.33% higher drop rate** |
| **Average Confidence** | 0.4229 | 0.4364 | +0.0135 (Slightly higher conf thresholding) |
| **Median Confidence** | 0.4018 | 0.4115 | Similar confidence profile |
| **Average Detector Speed** | **29.21 FPS** | **32.75 FPS** | +3.54 FPS (Faster due to fewer boxes) |

---

## 3. Dense Crowd Video Deep Dive Analysis

Empirical evaluation on [`dense_crowd_test.mp4`](file:///D:/Shreyas%20Files/AMC%20Engineering%20College/7th%20sem/Major%20Project/CrowdPatrol/data/videos/dense_crowd_test.mp4) reveals:
1. **Detection Count**: V3 does **NOT** detect substantially more people. In fact, it detects fewer than half the people detected by V2 (0.88 vs 1.87 detections/frame).
2. **Inner/Occluded Coverage**: V3 fails to detect inner or heavily occluded crowd members in this video. Over **65.33% of video frames** produced exactly **0 detections** under V3.
3. **Detection Concentration**: Detections remain sparse and are restricted only to isolated, high-contrast individuals near foreground edges.
4. **False Positives**: Neither model produced background hallucinations (0 false positives on buildings/structures).
5. **Detection Saturation / Ceiling**: Neither model approached the 300 detection ceiling.
6. **Duplicate Detections**: Zero duplicate bounding boxes were produced.

---

## 4. Visual Inspection Artifacts (Matched Frames)

10 side-by-side comparison images (`V2 | V3`) were generated under [`training/visualizations/v2_vs_v3_dense/`](file:///D:/Shreyas%20Files/AMC%20Engineering%20College/7th%20sem/Major%20Project/CrowdPatrol/training/visualizations/v2_vs_v3_dense/):
- `dense_frame_016_comparison.jpg`
- `dense_frame_031_comparison.jpg`
- `dense_frame_061_comparison.jpg`
- `dense_frame_091_comparison.jpg`
- `dense_frame_121_comparison.jpg`
- `dense_frame_151_comparison.jpg`
- `dense_frame_181_comparison.jpg`
- `dense_frame_211_comparison.jpg`
- `dense_frame_241_comparison.jpg`
- `dense_frame_271_comparison.jpg`

### Visual Findings:
* Across all 10 matched frame samples, V3 bounding boxes wrap tightly around visible heads/upper bodies when detected, but fails to trigger on the vast majority of small, low-resolution heads in the dense crowd.
* Because V3 was trained at `imgsz=480` on CrowdHuman VBOX targets, when executed at `imgsz=640` on low-resolution, high-density video frames, the feature map resolution is insufficient to trigger confidence above `0.35` for tiny occluded heads.

---

## 5. Normal Crowd Regression Test (4 Real Videos — 1,200 Frames)

To verify whether V3 maintains detection performance on standard crowd density, 4 real crowd videos were benchmarked:

| Video Name | V2 Avg Dets/Frame | V3 Avg Dets/Frame | V2 Zero % | V3 Zero % | Status |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **[`youtube_crowd_test.mp4`](file:///D:/Shreyas%20Files/AMC%20Engineering%20College/7th%20sem/Major%20Project/CrowdPatrol/data/videos/youtube_crowd_test.mp4)** | **12.83** | **13.22** | **0.0%** | **0.0%** | Parity (+0.39) |
| **[`real_crowd_video_1.mp4`](file:///D:/Shreyas%20Files/AMC%20Engineering%20College/7th%20sem/Major%20Project/CrowdPatrol/data/videos/real_crowd_video_1.mp4)** | **12.72** | **12.99** | **0.0%** | **0.0%** | Parity (+0.27) |
| **[`real_crowd_video_2.mp4`](file:///D:/Shreyas%20Files/AMC%20Engineering%20College/7th%20sem/Major%20Project/CrowdPatrol/data/videos/real_crowd_video_2.mp4)** | **13.51** | **13.77** | **0.0%** | **0.0%** | Parity (+0.26) |
| **[`real_crowd_video_3.mp4`](file:///D:/Shreyas%20Files/AMC%20Engineering%20College/7th%20sem/Major%20Project/CrowdPatrol/data/videos/real_crowd_video_3.mp4)** | **11.90** | **12.43** | **0.0%** | **0.0%** | Parity (+0.53) |

### Regression Conclusion:
V3 performs at **full parity with V2 on standard crowd scenes** (~12.5–13.5 detections/frame, 0.0% zero-detection rate, 0 false positives). It does not degrade normal crowd detection, but it does not solve dense crowd detection either.

---

## 6. DeepSORT Tracking Performance

| Video & Setup | V2 Avg Tracks | V2 Max Tracks | V3 Avg Tracks | V3 Max Tracks | Tracker FPS (V2 vs V3) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Dense Crowd (`dense_crowd_test.mp4`)** | **5.22** | **29** | **1.12** | **14** | 17.7 FPS vs 35.2 FPS |
| **Normal Crowd (`youtube_crowd_test.mp4`)** | **18.84** | **25** | **19.16** | **26** | 4.19 FPS vs 4.22 FPS |

* DeepSORT tracking stability remains clean and free of false track explosions for both models.
* On dense crowds, V3's lower detection count directly reduces DeepSORT track initiation (1.12 active tracks/frame vs V2's 5.22).

---

## 7. Full Pipeline Performance (YOLO -> DeepSORT -> 4x4 Grid -> Risk Engine)

| Video & Pipeline | V2 Dets/Fr | V2 Tracks/Fr | V2 Max Grid | V2 Risk Score | V3 Dets/Fr | V3 Tracks/Fr | V3 Max Grid | V3 Risk Score | Pipeline FPS |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Dense Crowd** | 1.94 | 5.22 | 9 | 6.88 | 0.39 | 1.12 | 4 | 3.55 | 14.0 vs 23.3 |
| **Normal Crowd** | 11.73 | 18.84 | 9 | 26.06 | 11.85 | 19.16 | 9 | 25.64 | 3.9 vs 3.9 |

---

## 8. Quantitative Comparison Summary Table

```
                V2              V3
------------------------------------------------
Dense detections/frame     1.87            0.88
Dense max detections       11              8
Dense zero-detection %     36.00%          65.33%
Dense avg confidence       0.4229          0.4364
Dense detector FPS         29.21 FPS       32.75 FPS
Normal detections/frame    12.83           13.22
Normal max detections      19              18
Normal zero-detection %    0.00%           0.00%
Normal avg confidence      0.7249          0.7340
Normal detector FPS        32.51 FPS       32.76 FPS
DeepSORT tracks/frame      18.84           19.16
Full pipeline FPS          3.92 FPS        3.93 FPS
```

---

## 9. Final Classification

Based strictly on empirical measurements and visual inspection evidence, the result of this controlled experiment is classified as:

### **C. V3 does not meaningfully improve dense-crowd detection.**

---

## 10. Summary & Next Steps
- V3 (Visible-Body target training) did not resolve the dense-crowd detection issue on `dense_crowd_test.mp4`.
- On standard crowd scenes, V3 and V2 perform at parity.
- **Model Isolation Maintained**: `models/crowdpatrol_yolov8n_finetuned_v2.pt` remains the default production model in code, and `stable-v2` remains clean.
