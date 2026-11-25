"""
Deep profiling script to isolate bottlenecks in YOLOv8, DeepSORT, MobileNetV2, and optical flow.
"""

import sys
import time
import cv2
import torch
import numpy as np
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
sys.path.append(str(BASE_DIR))

from src.experimental_head_mode import ExperimentalHeadDetector, DEFAULT_HEAD_MODEL_PATH
from src.tracking import PersonTracker
from src.motion_analysis import CrowdMotionAnalyzer

def profile():
    print(f"PyTorch Version: {torch.__version__}")
    print(f"PyTorch Num Threads: {torch.get_num_threads()}")
    
    cap = cv2.VideoCapture("data/videos/dense_crowd_test.mp4")
    # Advance to a dense frame
    cap.set(cv2.CAP_PROP_POS_FRAMES, 2790)
    ret, frame = cap.read()
    cap.release()
    
    if not ret:
        print("Failed to read frame")
        return
        
    print(f"Frame shape: {frame.shape}")
    
    detector = ExperimentalHeadDetector(model_path=DEFAULT_HEAD_MODEL_PATH, confidence=0.25, device="cpu", imgsz=640)
    tracker = PersonTracker(max_age=15, n_init=1)
    motion_analyzer = CrowdMotionAnalyzer(grid_size=(4, 4), flow_interval=2)
    
    # Warmup
    for _ in range(3):
        dets = detector.detect_full_frame(frame)
        _ = tracker.update(dets, frame)
        _ = motion_analyzer.analyze_frame(frame)
        
    # 1. Profile YOLOv8 Full Frame
    times_yolo = []
    for _ in range(15):
        t0 = time.perf_counter()
        dets = detector.detect_full_frame(frame)
        times_yolo.append((time.perf_counter() - t0) * 1000)
    print(f"YOLOv8 detect_full_frame: mean={np.mean(times_yolo):.2f} ms (min={np.min(times_yolo):.2f} ms)")
    print(f"Detections count: {len(dets)}")
    
    # 2. Profile DeepSORT with MobileNetV2
    times_tracker = []
    for _ in range(15):
        t0 = time.perf_counter()
        tracks = tracker.update(dets, frame)
        times_tracker.append((time.perf_counter() - t0) * 1000)
    print(f"DeepSORT update_tracks ({len(dets)} crops): mean={np.mean(times_tracker):.2f} ms (min={np.min(times_tracker):.2f} ms)")
    
    # 3. Profile MobileNetV2 embedder standalone
    crops = [frame[max(0, int(d[0][1])):int(d[0][1]+d[0][3]), max(0, int(d[0][0])):int(d[0][0]+d[0][2])] for d in dets]
    times_embed = []
    for _ in range(15):
        t0 = time.perf_counter()
        _ = tracker.tracker.embedder.predict(crops)
        times_embed.append((time.perf_counter() - t0) * 1000)
    print(f"MobileNetV2 embedder standalone ({len(crops)} crops): mean={np.mean(times_embed):.2f} ms (min={np.min(times_embed):.2f} ms)")
    
    # 4. Profile Optical Flow
    times_flow = []
    for _ in range(15):
        t0 = time.perf_counter()
        _ = motion_analyzer.analyze_frame(frame)
        times_flow.append((time.perf_counter() - t0) * 1000)
    print(f"Farneback Optical Flow: mean={np.mean(times_flow):.2f} ms (min={np.min(times_flow):.2f} ms)")
    
    # 5. Thread count experiments
    print("\n--- Thread Count Experiments for YOLOv8 & MobileNetV2 ---")
    orig_threads = torch.get_num_threads()
    for th in [2, 4, 6, 8, 12, 14, 20]:
        torch.set_num_threads(th)
        t_y = []
        for _ in range(5):
            t0 = time.perf_counter()
            _ = detector.detect_full_frame(frame)
            t_y.append((time.perf_counter() - t0) * 1000)
        t_e = []
        for _ in range(5):
            t0 = time.perf_counter()
            _ = tracker.tracker.embedder.predict(crops)
            t_e.append((time.perf_counter() - t0) * 1000)
        print(f"Threads={th:2d}: YOLO={np.mean(t_y):.1f} ms | MobileNetV2({len(crops)} crops)={np.mean(t_e):.1f} ms | Sum={np.mean(t_y)+np.mean(t_e):.1f} ms")
    torch.set_num_threads(orig_threads)

if __name__ == "__main__":
    profile()
