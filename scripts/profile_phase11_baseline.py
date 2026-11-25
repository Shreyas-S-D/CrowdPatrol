"""
CrowdPatrol Phase 11 — Comprehensive Profiling & Baseline Benchmark Script
Profiles individual pipeline components and multi-camera orchestration end-to-end.
"""

import sys
import time
import os
import psutil
import cv2
import torch
import numpy as np
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
sys.path.append(str(BASE_DIR))

from src.detection import PersonDetector
from src.experimental_head_mode import ExperimentalHeadDetector, DEFAULT_HEAD_MODEL_PATH
from src.tracking import PersonTracker
from src.motion_analysis import CrowdMotionAnalyzer
from src.density import DensityEstimator
from src.risk_assessment import RiskAssessor
from src.heatmap import generate_heatmap
from src.utils import FrameAnnotator
from src.multi_camera_manager import MultiCameraManager, CameraState


def profile_components(sample_video_path="data/videos/temp/upload_CAM-01_temple 1.mp4", num_iterations=20):
    print("=" * 70)
    print("1. PROFILING INDIVIDUAL PIPELINE COMPONENTS")
    print("=" * 70)
    print(f"PyTorch Version: {torch.__version__} | CPU Threads: {torch.get_num_threads()}")
    
    cap = cv2.VideoCapture(sample_video_path)
    if not cap.isOpened():
        print(f"Error opening {sample_video_path}")
        return
        
    # Read a dense frame
    cap.set(cv2.CAP_PROP_POS_FRAMES, 50)
    ret, frame = cap.read()
    cap.release()
    
    if not ret or frame is None:
        print("Failed to read video frame.")
        return
        
    h, w = frame.shape[:2]
    print(f"Input Frame Resolution: {w}x{h}")
    
    # Instantiate components
    person_detector = PersonDetector(confidence=0.35, device="cpu", imgsz=640)
    head_model_path = "models/crowdpatrol_yolov8n_head_v4.pt" if os.path.exists("models/crowdpatrol_yolov8n_head_v4.pt") else DEFAULT_HEAD_MODEL_PATH
    head_detector = ExperimentalHeadDetector(model_path=head_model_path, confidence=0.25, device="cpu", imgsz=640)
    
    tracker = PersonTracker(max_age=30, n_init=1)
    motion_analyzer = CrowdMotionAnalyzer(grid_size=(4, 4), flow_interval=1)
    density_estimator = DensityEstimator(grid_size=(4, 4))
    risk_assessor = RiskAssessor()
    
    # Warmup
    for _ in range(3):
        _ = person_detector.detect(frame)
        _ = head_detector.detect(frame, tiled=False)
        _ = motion_analyzer.analyze_frame(frame)
        
    person_dets = person_detector.detect(frame)
    head_dets = head_detector.detect(frame, tiled=False)
    
    # Warmup tracker with detections
    _ = tracker.update(person_dets, frame)
    
    # A. Preprocessing / Color Conversions / Frame Copying
    t_copies = []
    t_converts = []
    for _ in range(num_iterations):
        t0 = time.perf_counter()
        f_copy = frame.copy()
        t_copies.append((time.perf_counter() - t0) * 1000)
        
        t0 = time.perf_counter()
        _ = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        t_converts.append((time.perf_counter() - t0) * 1000)
    print(f"Frame copy (1280x720):             {np.mean(t_copies):6.2f} ms")
    print(f"Color conversion (BGR->GRAY):       {np.mean(t_converts):6.2f} ms")
    
    # B. YOLOv8 Person Mode (640x640)
    t_person_yolo = []
    for _ in range(num_iterations):
        t0 = time.perf_counter()
        _ = person_detector.detect(frame)
        t_person_yolo.append((time.perf_counter() - t0) * 1000)
    print(f"YOLOv8 Person Mode (640x640, c=0.35): {np.mean(t_person_yolo):6.2f} ms (dets: {len(person_dets)})")
    
    # C. YOLOv8 Head Mode (640x640, full-frame)
    t_head_yolo = []
    for _ in range(num_iterations):
        t0 = time.perf_counter()
        _ = head_detector.detect(frame, tiled=False)
        t_head_yolo.append((time.perf_counter() - t0) * 1000)
    print(f"YOLOv8 Head Mode (640x640, c=0.25):   {np.mean(t_head_yolo):6.2f} ms (dets: {len(head_dets)})")

    # D. DeepSORT / MobileNetV2 Embedding & Tracking
    t_tracker_update = []
    t_tracker_predict = []
    for _ in range(num_iterations):
        t0 = time.perf_counter()
        _ = tracker.update(person_dets, frame)
        t_tracker_update.append((time.perf_counter() - t0) * 1000)
        
        t0 = time.perf_counter()
        _ = tracker.predict()
        t_tracker_predict.append((time.perf_counter() - t0) * 1000)
    print(f"DeepSORT Update ({len(person_dets)} crops):        {np.mean(t_tracker_update):6.2f} ms")
    print(f"DeepSORT Predict (inter-frame):     {np.mean(t_tracker_predict):6.2f} ms")

    # E. Farneback Optical Flow Motion Analysis
    t_flow = []
    for _ in range(num_iterations):
        t0 = time.perf_counter()
        _ = motion_analyzer.analyze_frame(frame)
        t_flow.append((time.perf_counter() - t0) * 1000)
    print(f"Optical Flow (Farneback 320x180):   {np.mean(t_flow):6.2f} ms")

    # F. Density & Risk Assessment
    active_tracks = tracker.get_visible_tracks()
    t_density = []
    t_risk = []
    for _ in range(num_iterations):
        t0 = time.perf_counter()
        density_map, max_density = density_estimator.calculate_density(active_tracks, frame.shape)
        t_density.append((time.perf_counter() - t0) * 1000)
        
        t0 = time.perf_counter()
        _ = risk_assessor.assess_frame(
            max_density=max_density,
            motion_summary={"avg_speed": 1.2, "dominant_direction": "E", "camera_motion_detected": False},
            tracks=active_tracks,
            timestamp=time.time(),
            anomaly_score=0.1
        )
        t_risk.append((time.perf_counter() - t0) * 1000)
    print(f"Density Estimation (4x4):           {np.mean(t_density):6.2f} ms")
    print(f"Risk Assessment (multi-factor):     {np.mean(t_risk):6.2f} ms")

    # G. Heatmap Generation & Frame Annotation
    t_heatmap = []
    t_hud = []
    for _ in range(num_iterations):
        t0 = time.perf_counter()
        hm_base, _ = generate_heatmap(frame, active_tracks, draw_grid=False)
        t_heatmap.append((time.perf_counter() - t0) * 1000)
        
        t0 = time.perf_counter()
        _ = FrameAnnotator.create_dashboard_frame(
            hm_base,
            {
                "camera_id": "CAM-01", "camera_name": "Temple North", "mode": "Person Mode",
                "person_count": len(active_tracks), "active_tracks": len(active_tracks),
                "visible_heads": 0, "density": max_density, "anomaly": 0.1,
                "avg_speed": 1.2, "dominant_direction": "E", "risk": "LOW",
                "combined_score": 15.0, "alert_state": "NORMAL", "fps": 25.0
            },
            density_map,
            grid_size=(4, 4),
            tracks=active_tracks
        )
        t_hud.append((time.perf_counter() - t0) * 1000)
    print(f"Heatmap Blending (1280x720):        {np.mean(t_heatmap):6.2f} ms")
    print(f"HUD & Stat Panel Overlay:           {np.mean(t_hud):6.2f} ms")

    # H. JPEG Encoding
    t_encode = []
    for _ in range(num_iterations):
        t0 = time.perf_counter()
        _ = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
        t_encode.append((time.perf_counter() - t0) * 1000)
    print(f"JPEG Encode (1280x720 @ Q=80):       {np.mean(t_encode):6.2f} ms")
    print("=" * 70)


def benchmark_multicamera_workloads(num_frames=40):
    print("\n" + "=" * 70)
    print("2. MULTI-CAMERA WORKLOAD BENCHMARKS (END-TO-END)")
    print("=" * 70)

    configs = [
        ("Person Mode Focus Feed", "PERSON", "FOCUS", ["CAM-01"]),
        ("Head Mode Focus Feed", "HEAD", "FOCUS", ["CAM-01"]),
        ("Two-Camera Monitoring (CAM-01, CAM-02)", "PERSON", "GRID", ["CAM-01", "CAM-02"]),
        ("Four-Camera 2x2 Grid (All Cameras)", "PERSON", "GRID", ["CAM-01", "CAM-02", "CAM-03", "CAM-04"]),
    ]

    proc = psutil.Process()

    for label, mode, op_mode, enabled_cams in configs:
        # Initialize MultiCameraManager with yolo_imgsz=640 (audited)
        mcm = MultiCameraManager(
            detection_mode=mode,
            device="cpu",
            detect_interval=3,
            flow_interval=2,
            yolo_imgsz=640
        )
        
        # Enable only specified cameras
        for cid, cam in mcm.cameras.items():
            cam.enabled = (cid in enabled_cams)
            
        mcm.start_all_cameras()
        
        # Warmup 5 frames
        for _ in range(5):
            if op_mode == "FOCUS":
                mcm.step_focus("CAM-01", step_background=True)
            else:
                mcm.step_all()

        # Run benchmark
        proc.cpu_percent()
        mem_before = proc.memory_info().rss / (1024 * 1024)
        t_start = time.perf_counter()
        
        for _ in range(num_frames):
            if op_mode == "FOCUS":
                mcm.step_focus("CAM-01", step_background=True)
            else:
                mcm.step_all()
                
        dur = time.perf_counter() - t_start
        cpu_usage = proc.cpu_percent()
        mem_after = proc.memory_info().rss / (1024 * 1024)
        
        metrics = mcm.get_throughput_metrics()
        grid_fps = metrics.get("grid_display_fps", 0.0)
        inf_fps = metrics.get("yolo_inference_fps", {})
        agg_fps = metrics.get("aggregate_throughput_fps", 0.0)
        loop_fps = num_frames / dur
        
        print(f"\nBenchmark: {label}")
        print(f"  Execution Duration:      {dur:.2f} s ({num_frames} cycles, {loop_fps:.2f} loop-iter/s)")
        print(f"  CPU Utilization:         {cpu_usage:.1f}%")
        print(f"  Memory Footprint:        {mem_after:.1f} MB (delta: {mem_after - mem_before:+.1f} MB)")
        print(f"  Display / Grid FPS:      {grid_fps:.1f} FPS")
        print(f"  YOLO Inference FPS:      {inf_fps}")
        print(f"  Aggregate Throughput:    {agg_fps:.1f} processed frames/sec")

        mcm.stop_all_cameras()

    print("=" * 70)


if __name__ == "__main__":
    profile_components()
    benchmark_multicamera_workloads(num_frames=30)
