"""
Benchmark script for CrowdPatrol Phase 4.1.
Measures Display FPS, Actual YOLO Inference FPS per camera, and Aggregate Throughput
in both 2x2 CCTV Grid Mode and Focus Feed Mode.
"""

import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
sys.path.append(str(BASE_DIR))

from src.multi_camera_manager import MultiCameraManager

def benchmark_modes():
    print("=" * 60)
    print("CROWDPATROL PHASE 4.1: PERFORMANCE BENCHMARK")
    print("=" * 60)
    
    # 1. 2x2 Grid Benchmark
    print("\n--- 1. Testing 2x2 CCTV Grid Mode (All 4 Feeds Active) ---")
    mgr_grid = MultiCameraManager(device="cpu", detect_interval=3)
    mgr_grid.start_all_cameras()
    
    t0 = time.perf_counter()
    for _ in range(40):
        mgr_grid.step_all()
    t1 = time.perf_counter()
    grid_duration = t1 - t0
    grid_loop_fps = 40.0 / grid_duration
    grid_metrics = mgr_grid.get_throughput_metrics()
    
    print(f"2x2 Grid Iteration Loop: {grid_loop_fps:.2f} iterations/sec ({grid_duration:.2f}s for 40 cycles)")
    print(f"Display FPS per Camera: {grid_metrics['display_fps']}")
    print(f"YOLO Inference FPS per Camera: {grid_metrics['yolo_inference_fps']}")
    print(f"Aggregate System Throughput: {grid_metrics['aggregate_throughput_fps']:.2f} frames/sec")
    mgr_grid.stop_all_cameras()
    
    # 2. Focus Feed Benchmark
    print("\n--- 2. Testing Focus Feed Mode (Focused CAM-01 + Background Surveillance) ---")
    mgr_focus = MultiCameraManager(device="cpu", detect_interval=3)
    mgr_focus.start_all_cameras()
    
    t0 = time.perf_counter()
    for _ in range(40):
        mgr_focus.step_focus("CAM-01", step_background=True)
    t1 = time.perf_counter()
    focus_duration = t1 - t0
    focus_loop_fps = 40.0 / focus_duration
    focus_metrics = mgr_focus.get_throughput_metrics()
    
    print(f"Focus Feed Iteration Loop: {focus_loop_fps:.2f} iterations/sec ({focus_duration:.2f}s for 40 cycles)")
    print(f"Display FPS per Camera: {focus_metrics['display_fps']}")
    print(f"YOLO Inference FPS per Camera: {focus_metrics['yolo_inference_fps']}")
    print(f"Aggregate System Throughput: {focus_metrics['aggregate_throughput_fps']:.2f} frames/sec")
    mgr_focus.stop_all_cameras()

if __name__ == "__main__":
    benchmark_modes()
