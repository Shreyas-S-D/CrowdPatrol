# CrowdPatrol — Phase 11: Final Performance & Optimization Status

**Project:** CrowdPatrol — AI-Powered Multi-Camera Crowd Monitoring & Early Warning System  
**Date:** November 22, 2026  
**Final Status:** ALL AUDITS COMPLETE & 100% VERIFIED  

---

## 1. Executive Summary

Phase 11 and its validation audits (Phase 11.1 and Phase 11.2) evaluated, benchmarked, profiled, and verified the multi-camera inference pipeline of CrowdPatrol. The goal was to achieve maximum CPU throughput and system responsiveness while strictly preserving detection resolution (640×640), detection thresholds (Person: 0.35, Head: 0.25), core AI models (YOLOv8, DeepSORT, MobileNetV2), and safety alert dispatching.

All 123 backend and reliability tests pass cleanly, the React frontend builds with zero errors, and the Streamlit dashboard remains fully operational as a fallback interface.

---

## 2. Verified Performance Telemetry

Benchmarks were isolated using reproducible scripts (`scripts/audit_benchmark_integrity.py`), strictly separating cold model initialization and 5-frame warm-up from steady-state processing:

| Pipeline Configuration | Cold Init | Warm-Up (5f) | Steady State Loop Rate | YOLO Inference FPS (per cam) | Display Render FPS | Aggregate Frame Throughput | Steady RAM |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Person Mode (Focus Feed)** | 2667.4 ms | 676.1 ms | **12.65 iters/s** | **4.15 FPS** | **13.4 FPS** | **34.4 FPS** | 686.9 MB |
| **Head Mode (Focus Feed)** | 440.7 ms | 1225.8 ms | **6.12 iters/s** | **1.96 FPS** | **6.9 FPS** | **33.0 FPS** | 864.3 MB |
| **Two-Camera Monitoring** | 495.1 ms | 996.4 ms | **9.21 iters/s** | **2.17 – 2.56 FPS** | **9.1 FPS** | **33.7 FPS** | 1087.2 MB |
| **Four-Camera 2×2 Grid** | 515.4 ms | 2201.8 ms | **3.59 iters/s** | **0.87 – 0.98 FPS** | **3.6 FPS** | **20.0 FPS** | 1454.9 MB |

### Metric Breakdown:
- **YOLO Inference FPS:** Frequency at which deep learning inference executes for a given camera channel to detect crowd objects.
- **Display Render FPS:** Frame rate at which the MJPEG stream (grid or focus) is rendered, annotated with bounding boxes and HUD, and delivered to the browser.
- **Aggregate Throughput:** Cumulative raw frames ingested and processed across all camera workers per second (including frame decode, optical flow, and Kalman prediction).

---

## 3. Detection Consistency: 1080p Reference vs. 720p Candidate

### Evaluation Methodology & Scope:
- **Scope:** Evaluates cross-resolution consistency and stability between input resolutions of the same YOLOv8 model on real CCTV footage (`data/videos/temp/upload_CAM-01_temple 1.mp4`).
- **Ground Truth Note:** Independently annotated ground truth (human bounding boxes) was **not used**. Detections from the unscaled 1080p stream serve as the reference baseline.
- **Protocol:** Candidate 720p detections are rescaled back to 1080p coordinate space and matched greedily against reference detections with IoU threshold 0.5.

### Results:

| Metric | Person Mode (conf=0.35) | Head Mode (conf=0.25) | Interpretation |
| :--- | :---: | :---: | :--- |
| **1080p Reference Retention Rate** | **98.24%** (223 / 227) | **97.85%** (500 / 511) | Fraction of 1080p detections retained at 720p |
| **720p Candidate Concordance Rate** | **94.89%** (223 / 235) | **95.97%** (500 / 521) | Fraction of 720p detections matching 1080p |
| **Harmonic Concordance Index (F-agree)** | **0.9654** | **0.9690** | Harmonic mean of Retention and Concordance |
| **Mean Bounding-Box IoU** | **0.9723 (97.23%)** | **0.9680 (96.80%)** | Spatial overlap of matched bounding boxes |
| **Mean Confidence Difference** | **0.0129 (1.29%)** | **0.0180 (1.80%)** | Score deviation between matched pairs |
| **1080p Dropouts (absent in 720p)** | **1.76%** (4 / 227) | **2.15%** (11 / 511) | Minimal loss of reference detections |
| **720p Additional Detections** | **5.11%** (12 / 235) | **4.03%** (21 / 521) | Additional detections produced at 720p scale |

**Conclusion:** Scaling 1080p video inputs to 720p prior to the 640×640 YOLO crop preserves over 97.8% of detections with 97% spatial overlap, while significantly lowering image memory bandwidth.

---

## 4. CPU & Threading Architecture

### Host Machine Profile:
- **Processor:** Intel Core i7-13700H (14 cores / 20 threads).
  - 6 Performance-cores (P-cores, with Hyper-Threading = 12 logical threads).
  - 8 Efficient-cores (E-cores, single-threaded = 8 logical threads).
- **CPU Measurement Interpretation:**
  - In Windows, `psutil` sums CPU utilization across all logical processors (maximum capacity = 2000%).
  - An aggregate metric of ~800% corresponds to 8 logical threads running at 100%, which represents **40% of the total available logical compute capacity** (or 57% of physical cores).
  - This is standard multithreaded vector execution by PyTorch's OpenMP / oneDNN engine, leaving 60% of CPU capacity for operating system, network, and application I/O.

### Thread Sweep Benchmark vs. Production Setting:
- A benchmark sweep (`[2, 4, 6, 8, 10, 14]` threads) showed peak throughput at 8 threads (3.73 iters/s vs. 3.55 iters/s at 14 threads), likely due to eliminating P-core / E-core thread synchronization overhead.
- **Production Setting:** In production code (`src/tracking.py`), PyTorch thread count defaults to 14 (capped at 14 via `if torch.get_num_threads() > 14: torch.set_num_threads(14)`).
- **Controlled Policy:** `torch.set_num_threads(8)` is **NOT applied in production**. Following strict instructions to avoid unverified global environment modifications, production retains PyTorch's default setting.

---

## 5. Architectural Integrity & Safety Constraints

1. **Detection Resolution:** Confirmed at **640×640** for both Person Mode and Head Mode across all inference paths (`src/detection.py`, `src/experimental_head_mode.py`, `backend/services/pipeline_service.py`).
2. **Confidence Thresholds:**
   - Person Mode: **0.35**
   - Head Mode: **0.25**
3. **Core Model Preservation:**
   - YOLOv8: Intact (weights: `models/yolov8n.pt`, `models/crowdpatrol_yolov8n_head_v4.pt`).
   - DeepSORT: Intact (`deep_sort_realtime`).
   - MobileNetV2: Intact; `channels_last` memory format verified mathematically equivalent (cosine similarity: `0.99999988`).
4. **Alert Safety Independence:**
   - Heatmap throttling (`frame_iter % 2 == 0`) strictly throttles the JPEG encoding for the browser MJPEG stream.
   - Core risk calculations (`cam.density_map`, `cam.max_density`, `motion_summary`) and `AlertManager.process_camera_telemetry()` execute on **every single frame unthrottled**.
5. **Streamlit Fallback:** `dashboard/simple_dashboard.py` and `dashboard/landing_page.py` compile cleanly and remain fully functional.

---

## 6. Regression Test Suite Matrix

Every test suite in the project was executed and verified:

| Test Suite | File | Count | Passed | Failed | Execution Time |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **FastAPI Backend Suite** | `tests/test_fastapi_backend.py` | 13 | 13 | 0 | 9.48s |
| **Alert Manager Suite** | `tests/test_alert_manager.py` | 27 | 27 | 0 | 4.80s |
| **Dual Detection Mode Suite** | `tests/test_dual_mode.py` | 33 | 33 | 0 | 3.32s |
| **Multi-Camera Engine Suite** | `tests/test_multi_camera.py` | 37 | 37 | 0 | 19.26s |
| **Landing Page Backend Suite** | `tests/test_landing_page.py` | 6 | 6 | 0 | 7.10s |
| **Physical Camera Reliability** | `tests/test_phase10_camera_reliability.py` | 7 | 7 | 0 | 47.45s |
| **React Frontend Production Build** | `frontend/` (`npm run build`) | Vite build | Pass | 0 | 0.88s |
| **Total Test Count** | **All suites combined** | **123** | **123** | **0** | **100% PASS** |

---

## 7. Known Remaining Limitations

1. **Four-Camera Inference Latency on Pure CPU:**
   - In a 4-camera 2×2 grid on pure CPU execution, each camera achieves ~0.87–0.98 YOLO inference FPS (~1.0–1.1s detection interval per camera).
   - DeepSORT's Kalman filter predicts object trajectories at 0.01ms between detection intervals to maintain continuous track IDs.
   - While adequate for steady crowd flow monitoring, high-speed crowd surges may experience a ~1s detection latency.
   - Real-time 15–30 FPS detection across 4 concurrent 1080p feeds on this architecture requires dedicated GPU acceleration (NVIDIA CUDA / TensorRT).
2. **DirectShow / RTSP Probing on Windows:**
   - Probing non-existent RTSP streams or inactive camera hardware incurs a 12–30s OpenCV/FFmpeg socket timeout in background worker threads before returning OFFLINE.
   - This is handled gracefully by timeout guards and background polling, but is an inherent characteristic of the underlying OS media framework.

---

## 8. Backup & Rollback Inventory

All original Phase 11 files remain safely backed up in `backups/phase11/`:
- `backups/phase11/detection.py`
- `backups/phase11/heatmap.py`
- `backups/phase11/multi_camera_manager.py`
- `backups/phase11/pipeline_service.py`
- `backups/phase11/tracking.py`
- `backups/phase11/utils.py`

---

## 9. Final Sign-Off

CrowdPatrol Phase 11 performance optimizations and validation audits (Phase 11.1 & 11.2) have concluded with 100% compliance with all system constraints, zero regressions across 123 tests, and fully documented telemetry and limitations.
