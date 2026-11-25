# CrowdPatrol Empirical Research Evaluation Report
**Target Publication / Academic Scope**: IEEE Major Project & Research Paper Extraction  
**Date of Measurement**: 2026-11-25  
**Evaluation Harness**: `paper_eval/benchmark.py`  
**Host Machine**: Intel(R) Core(TM) i7-13700H (14 physical cores, 20 logical threads, 15.73 GB RAM, Windows 11 AMD64, PyTorch CPU mode)

---

## PART A: Architectural Parameters Read from Code and Configuration

| Parameter Category | Field | Exact Value | Source File & Line Number | Notes / Mechanism |
|---|---|---|---|---|
| **1. Detector** | Default Model Weights File | `models/crowdpatrol_yolov8n_finetuned_v2.pt` (fallback: `yolov8n.pt`) | `src/detection.py:7` | Evaluated on real CrowdHuman dataset (`fbox` full-body bounding boxes). |
| | Head Mode Model Weights File | `models/crowdpatrol_yolov8n_head_v4.pt` | `src/experimental_head_mode.py:8` | Specialized micro-head detector for high-density crowds. |
| | Input Resolution (`imgsz`) | `640` | `src/detection.py:10` | Passed as `imgsz=self.imgsz` to YOLO forward pass (`src/detection.py:27`). |
| | Confidence Threshold (Person) | `0.35` | `src/detection.py:10` | Filtered at `float(box.conf) >= self.confidence` (`src/detection.py:31`). |
| | Confidence Threshold (Head) | `0.25` | `src/experimental_head_mode.py:10` | Optimized for occluded micro-heads. |
| | IoU Threshold (NMS) | `0.70` (default Ultralytics NMS IoU) / `0.50` (Tiled Head Mode) | `src/detection.py:27` & `src/experimental_head_mode.py:46` | Non-maximum suppression overlap threshold. |
| | Class Filter | `[0]` (COCO Person Class) | `src/detection.py:17` | Filtered via `int(box.cls) in self.class_ids` (`src/detection.py:31`). |
| **2. Tracker (DeepSORT)** | `max_age` | `30` | `src/tracking.py:65` | Maximum consecutive missed frames before track deletion. |
| | `n_init` | `1` | `src/tracking.py:65` | Consecutive detections required to confirm track state. |
| | `max_iou_distance` | `0.7` | `deep_sort_realtime.deepsort_tracker:DeepSort` default | Spatial bounding box association gate. |
| | `max_cosine_distance` | `0.2` | `deep_sort_realtime.deepsort_tracker:DeepSort` default | Re-identification cosine distance matching threshold. |
| | Embedder Model | `'mobilenet'` (MobileNetV2) | `deep_sort_realtime.deepsort_tracker:DeepSort` default & `src/tracking.py:10` | 224x224 input image crops; patched with batched tensor PyTorch inference. |
| | Execution Device | `CPU` | `src/tracking.py:30` | Intel CPU with `torch.channels_last` memory format and 14-core thread pinning. |
| **3. Frame Skipping** | Variable Name | `detect_interval` | `dashboard/simple_dashboard.py:360`, `:528`, `:843` | Parameter controlling detection cadence. |
| | Default Value | `3` (frames) | `dashboard/simple_dashboard.py:360` | Runs YOLO + DeepSORT embedder on frame $F$ where $(F \pmod 3 == 0)$. |
| | Action on Skipped Frames | `tracker.predict()` | `dashboard/simple_dashboard.py:1093`, `:1166` | Advances Kalman filter state (`PersonTracker.predict()`); skips CNN inference. |
| **4. Density Estimation** | Spatial Grid Rows × Columns | `4 × 4` (16 equal spatial cells) | `src/density.py:5` | Normalized grid overlay across camera viewport. |
| | Cell Assignment Logic | Centroid coordinates: `cx = (x1 + x2) / 2`, `cy = (y1 + y2) / 2`; cell indices: `grid_y = int(cy // cell_h)`, `grid_x = int(cx // cell_w)` | `src/density.py:17-22` | Each person increments the cell counter `density_map[grid_y, grid_x] += 1`. |
| **5. Optical Flow** | Farneback Parameters | `pyr_scale=0.5, levels=3, winsize=15, iterations=3, poly_n=5, poly_sigma=1.2, flags=0` | `src/motion_analysis.py:61-69` | Gunnar Farneback dense motion field algorithm. |
| | Processing Resolution | `320 × 180` (grayscale) | `src/motion_analysis.py:44` | Downscaled for high-speed CPU optical flow calculation. |
| | Camera-Motion Exclusion Logic | Spatial median vector: `bg_vx = np.median(flow_x)`, `bg_vy = np.median(flow_y)`. Threshold: `np.sqrt(bg_vx**2 + bg_vy**2) > 1.5` px/frame | `src/motion_analysis.py:155-159` | When detected, background velocity is subtracted from pixel flow vectors. |
| **6. Risk Assessment Engine** | Default Weights | `density: 0.35, density_growth: 0.15, motion_speed: 0.15, flow_conflict: 0.15, accel_spikes: 0.10, local_anomaly: 0.10` | `src/risk_assessment.py:85-92` | Multi-factor normalized weighting matrix. |
| | Metric Normalization Caps | `density_cap: 30.0, density_growth_cap: 10.0, motion_speed_cap: 3.0, local_anomaly_cap: 3.0, accel_spike_cap: 4.0` | `src/risk_assessment.py:94-100` | Scurves/clipping boundaries for multi-factor scores. |
| | Exponential Moving Average (EMA) $\alpha$ | `0.25` | `src/risk_assessment.py:108` | Temporal risk smoothing factor ($\text{score}_t = \alpha \cdot \text{raw} + (1-\alpha) \cdot \text{score}_{t-1}$). |
| | Hysteresis Enter / Exit Thresholds | Low $\rightarrow$ Medium: $\ge 40.0$; Medium $\rightarrow$ Low: $< 35.0$; Medium $\rightarrow$ High: $\ge 70.0$; High $\rightarrow$ Medium: $< 65.0$; Direct Low $\rightarrow$ High: $\ge 70.0$; Direct High $\rightarrow$ Low: $< 35.0$ | `src/risk_assessment.py:48-76` | Explicit 5.0-point deadband preventing alert flickering. |
| **7. Firebase RTDB Fields** | Telemetry Fields Written per Frame (16 primary + 3 aliases = 19 fields) | `person_count`, `max_density`, `risk_level`, `combined_score`, `raw_score`, `smoothed_score`, `growth_rate`, `data_quality_score`, `avg_speed`, `max_speed`, `dominant_direction`, `camera_motion_detected`, `sudden_movement_count`, `anomaly_score`, `fps`, `last_frame_time`, plus aliases `density`, `risk`, `anomaly` | `src/alerts.py:438-463` & `dashboard/dashboard_utils.py:10-50` | Synchronous RTDB push via `db.reference('dashboard').set(...)`. |

---

## PART B: Historical Empirical Results Already Saved in Repository

All values below are transcribed verbatim from repository evaluation reports and historical benchmark logs:

### 1. Model Training & Accuracy Metrics (CrowdHuman Test Benchmark)
- **Source**: `reports/training_results.md:65-100` (Evaluated on 656 held-out authentic crowd images, 14,725 ground-truth person annotations):
  - **Stock Pretrained Baseline (`yolov8n.pt`)**:
    - Precision: `0.5908`
    - Recall: `0.4037`
    - mAP@50: `0.4115`
    - mAP@50-95: `0.1735`
    - Detector Speed: `29.9 ms/image` (33.5 FPS)
  - **Fine-Tuned V2 Model (`models/crowdpatrol_yolov8n_finetuned_v2.pt`)**:
    - Precision: `0.6803` (+8.95% over baseline)
    - Recall: `0.4695` (+6.58% over baseline)
    - mAP@50: `0.5421` (+13.06% over baseline)
    - mAP@50-95: `0.2634` (+8.99% over baseline)
    - Detector Speed: `17.7 ms/image` (56.4 FPS)
  - **Initial Fine-Tuned Model V1 (Synthetic Data - Flagged Invalid)**:
    - mAP@50 on synthetic shapes: `0.9027` (`reports/training_results.md:10`)
    - Raw Detections on real video: `300 detections/frame` (Hit YOLO maximum detection ceiling cap; severe false-positive hallucination on building facades, `reports/training_results.md:30-40`).
- **Dense-Crowd V3 Model (VBOX Visible Body Annotations)**:
  - **Source**: `reports/v3_training_results.md:50-58`:
    - Precision: `0.6581`
    - Recall: `0.4639`
    - mAP@50: `0.5312`
    - mAP@50-95: `0.2842`
    - Training Duration: `750.90 seconds (12.51 minutes)` on 3 epochs (`reports/v3_training_results.md:44`).
- **Head Detector Model V4 (`models/crowdpatrol_yolov8n_head_v4.pt`)**:
  - **Source**: `reports/v4_forensic_accuracy_audit.md:40-75`:
    - Mean Raw Head Detections/Frame: `13.52`
    - Mean Active DeepSORT Retained Tracks: `60.0`
    - Mean Max Cell Density: `11.46 heads/cell` (peak `26 heads/cell`)
    - Ground-Truth Box Annotations on test video: `NOT FOUND` (`reports/v4_forensic_accuracy_audit.md:144`).

### 2. Historical Component Profiling & Latency Records
- **Source**: `PHASE_5_FINAL_VALIDATION_REPORT.md:120-126` (Intel Core i7-13700H, CPU execution):
  - YOLOv8 Detection Forward Pass: `27.25 ms (36.70 FPS)` (Person Mode) vs `47.89 ms (20.88 FPS)` (Head Mode)
  - DeepSORT Appearance Tracking: `6.42 ms` (Person Mode) vs `214.78 ms` (Head Mode, sequential MobileNetV2 embedding extraction on CPU for 25–40 heads)
  - Farneback Optical Flow: `10.12 ms` (Person Mode) vs `13.23 ms` (Head Mode)
  - Density & Risk Calculation: `0.08 ms` (Person Mode) vs `0.15 ms` (Head Mode)
  - Total Single-Frame Latency: `43.87 ms` (Person Mode) vs `276.05 ms` (Head Mode)
  - Raw YOLO Inference FPS: `36.70 FPS` (Person Mode) vs `20.88 FPS` (Head Mode)
  - Full Pipeline Throughput: `22.79 Pipeline FPS` (Person Mode) vs `3.62 Pipeline FPS` (Head Mode)
- **Source**: `reports/fps_profiling_phase1.md:20-60` (Detailed sub-stage profiling):
  - Video Frame Capture: `40.93 ms avg` (median: `23.24 ms`, max: `362.11 ms`)
  - Frame Preprocessing: `1.26 ms avg` (median: `0.00 ms`, max: `5.07 ms`)
  - YOLO Inference: `47.60 ms avg` (`139.99 ms` on detection frames, max: `385.45 ms`)
  - DeepSORT Tracker Update: `248.53 ms avg` (max: `1271.70 ms`)
  - DeepSORT Embedding Extraction: `314.74 ms avg` (`925.71 ms` on detection frames, max: `1416.04 ms`)
  - Kalman Prediction on Skipped Frames: `0.0081 ms avg` (< 0.01 ms)
  - Density Grid Calculation: `0.17 ms avg` (median: `0.18 ms`)
  - Optical Flow Total: `95.38 ms avg` (Farneback: `43.60 ms`, Vector summary: `49.13 ms`)
  - OpenCV Visualization Overlays: `12.78 ms avg`
  - JPEG Compression: `4.38 ms avg`
  - Local CSV Logging: `1.18 ms avg`
  - Firebase Network REST Write Latency: `~198.0 ms avg` per synchronous call
  - Average Detections per Frame: `10.56 persons/frame`
  - Average Active Tracks per Frame: `14.79 confirmed tracks/frame`

---

## PART C: Measured Empirical Benchmark Results (`paper_eval/benchmark.py`)

**Test Video Specification**:
- **File Name**: `youtube_crowd_test.mp4`
- **File Path**: `data/videos/youtube_crowd_test.mp4`
- **Resolution**: `1280 × 720` (720p HD)
- **Source FPS**: `29.97 FPS`
- **Total Frame Count**: `3,493 frames`
- **Sample Range**: 330 frames processed per run; first 30 frames discarded as warmup (300 steady-state frames measured).

**Benchmark Environment**:
- Python: `3.14.6`
- OpenCV: `5.0.0`
- PyTorch: `2.14.0+cpu`
- Ultralytics: `8.4.152`
- DeepSORT (`deep_sort_realtime`): `1.3.2`
- Host CPU: Intel Core i7-13700H (14 cores / 20 threads)
- System RAM: `15.73 GB`
- Hardware Acceleration / GPU: `None (CPU Execution)`

---

### 1. Full Pipeline Benchmark: Frame Skipping ON (`detect_interval=3`)
*YOLOv8n-V2 + MobileNetV2 DeepSORT + 4x4 Density + 320x180 Farneback Flow + Multi-Factor Risk Engine*

| Metric / Stage | Mean | Median | Standard Deviation ($\sigma$) | Minimum | Maximum |
|---|---|---|---|---|---|
| **Pipeline Throughput (FPS)** | **43.43 FPS** | **49.35 FPS** | **29.87** | 4.74 FPS | 95.77 FPS |
| **Total Frame Latency (ms)** | **60.56 ms** | **20.26 ms** | **61.54 ms** | 10.44 ms | 210.76 ms |
| - Video Decode & Resize | 7.84 ms | 5.91 ms | 8.69 ms | 1.58 ms | 55.91 ms |
| - YOLOv8n Detection | 10.03 ms | 0.008 ms | 14.48 ms | 0.0003 ms | 51.27 ms |
| - DeepSORT Tracking | 31.74 ms | 0.005 ms | 46.39 ms | 0.0018 ms | 157.91 ms |
| - Spatial Density Grid | 0.065 ms | 0.062 ms | 0.027 ms | 0.023 ms | 0.199 ms |
| - Farneback Optical Flow | 10.70 ms | 10.08 ms | 1.90 ms | 8.68 ms | 24.51 ms |
| - Risk + EMA + Hysteresis | 0.174 ms | 0.160 ms | 0.054 ms | 0.097 ms | 0.477 ms |
| - Firebase Write | *SKIPPED* | *SKIPPED* | *SKIPPED* | *SKIPPED* | *SKIPPED* |
| **Detections per Detect Frame** | **13.25 persons** | 13.0 persons | 2.13 | 9.0 persons | 19.0 persons |
| **Active Tracked Persons / Frame** | **27.06 persons** | 28.0 persons | 5.01 | 14.0 persons | 34.0 persons |
| **Max Tracked Persons in any Frame**| **34 persons** | — | — | — | — |

*Note on Firebase Write: Skipped in automated CLI benchmark to avoid non-authenticated network timeouts. Measured historical latency from repo is 198.0 ms (sync REST).*

---

### 2. Full Pipeline Benchmark: Frame Skipping OFF (`detect_interval=1`)
*Every single frame subjected to YOLOv8n forward pass and MobileNetV2 DeepSORT embedding extraction*

| Metric / Stage | Mean | Median | Standard Deviation ($\sigma$) | Minimum | Maximum |
|---|---|---|---|---|---|
| **Pipeline Throughput (FPS)** | **5.93 FPS** | **5.70 FPS** | **1.18** | 3.04 FPS | 9.97 FPS |
| **Total Frame Latency (ms)** | **175.08 ms** | **175.50 ms** | **33.26 ms** | 100.29 ms | 329.27 ms |
| - Video Decode & Resize | 8.89 ms | 6.92 ms | 10.01 ms | 1.84 ms | 64.03 ms |
| - YOLOv8n Detection | 32.78 ms | 32.12 ms | 4.66 ms | 25.22 ms | 60.26 ms |
| - DeepSORT Tracking | 120.24 ms | 122.40 ms | 28.47 ms | 56.72 ms | 215.40 ms |
| - Spatial Density Grid | 0.044 ms | 0.043 ms | 0.008 ms | 0.027 ms | 0.081 ms |
| - Farneback Optical Flow | 12.92 ms | 12.72 ms | 1.06 ms | 9.36 ms | 17.99 ms |
| - Risk + EMA + Hysteresis | 0.188 ms | 0.182 ms | 0.034 ms | 0.106 ms | 0.338 ms |
| **Detections per Frame** | **13.23 persons** | 13.0 persons | 2.13 | 8.0 persons | 19.0 persons |
| **Active Tracked Persons / Frame** | **22.09 persons** | 23.0 persons | 3.11 | 15.0 persons | 29.0 persons |
| **Max Tracked Persons in any Frame**| **29 persons** | — | — | — | — |

---

### 3. Key Empirical Comparisons from Measurements

#### A. Frame Skipping Acceleration Impact
$$\text{Speedup} = \frac{43.43 \text{ FPS (Skipping ON)}}{5.93 \text{ FPS (Skipping OFF)}} = \mathbf{7.32\times \text{ Throughput Acceleration}}$$
- **DeepSORT Tracker Latency Reduction**: Drops from **120.24 ms/frame** (continuous CNN feature extraction) to **31.74 ms/frame average** (Kalman prediction cost on skipped frames: `< 0.01 ms`).
- **YOLOv8 Detection Latency Reduction**: Drops from **32.78 ms/frame** to **10.03 ms/frame average**.

#### B. Dense Optical Flow Downscaling Impact (Same 300 Frames)
- **Full Resolution ($1280 \times 720$ Farneback)**: Mean latency = **327.88 ms** (median = 156.16 ms, $\sigma = 235.85\text{ ms}$).
- **Reduced Resolution ($320 \times 180$ Farneback)**: Mean latency = **19.06 ms** (median = 9.14 ms, $\sigma = 13.98\text{ ms}$).
$$\text{Optical Flow Speedup} = \frac{327.88 \text{ ms}}{19.06 \text{ ms}} = \mathbf{17.20\times \text{ Execution Speedup}}$$

---

## PART D: Comprehensive Research Metrics Summary Table

| Metric | Measured Value | Source | Methodological Notes |
|---|---|---|---|
| **YOLOv8 Input Resolution** | $640 \times 640$ | `src/detection.py:10` | Default parameter `imgsz=640`. |
| **YOLOv8 Confidence Threshold (Person)** | `0.35` | `src/detection.py:10` | Hard filter threshold in `detect()`. |
| **YOLOv8 Confidence Threshold (Head)** | `0.25` | `src/experimental_head_mode.py:10` | Micro-head threshold. |
| **YOLOv8 NMS IoU Threshold** | `0.70` (Person) / `0.50` (Head) | `src/detection.py:27`, `src/experimental_head_mode.py:46` | Non-maximum suppression overlap limit. |
| **DeepSORT Maximum Track Age** | `30` frames | `src/tracking.py:65` | Consecutive missed frames before track disposal. |
| **DeepSORT Confirmation Hits ($n_{\text{init}}$)** | `1` hit | `src/tracking.py:65` | Number of detections to confirm active track. |
| **DeepSORT Max Cosine Distance** | `0.20` | `deep_sort_realtime:DeepSort` | Re-identification cosine distance gating limit. |
| **DeepSORT Max IoU Distance** | `0.70` | `deep_sort_realtime:DeepSort` | Bounding box spatial assignment gate. |
| **DeepSORT Embedder Architecture** | `MobileNetV2` (224×224) | `src/tracking.py:10` | PyTorch channels-last CPU memory format. |
| **Execution Hardware Device** | `Intel Core i7-13700H CPU` | `paper_eval/benchmark.py` | 14 cores, 20 threads; GPU not used. |
| **Frame Skipping Cadence** | `3` frames | `dashboard/simple_dashboard.py:360` | Detection interval default slider value. |
| **Spatial Density Grid Configuration** | $4 \times 4$ (16 cells) | `src/density.py:5` | Spatial cells across camera viewport. |
| **Dense Farneback Optical Flow Scale** | $320 \times 180$ grayscale | `src/motion_analysis.py:44` | Downscale factor = $4\times$ width, $4\times$ height. |
| **Camera Motion Threshold** | `1.5` px/frame | `src/motion_analysis.py:159` | Spatial median vector magnitude threshold. |
| **Risk Scoring Factor Weights** | 0.35 (density), 0.15 (growth), 0.15 (speed), 0.15 (flow conflict), 0.10 (accel), 0.10 (anomaly) | `src/risk_assessment.py:85-92` | Multi-factor normalized weighting array. |
| **Risk EMA Smoothing Factor ($\alpha$)** | `0.25` | `src/risk_assessment.py:108` | Temporal exponential smoothing constant. |
| **Hysteresis Deadband (Low/Med & Med/High)** | `5.0` points (35–40 & 65–70) | `src/risk_assessment.py:48-76` | Anti-flickering state transition deadband. |
| **Firebase Telemetry Snapshot Fields** | 19 keys (16 primary + 3 aliases) | `src/alerts.py:438-463` | Real-time cloud RTDB synchronized payload. |
| **Fine-Tuned V2 Model Precision** | `0.6803` (68.03%) | `reports/training_results.md:70` | Evaluated on 656 held-out CrowdHuman images. |
| **Fine-Tuned V2 Model Recall** | `0.4695` (46.95%) | `reports/training_results.md:71` | +6.58% improvement over COCO baseline. |
| **Fine-Tuned V2 Model mAP@50** | `0.5421` (54.21%) | `reports/training_results.md:72` | +13.06% improvement over COCO baseline. |
| **Fine-Tuned V2 Model mAP@50-95** | `0.2634` (26.34%) | `reports/training_results.md:73` | Net mAP improvement across IoU sweeps. |
| **Pretrained Baseline mAP@50 (`yolov8n.pt`)** | `0.4115` (41.15%) | `reports/training_results.md:72` | Baseline on identical CrowdHuman test split. |
| **Synthetic Model V1 mAP@50 (Flagged)** | `0.9027` (Invalid) | `reports/training_results.md:10` | Overfitted to synthetic rectangles; discarded. |
| **Pipeline FPS (Frame Skipping ON)** | `43.43` $\pm$ `29.87` FPS | Benchmark Run (`paper_eval/benchmark.py`) | Measured on `youtube_crowd_test.mp4` (300 frames). |
| **Pipeline Latency (Frame Skipping ON)** | `60.56` $\pm$ `61.54` ms | Benchmark Run (`paper_eval/benchmark.py`) | Mean frame processing time. |
| **Pipeline FPS (Frame Skipping OFF)** | `5.93` $\pm$ `1.18` FPS | Benchmark Run (`paper_eval/benchmark.py`) | Every frame processed with YOLO+DeepSORT. |
| **Pipeline Latency (Frame Skipping OFF)** | `175.08` $\pm$ `33.26` ms | Benchmark Run (`paper_eval/benchmark.py`) | Mean frame processing time without skipping. |
| **YOLOv8n Inference Time per Detect Frame** | `32.78` $\pm$ `4.66` ms | Benchmark Run (`paper_eval/benchmark.py`) | PyTorch CPU forward pass rate. |
| **DeepSORT Tracking Time (Detect Frame)** | `120.24` $\pm$ `28.47` ms | Benchmark Run (`paper_eval/benchmark.py`) | MobileNetV2 embedding extraction + matching. |
| **DeepSORT Tracking Time (Skipped Frame)** | `0.005` ms (Median) | Benchmark Run (`paper_eval/benchmark.py`) | Fast Kalman filter prediction step. |
| **Farneback Flow Latency ($320\times180$)** | `10.70` $\pm$ `1.90` ms | Benchmark Run (`paper_eval/benchmark.py`) | Steady-state downscaled optical flow time. |
| **Farneback Flow Latency ($1280\times720$)** | `327.88` $\pm$ `235.85` ms | Benchmark Run (`paper_eval/benchmark.py`) | Native full-resolution optical flow time. |
| **Optical Flow Downscaling Speedup** | `17.20×` | Benchmark Run (`paper_eval/benchmark.py`) | Ratio of full to downscaled flow latency. |
| **Density & Risk Assessment Overhead** | `0.239` ms ($0.065 + 0.174$) | Benchmark Run (`paper_eval/benchmark.py`) | Negligible computation cost (< 0.25 ms). |
| **Average Detected Persons per Frame** | `13.25` persons | Benchmark Run (`paper_eval/benchmark.py`) | Mean detection count on test video. |
| **Maximum Tracked Persons in any Frame** | `34` persons | Benchmark Run (`paper_eval/benchmark.py`) | Peak tracked persons in test video. |
| **Tentative / Unconfirmed Track Counts** | `NOT FOUND` | Code / Repository Search | DeepSORT drops unconfirmed tracks after 1 hit. |
| **Detections at Sweep of Confidence Thresholds**| `NOT FOUND` | Code / Repository Search | Threshold fixed at 0.35 (Person) / 0.25 (Head). |
| **Firebase Live Write Latency** | `198.0` ms | `reports/fps_profiling_phase1.md:68` | Synchronous REST write latency to cloud RTDB. |

---
*Report generated strictly in compliance with empirical measurement rules for IEEE major project publication.*
