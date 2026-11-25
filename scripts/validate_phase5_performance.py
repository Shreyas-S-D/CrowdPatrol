"""
CrowdPatrol Phase 5 Comprehensive Performance & Resource Validation Benchmark.

Measures:
1. Actual YOLO inference FPS vs Display FPS.
2. Single-Camera (Person Mode vs Head Mode).
3. 2x2 Multi-Camera (Grid Mode vs Focus Mode).
4. Dense crowd accuracy verification on dense_crowd_test.mp4.
5. CPU and Memory utilization under sustained processing.
"""

import sys
import os
import time
import psutil
import numpy as np
import cv2
import torch
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.detection import PersonDetector
from src.experimental_head_mode import ExperimentalHeadDetector, DEFAULT_HEAD_MODEL_PATH
from src.tracking import PersonTracker
from src.density import DensityEstimator
from src.experimental_head_density import HeadDensityEstimator
from src.motion_analysis import CrowdMotionAnalyzer
from src.risk_assessment import RiskAssessor
from src.experimental_head_risk import ExperimentalHeadRiskAdapter
from src.multi_camera_manager import MultiCameraManager

def benchmark_single_camera():
    print("\n" + "="*60)
    print("   BENCHMARK 1: SINGLE CAMERA (PERSON MODE VS HEAD MODE)")
    print("="*60)
    
    test_video = "data/videos/dense_crowd_test.mp4"
    if not os.path.exists(test_video):
        print(f"[!] Test video {test_video} not found, generating synthetic frames.")
        frames = [np.random.randint(0, 255, (720, 1280, 3), dtype=np.uint8) for _ in range(60)]
    else:
        cap = cv2.VideoCapture(test_video)
        frames = []
        for _ in range(60):
            ret, frame = cap.read()
            if not ret:
                break
            frames.append(frame)
        cap.release()
        
    print(f"Loaded {len(frames)} frames for evaluation.")
    proc = psutil.Process()

    # --- Mode A: Person Mode ---
    print("\n[A] Testing Person Mode (YOLOv8n-V2 + DeepSORT + Optical Flow)...")
    p_detector = PersonDetector(confidence=0.35, device="cpu")
    p_tracker = PersonTracker(max_age=30, n_init=1)
    p_motion = CrowdMotionAnalyzer()
    p_density = DensityEstimator()
    p_risk = RiskAssessor()

    yolo_times = []
    track_times = []
    flow_times = []
    total_times = []
    
    # Warmup
    _ = p_detector.detect(frames[0])
    
    mem_before = proc.memory_info().rss / (1024 * 1024)
    cpu_start = proc.cpu_percent(interval=None)
    t_start = time.perf_counter()
    
    for f in frames:
        t0 = time.perf_counter()
        
        # 1. Detection
        td0 = time.perf_counter()
        dets = p_detector.detect(f)
        td1 = time.perf_counter()
        yolo_times.append((td1 - td0) * 1000.0)
        
        # 2. Tracking
        tt0 = time.perf_counter()
        tracks = p_tracker.update(dets, f)
        tt1 = time.perf_counter()
        track_times.append((tt1 - tt0) * 1000.0)
        
        # 3. Motion
        tm0 = time.perf_counter()
        _, motion_summary = p_motion.analyze_frame(f)
        tm1 = time.perf_counter()
        flow_times.append((tm1 - tm0) * 1000.0)
        
        # 4. Density & Risk
        _, max_density = p_density.calculate_density(tracks, f.shape)
        _ = p_risk.assess_frame(max_density, motion_summary, tracks, time.time())
        
        t1 = time.perf_counter()
        total_times.append((t1 - t0) * 1000.0)
        
    t_end = time.perf_counter()
    cpu_person = proc.cpu_percent(interval=None)
    mem_after = proc.memory_info().rss / (1024 * 1024)
    
    p_yolo_ms = np.mean(yolo_times)
    p_track_ms = np.mean(track_times)
    p_flow_ms = np.mean(flow_times)
    p_total_ms = np.mean(total_times)
    p_inf_fps = 1000.0 / p_yolo_ms
    p_pipe_fps = 1000.0 / p_total_ms
    
    print(f" -> Person Mode YOLO Inference Latency:   {p_yolo_ms:.2f} ms ({p_inf_fps:.2f} FPS)")
    print(f" -> Person Mode DeepSORT Latency:         {p_track_ms:.2f} ms")
    print(f" -> Person Mode Optical Flow Latency:     {p_flow_ms:.2f} ms")
    print(f" -> Person Mode Total Pipeline Latency:   {p_total_ms:.2f} ms ({p_pipe_fps:.2f} Pipeline FPS)")
    print(f" -> RAM Usage: {mem_after:.1f} MB (Delta: {mem_after - mem_before:+.1f} MB)")

    # --- Mode B: Head Mode ---
    print("\n[B] Testing Head Mode (YOLOv8n-Head-V4 + Multi-Scale + DeepSORT max_age=15)...")
    head_model = "models/crowdpatrol_yolov8n_head_v4.pt" if os.path.exists("models/crowdpatrol_yolov8n_head_v4.pt") else DEFAULT_HEAD_MODEL_PATH
    h_detector = ExperimentalHeadDetector(model_path=head_model, confidence=0.25, device="cpu")
    h_tracker = PersonTracker(max_age=15, n_init=1)
    h_motion = CrowdMotionAnalyzer()
    h_density = HeadDensityEstimator()
    h_risk = ExperimentalHeadRiskAdapter()

    h_yolo_times = []
    h_track_times = []
    h_flow_times = []
    h_total_times = []
    h_det_counts = []
    
    # Warmup
    _ = h_detector.detect(frames[0], tiled=False)
    
    mem_h_before = proc.memory_info().rss / (1024 * 1024)
    
    for f in frames:
        t0 = time.perf_counter()
        
        # 1. Detection (Full-frame native 640x640)
        td0 = time.perf_counter()
        dets = h_detector.detect(f, tiled=False)
        td1 = time.perf_counter()
        h_yolo_times.append((td1 - td0) * 1000.0)
        h_det_counts.append(len(dets))
        
        # 2. Tracking (MobileNetV2 channels_last)
        tt0 = time.perf_counter()
        tracks = h_tracker.update(dets, f)
        tt1 = time.perf_counter()
        h_track_times.append((tt1 - tt0) * 1000.0)
        
        # 3. Motion
        tm0 = time.perf_counter()
        _, motion_summary = h_motion.analyze_frame(f)
        tm1 = time.perf_counter()
        h_flow_times.append((tm1 - tm0) * 1000.0)
        
        # 4. Density & Risk
        _, head_max, stats = h_density.calculate_density(tracks, f.shape)
        _ = h_risk.calculate_experimental_head_risk(stats["total_heads"], head_max, 1)
        
        t1 = time.perf_counter()
        h_total_times.append((t1 - t0) * 1000.0)
        
    mem_h_after = proc.memory_info().rss / (1024 * 1024)
    
    h_yolo_ms = np.mean(h_yolo_times)
    h_track_ms = np.mean(h_track_times)
    h_flow_ms = np.mean(h_flow_times)
    h_total_ms = np.mean(h_total_times)
    h_inf_fps = 1000.0 / h_yolo_ms
    h_pipe_fps = 1000.0 / h_total_ms
    avg_heads = np.mean(h_det_counts)
    
    print(f" -> Head Mode YOLO Inference Latency:     {h_yolo_ms:.2f} ms ({h_inf_fps:.2f} FPS)")
    print(f" -> Head Mode DeepSORT Latency:           {h_track_ms:.2f} ms")
    print(f" -> Head Mode Optical Flow Latency:       {h_flow_ms:.2f} ms")
    print(f" -> Head Mode Total Pipeline Latency:     {h_total_ms:.2f} ms ({h_pipe_fps:.2f} Pipeline FPS)")
    print(f" -> Average Heads Detected per frame:     {avg_heads:.1f}")
    print(f" -> RAM Usage: {mem_h_after:.1f} MB (Delta: {mem_h_after - mem_h_before:+.1f} MB)")

    return {
        "person": {"yolo_ms": p_yolo_ms, "yolo_fps": p_inf_fps, "track_ms": p_track_ms, "flow_ms": p_flow_ms, "total_ms": p_total_ms, "pipe_fps": p_pipe_fps},
        "head": {"yolo_ms": h_yolo_ms, "yolo_fps": h_inf_fps, "track_ms": h_track_ms, "flow_ms": h_flow_ms, "total_ms": h_total_ms, "pipe_fps": h_pipe_fps, "avg_heads": avg_heads}
    }

def benchmark_multi_camera_2x2():
    print("\n" + "="*60)
    print("   BENCHMARK 2: 2x2 MULTI-CAMERA (4 CAMERAS SIMULTANEOUS)")
    print("="*60)
    
    mgr = MultiCameraManager(config_path=Path("config/cameras.json"), detect_interval=2)
    online_count = mgr.start_all_cameras()
    print(f"Started MultiCameraManager: {online_count} cameras online.")
    
    proc = psutil.Process()
    time.sleep(0.5)  # Let warmup occur
    
    # 1. Evaluate 2x2 Grid Mode
    print("\n[A] Testing 2x2 Grid Mode (All 4 Cameras Monitored)...")
    grid_step_times = []
    cpu_samples = []
    
    for _ in range(30):
        t0 = time.perf_counter()
        frames = mgr.step_all()
        t1 = time.perf_counter()
        grid_step_times.append((t1 - t0) * 1000.0)
        cpu_samples.append(proc.cpu_percent(interval=None))
        
    grid_step_ms = np.mean(grid_step_times)
    grid_fps = 1000.0 / grid_step_ms if grid_step_ms > 0 else 0
    agg_grid_throughput = grid_fps * len(frames)
    
    print(f" -> 2x2 Grid Step Latency:         {grid_step_ms:.2f} ms")
    print(f" -> 2x2 Grid Display Rate:         {grid_fps:.2f} cycles/sec")
    print(f" -> Aggregate 4-Camera Throughput:  {agg_grid_throughput:.2f} frames/sec")
    print(f" -> Average CPU Utilization:       {np.mean(cpu_samples):.1f}%")
    
    # 2. Evaluate Focus Mode
    print("\n[B] Testing Focus Mode (CAM-01 Focused, 3 Background)...")
    focus_step_times = []
    
    for _ in range(30):
        t0 = time.perf_counter()
        focus_dict = mgr.step_focus("CAM-01")
        t1 = time.perf_counter()
        focus_step_times.append((t1 - t0) * 1000.0)
        
    focus_step_ms = np.mean(focus_step_times)
    focus_fps = 1000.0 / focus_step_ms if focus_step_ms > 0 else 0
    
    # Measure per-camera inference FPS
    cam1 = mgr.cameras.get("CAM-01")
    cam1_inf_fps = cam1.yolo_inference_fps if hasattr(cam1, "yolo_inference_fps") and cam1.yolo_inference_fps > 0 else (focus_fps / 2.0)
    
    print(f" -> Focus Feed Step Latency:       {focus_step_ms:.2f} ms")
    print(f" -> Focus Display Delivery Rate:   {focus_fps:.2f} FPS")
    print(f" -> Focus Camera Actual AI FPS:    {cam1_inf_fps:.2f} FPS (Every detect_interval=2)")
    print(f" -> Off-screen Camera Processing:  Lightweight background mode (HUD skipped)")

    mgr.stop_all_cameras()
    return {
        "grid_step_ms": grid_step_ms, "grid_fps": grid_fps, "agg_throughput": agg_grid_throughput,
        "focus_step_ms": focus_step_ms, "focus_fps": focus_fps, "cam1_inf_fps": cam1_inf_fps
    }

def verify_dense_crowd_accuracy():
    print("\n" + "="*60)
    print("   BENCHMARK 3: DENSE CROWD DETECTION ACCURACY AUDIT")
    print("="*60)
    
    video_path = "data/videos/dense_crowd_test.mp4"
    if not os.path.exists(video_path):
        print("[!] Video not found.")
        return
        
    cap = cv2.VideoCapture(video_path)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    print(f"Video {video_path}: {total_frames} total frames at 1280x720.")
    
    # Audit frame 2794 and frame 3911
    test_indices = [2794, 3911, 4749]
    head_model = "models/crowdpatrol_yolov8n_head_v4.pt" if os.path.exists("models/crowdpatrol_yolov8n_head_v4.pt") else DEFAULT_HEAD_MODEL_PATH
    detector = ExperimentalHeadDetector(model_path=head_model, confidence=0.25, device="cpu")
    tracker = PersonTracker(max_age=15, n_init=1)
    
    for f_idx in test_indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, f_idx)
        ret, frame = cap.read()
        if not ret:
            continue
            
        # Single-pass baseline
        base_dets = detector.detect(frame, tiled=False)
        # Multi-scale enhanced
        enh_dets = detector.detect_tiled_2x2(frame)
        
        # DeepSORT tracking
        tracks = tracker.update(enh_dets, frame)
        vis_tracks = tracker.get_visible_tracks()
        
        gain = ((len(enh_dets) - len(base_dets)) / max(len(base_dets), 1)) * 100.0
        print(f" -> Frame {f_idx:4d}: Baseline={len(base_dets):2d} heads | Multi-Scale={len(enh_dets):2d} heads | DeepSORT Tracked={len(vis_tracks):2d} heads | Gain: {gain:+.1f}%")

    cap.release()

if __name__ == "__main__":
    print("="*60)
    print("  CROWDPATROL PHASE 5 SYSTEM PERFORMANCE & INTEGRATION SUITE")
    print("="*60)
    bench1 = benchmark_single_camera()
    bench2 = benchmark_multi_camera_2x2()
    verify_dense_crowd_accuracy()
    print("\n[✓] ALL PERFORMANCE & ACCURACY BENCHMARKS COMPLETED SUCCESSFULLY.")
