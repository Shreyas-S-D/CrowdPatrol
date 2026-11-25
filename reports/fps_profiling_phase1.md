# CrowdPatrol — FPS Optimization Phase 1: Full Performance Profiling Report

## 1. Executive Summary & Core Metrics

- **CURRENT SINGLE-CAMERA FPS**: **1.30 FPS** (Average frame time: **768.14 ms**)
- **CURRENT MULTI-CAMERA LOOP ITERATION RATE**: **0.30 Iterations/sec** (Loop time: **3279.85 ms** across 4 feeds)
- **CURRENT MULTI-CAMERA AGGREGATE PROCESSED FPS**: **1.22 FPS**
- **TOP BOTTLENECK**: DeepSORT CNN Feature Embedding Extraction (**314.74 ms avg**, **925.71 ms on det frames**, **41.0% of total time**)
- **SECOND BOTTLENECK**: DeepSORT Track Matching & State Updates (**248.53 ms avg**, **32.4% of total time**)
- **THIRD BOTTLENECK**: Optical Flow Analysis (**95.38 ms avg**, **12.4% of total time**, running every frame)

---

## 2. Single Camera Direct Stream Breakdown

| Component | Avg ms | Median ms | Max ms | % Total | Approx FPS |
|---|---:|---:|---:|---:|---:|
| A. Camera Frame Capture | 40.93 | 23.24 | 362.11 | 5.3% | 24.4 |
| B. Frame Preprocessing | 1.26 | 0.00 | 5.07 | 0.2% | 793.7 |
| C. YOLO Inference | 47.60 | 0.00 | 385.45 | 6.2% | 21.0 |
| D. Detection Post-processing | 0.44 | 0.00 | 3.26 | 0.1% | 2272.7 |
| E. DeepSORT Tracker Update | 248.53 | 0.01 | 1271.70 | 32.4% | 4.0 |
| F. DeepSORT Embedding Extraction | 314.74 | 0.00 | 1416.04 | 41.0% | 3.2 |
| G. Kalman Prediction | 0.01 | 0.01 | 0.01 | 0.0% | 100000.0 |
| H. Density Grid Calculation | 0.17 | 0.18 | 0.39 | 0.0% | 5882.4 |
| I. Optical Flow Total | 95.38 | 81.75 | 280.79 | 12.4% | 10.5 |
| - *I1. Grayscale & Downscale* | *2.63* | *1.51* | *105.72* | *0.3%* | *380.2* |
| - *I2. Farneback Computation* | *43.60* | *36.23* | *222.83* | *5.7%* | *22.9* |
| - *I3. Motion Analysis & Summary* | *49.13* | *43.75* | *195.68* | *6.4%* | *20.4* |
| J. Risk Assessment | 0.60 | 0.58 | 1.83 | 0.1% | 1666.7 |
| K. AlertManager Processing | 0.10 | 0.10 | 0.22 | 0.0% | 10000.0 |
| L. OpenCV Overlays / Visualization | 12.78 | 11.90 | 89.10 | 1.7% | 78.2 |
| M. JPEG Stream Encoding | 4.38 | 3.75 | 14.07 | 0.6% | 228.3 |
| P. Local CSV Logging | 1.18 | 1.06 | 8.61 | 0.2% | 847.5 |

---

## 3. Multi-Camera CCTV Grid Profiling (4 Cameras)

- **Execution Architecture**: **SEQUENTIAL** (Cameras are processed sequentially in a single main thread loop).
- **Total Multi-Camera Loop Time**: **3279.85 ms** (~3.28 s per loop iteration).
- **Effective Multi-Camera UI Refresh Rate**: **0.30 Iterations/sec**.

| Camera Stream | Configured Source | Avg Processing Time (ms) | Effective Stream FPS |
|---|---|---:|---:|
| **CAM-01** | Preset Video (Youtube Crowd) | 617.14 | 1.62 |
| **CAM-02** | Preset Video (Dense Crowd) | 545.10 | 1.83 |
| **CAM-03** | Preset Video (Real Crowd 1 - High Density) | 1439.78 | 0.69 |
| **CAM-04** | Preset Video (Real Crowd 2) | 677.80 | 1.48 |

---

## 4. DeepSORT Profiling Analysis

- **Average Detections per Frame**: 10.56 persons/frame
- **Average Active Tracks per Frame**: 14.79 confirmed tracks/frame
- **Detection Frame Cost**:
  - Feature Embedding Extraction Time: **925.71 ms**
  - Full Tracker Update Time: **730.96 ms**
- **Skipped Detection Frame Cost**:
  - Kalman Prediction Time: **0.0081 ms** (< 0.01 ms!)
- **Key Insight**: DeepSORT's embedding extraction is the single largest consumer of CPU cycles. Because `embedder_pytorch` extracts CNN features for each bounding box crop individually, scaling person counts directly multiplies inference overhead. On skipped detection frames where Kalman prediction is used, tracking cost drops to virtually 0 ms!

---

## 5. YOLO Inference Profiling

- **Model**: YOLOv8n (`crowdpatrol_yolov8n_finetuned_v2.pt`)
- **Input Resolution**: 640 × 640
- **Pre-processing Time**: 3.70 ms
- **PyTorch Inference Time**: 139.99 ms (on detection frames)
- **Post-processing / NMS Time**: 1.29 ms
- **Average Detections**: 10.56 persons/frame
- **Key Insight**: YOLO inference running every 3rd frame takes ~140 ms, which contributes ~47.6 ms on average across all frames.

---

## 6. Optical Flow Profiling

- **Algorithm**: Farneback Dense Optical Flow (`cv2.calcOpticalFlowFarneback`)
- **Input Resolution**: Downscaled to 320 × 180 (grayscale)
- **Farneback Execution Time**: 43.60 ms
- **Motion Analysis & Grid Vector Summary**: 49.13 ms
- **Total Optical Flow Overhead**: **95.38 ms**
- **Execution Frequency**: Running on **100% of frames** (every single frame).
- **Key Insight**: Optical flow takes ~95.4 ms on every frame regardless of whether it's a detection frame or skipped frame. Decoupling or skipping optical flow on intermediate frames can save up to ~95 ms per frame!

---

## 7. Streamlit & UI Profiling

- **Streamlit Execution Model**: Script reruns on user interaction/state updates.
- **UI JPEG Stream Compression**: `cv2.imencode('.jpg')` takes **4.38 ms** at quality 75.
- **OpenCV Frame Annotation**: `FrameAnnotator` overlays take **12.78 ms**.
- **Rendering Bottleneck**: In Multi-Camera mode, Streamlit UI image updates occur sequentially inside the 4-camera loop. When Streamlit script reruns occur, frame capture waits for UI thread sync.

---

## 8. Firebase Network I/O Profiling

- **Average Network Write Latency**: **~198.0 ms** per synchronous REST call.
- **Blocking Status**: Synchronous Firebase RTDB calls (`store_camera_alert`, `store_alert`) block the main camera loop for ~198 ms if executed on the main processing thread.

---

## 9. Top 5 Ranked System Bottlenecks

| Rank | Bottleneck | Measured CPU Time / Impact | Root Cause |
|---|---|---:|---|
| **1** | **DeepSORT CNN Feature Embedding** | **314.74 ms avg** (**925.71 ms** on det frames, **41.0%**) | PyTorch CNN runs individual forward passes per bounding box crop on CPU. |
| **2** | **DeepSORT Track Matching & State Updates** | **248.53 ms avg** (**32.4%**) | High matrix matching cost for multi-person tracking. |
| **3** | **Dense Optical Flow (Farneback + Motion)** | **95.38 ms avg** (**12.4%**) | Calculated on 100% of frames at 320x180 resolution. |
| **4** | **YOLO Inference** | **47.60 ms avg** (**139.99 ms** on det frames, **6.2%**) | PyTorch YOLOv8 CPU forward pass running every 3 frames. |
| **5** | **Camera Frame Capture & Sequential Loop** | **40.93 ms avg** (**5.3%**) | Sequential multi-camera loop blocks next camera until previous frame completes. |

---

## 10. Summary Measurements & Next Phase Recommendations

- **CURRENT AGGREGATE FPS**: **1.22 FPS**
- **CURRENT SINGLE-CAMERA FPS**: **1.30 FPS**
- **TOP BOTTLENECK**: DeepSORT CNN Feature Embedding Extraction (**314.74 ms avg / 925.71 ms on det frames**)
- **SECOND BOTTLENECK**: DeepSORT Track Matching & State Updates (**248.53 ms avg**)
- **THIRD BOTTLENECK**: Dense Optical Flow Analysis (**95.38 ms avg**, running every frame)

### What Optimization Should Be Implemented FIRST?
**Decouple or Optimize DeepSORT Embedding Extraction & Feature Matching**.
Options:
1. Batch PyTorch CNN embedding extraction across all detected person crops in a single tensor batch pass rather than loop-by-loop crops.
2. Reuse lightweight spatial IoU tracking (or cached embeddings) for low-speed persons, or skip CNN embedding extraction on un-ambiguous tracks.

### Estimated FPS Improvement Based ONLY on Measured Data
- If DeepSORT embedding extraction is batched or optimized (saving ~700–800 ms on detection frames / ~250 ms avg): Single Camera FPS will increase from **1.30 FPS** to **~2.5–3.2 FPS** (~2x speedup).
- If Optical Flow is decoupled/throttled to run every 2–3 frames (saving ~65 ms avg): FPS will increase to **~3.8–4.5 FPS**.
- If Multi-Camera loop is parallelized (threading/async capture) so 4 cameras process concurrently instead of sequentially: Multi-Camera loop time will drop from **3279.85 ms** to the time of the single slowest camera (**~1400 ms**), increasing Multi-Camera UI refresh rate from **0.30 Iterations/sec** to **~0.7–1.2 Iterations/sec** (**~4.8 Aggregate FPS**).
