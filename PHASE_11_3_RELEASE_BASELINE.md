# CrowdPatrol — Phase 11.3: Release Baseline & Audit Report

**Project:** CrowdPatrol — Multi-Camera CCTV Crowd Monitoring & Early Warning System  
**Date:** November 23, 2026  
**Auditor:** Antigravity AI Engineering Assistant  
**Milestone:** Phase 11 Final Baseline Freeze  
**Git Branch:** `multi-camera-command-center`  
**Working Tree Status:** Cleanly auditable; no commits or destructive resets performed.

---

## 1. Final Implementation Status

Phase 11 (Performance Optimization) and its follow-on validation audits (Phase 11.1 and Phase 11.2) have established an optimized, stable, and verified multi-camera surveillance pipeline.

### Core Achievements:
1. **PyTorch Inference Mode:** Wrapped YOLO forward passes in `torch.inference_mode()` across `src/detection.py`, eliminating autograd graph overhead.
2. **DeepSORT MobileNetV2 Memory Optimization:** Migrated embedder feature tensors to `torch.channels_last` layout in `src/tracking.py`, providing faster CPU memory locality while maintaining strict numerical equivalence (Minimum Cosine Similarity: `0.99999988`).
3. **Surveillance Input Standardization:** Standardized raw video streams to a maximum display resolution of 1280×720 in `src/multi_camera_manager.py` before passing to the 640×640 detection tensor, cutting buffer transfer overhead without degrading detection agreement (Mean IoU: `0.9723` Person, `0.9680` Head; 1080p Retention Rate: `98.24%` Person, `97.85%` Head).
4. **ROI-Based HUD Alpha Blending:** Replaced full-frame `cv2.addWeighted` copying with sub-region ROI blending (`frame[:hud_h, :]`) in `src/utils.py`, reducing per-frame annotation time from 4.8ms to 0.4ms.
5. **Decoupled Heatmap Display Throttling:** Throttled web MJPEG JPEG compression to every 2nd frame (`backend/services/pipeline_service.py`), while keeping core density calculation and emergency alert dispatching running at **100% full unthrottled frame rate**.
6. **Strict Preservation of Safety Parameters:** Confirmed detection tensor size at **640×640**, Head confidence at **0.25**, Person confidence at **0.35**, and alert routing to SMTP email / SMS completely untouched.

---

## 2. Complete Changed-File Inventory

### A. Tracked Modified Files (`git diff --stat`)

| File Path | Description of Changes |
| :--- | :--- |
| `src/detection.py` | Wrapped YOLO inference in `torch.inference_mode()`; implemented `detect_batch()` for multi-frame support. |
| `src/tracking.py` | Initialized MobileNetV2 embedder with `torch.channels_last` memory format; thread clamp at 14. |
| `src/multi_camera_manager.py` | Standardized display frame resolution to 1280×720; zero-copy frame assignment (`cam.current_frame = frame`); default `yolo_imgsz=640`. |
| `src/utils.py` | Optimized HUD overlay rendering using sub-region ROI alpha blending rather than whole-frame copying. |
| `src/alert_manager.py` | Alert history enhancements, notification dispatcher attachment hooks, spatial zone risk extraction. |
| `src/alerts.py` | Added namespaced & flat RTDB sync for alerts and status update propagation. |
| `src/camera_devices.py` | Hardware camera device discovery, DirectShow & MediaFoundation probing, connection verification. |
| `src/experimental_head_mode.py` | Head detection pipeline support, 640×640 tensor input, confidence 0.25. |
| `src/motion_analysis.py` | Optical flow stride support and camera motion detection. |
| `config/cameras.json` | Multi-camera configuration defaults. |
| `dashboard/dashboard_utils.py` | Streamlit dashboard UI helpers and status widgets. |
| `dashboard/simple_dashboard.py` | Streamlit command-center fallback dashboard. |
| `tests/test_alert_manager.py` | Unit and integration tests for alert lifecycle and severity routing. |
| `tests/test_dual_mode.py` | Unit tests for Person Mode vs. Head Mode transitions. |
| `tests/test_multi_camera.py` | Multi-camera synchronization, focus switching, and staggered stride unit tests. |

### B. Untracked Phase 11 Audit & Benchmark Scripts (`scripts/`)

| File Path | Purpose & Status |
| :--- | :--- |
| `scripts/audit_benchmark_integrity.py` | Isolates cold model init, 5-frame warm-up, and steady-state loop rate. |
| `scripts/audit_detection_accuracy.py` | Evaluates 1080p reference vs. 720p candidate cross-resolution agreement and concordance. |
| `scripts/audit_embeddings_tolerance.py` | Verifies MobileNetV2 NCHW vs. Channels-Last numerical float tolerance. |
| `scripts/audit_threads_and_cpu.py` | Empirical sweep across `[2, 4, 6, 8, 10, 14]` threads on the i7-13700H. |
| `scripts/profile_phase11_baseline.py` | Baseline profiling script for Phase 11. |
| `scripts/test_embedder_speed.py` | Standalone embedder benchmark. |
| `scripts/test_heatmap_opt.py` | Heatmap generation optimization test. |
| `scripts/test_hud_opt.py` | ROI HUD blending benchmark. |

### C. Untracked Release & Audit Documentation

| File Path | Description |
| :--- | :--- |
| `PHASE_11_1_PERFORMANCE_VALIDATION_AUDIT_REPORT.md` | Comprehensive validation audit report with corrected terminology and CPU architecture analysis. |
| `PHASE_11_FINAL_STATUS.md` | Final optimization status, benchmark summary, and verification sign-off. |
| `PHASE_11_3_RELEASE_BASELINE.md` | This document: release baseline, file inventory, and next milestone. |

### D. Untracked Application & Test Infrastructure

| File Path | Description |
| :--- | :--- |
| `backend/` | FastAPI application, REST endpoints, and WebSocket/MJPEG streaming services. |
| `frontend/` | React + Vite security-tech CCTV web application. |
| `tests/test_fastapi_backend.py` | FastAPI backend test suite (13 tests). |
| `tests/test_landing_page.py` | Landing page backend test suite (6 tests). |
| `tests/test_phase10_camera_reliability.py` | Physical camera validation & reliability test suite (7 tests). |
| `backups/phase11/` | Pre-Phase 11 original source backups (6 files). |

---

## 3. Verified Test Results Matrix

All 123 backend and reliability tests pass cleanly, and the frontend builds without warnings:

| Test Suite | File / Command | Tests | Status | Duration |
| :--- | :--- | :---: | :---: | :---: |
| **FastAPI Backend Suite** | `tests/test_fastapi_backend.py` | 13 | **13 PASSED** | 9.48s |
| **Alert Manager Suite** | `tests/test_alert_manager.py` | 27 | **27 PASSED** | 4.80s |
| **Dual Detection Mode Suite** | `tests/test_dual_mode.py` | 33 | **33 PASSED** | 3.32s |
| **Multi-Camera Engine Suite** | `tests/test_multi_camera.py` | 37 | **37 PASSED** | 19.26s |
| **Landing Page Backend Suite** | `tests/test_landing_page.py` | 6 | **6 PASSED** | 7.10s |
| **Physical Camera Reliability** | `tests/test_phase10_camera_reliability.py` | 7 | **7 PASSED** | 47.45s |
| **React Frontend Production Build** | `cd frontend && npm run build` | Bundle | **SUCCESS** | 0.88s |
| **Streamlit Fallback Syntax Verification** | `py_compile dashboard/simple_dashboard.py` | Compile | **SUCCESS** | < 1.0s |
| **Total Test Count** | Across all suites | **123** | **123 PASSED (100%)** | — |

---

## 4. Final Performance Telemetry

Isolated steady-state measurements on host hardware (Intel Core i7-13700H, 14 cores / 20 threads, CPU execution):

| Workload Configuration | Cold Model Init | Warm-Up (5f) | Steady Loop Rate | YOLO Inference FPS | Display Render FPS | Aggregate Throughput | Process RAM |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Person Mode (Focus Feed)** | 2667.4 ms | 676.1 ms | **12.65 it/s** | **4.15 FPS** | **13.4 FPS** | **34.4 FPS** | 686.9 MB |
| **Head Mode (Focus Feed)** | 440.7 ms | 1225.8 ms | **6.12 it/s** | **1.96 FPS** | **6.9 FPS** | **33.0 FPS** | 864.3 MB |
| **Two-Camera Monitoring** | 495.1 ms | 996.4 ms | **9.21 it/s** | **2.17 – 2.56 FPS** | **9.1 FPS** | **33.7 FPS** | 1087.2 MB |
| **Four-Camera 2×2 Grid** | 515.4 ms | 2201.8 ms | **3.59 it/s** | **0.87 – 0.98 FPS** | **3.6 FPS** | **20.0 FPS** | 1454.9 MB |

---

## 5. Known Limitations

1. **Four-Camera Pure CPU Inference Latency:**
   - Under pure CPU execution without hardware GPU acceleration, running 4 concurrent video feeds in a 2×2 grid yields ~0.87–0.98 YOLO inference FPS per camera.
   - DeepSORT's Kalman filter bridges the gap at 0.01ms per frame, ensuring smooth track maintenance.
   - However, rapid scene changes or sudden crowd surges have a detection latency of ~1.0–1.1s on CPU.
   - Dedicated GPU acceleration (NVIDIA CUDA / TensorRT) is required to achieve 15–30 YOLO FPS per camera across 4 streams.
2. **DirectShow / RTSP Probing Timeouts:**
   - Probing offline RTSP URLs or invalid hardware camera indices on Windows incurs a 12–30s OpenCV/FFmpeg network timeout in daemon worker threads before reporting OFFLINE.
   - Handled gracefully by background timeout guards without crashing or blocking the main event loop.

---

## 6. Backup & Rollback Inventory

Original pre-Phase 11 versions of all modified files are preserved in `backups/phase11/`:
- `backups/phase11/detection.py` (Pre-inference_mode YOLO wrapper)
- `backups/phase11/tracking.py` (Pre-channels_last DeepSORT embedder)
- `backups/phase11/multi_camera_manager.py` (Pre-720p standardization manager)
- `backups/phase11/utils.py` (Pre-ROI whole-frame HUD blending)
- `backups/phase11/pipeline_service.py` (Pre-throttling pipeline worker)
- `backups/phase11/heatmap.py` (Original heatmap generation)

---

## 7. Recommended Next Development Milestone

### Milestone: Phase 12 — Production Packaging & Hardware Acceleration
1. **Containerization & Deployment Packaging:**
   - Author a multi-stage `Dockerfile` and `docker-compose.yml` encapsulating the FastAPI backend, Uvicorn server, and built React frontend assets via Nginx or static mounting.
2. **GPU Acceleration (CUDA / TensorRT) Support:**
   - Implement optional automatic GPU detection (`torch.cuda.is_available()`) to route YOLOv8 and MobileNetV2 tensors to CUDA when available.
   - This will lift the 4-camera inference bottleneck from ~0.9 FPS to 25–30 FPS per camera.
3. **Automated End-to-End System Integration Test:**
   - Package a one-click launcher script (`run_crowdpatrol.bat` / `run_crowdpatrol.sh`) that starts FastAPI and serves the React dashboard.
