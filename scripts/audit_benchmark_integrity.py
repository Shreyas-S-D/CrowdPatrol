"""
CrowdPatrol Phase 11.1 — Benchmark Integrity Script
Separates cold model initialization, warm-up, and steady-state measurement phases.
"""

import sys
import time
import psutil
import torch
import cv2
import numpy as np
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
sys.path.append(str(BASE_DIR))

from src.multi_camera_manager import MultiCameraManager


def run_workload_audit(name, mode, op_mode, enabled_cams, num_frames=30, warmup_frames=5):
    proc = psutil.Process()
    
    # 1. Initialization phase
    t_init_0 = time.perf_counter()
    mcm = MultiCameraManager(
        detection_mode=mode,
        device="cpu",
        detect_interval=3,
        flow_interval=2,
        yolo_imgsz=640
    )
    for cid, cam in mcm.cameras.items():
        cam.enabled = (cid in enabled_cams)
    mcm.start_all_cameras()
    init_dur = (time.perf_counter() - t_init_0) * 1000

    # 2. Warm-up phase
    t_warmup_0 = time.perf_counter()
    for _ in range(warmup_frames):
        if op_mode == "FOCUS":
            mcm.step_focus("CAM-01", step_background=True)
        else:
            mcm.step_all()
    warmup_dur = (time.perf_counter() - t_warmup_0) * 1000

    # 3. Steady-state phase (Isolated measurement boundary)
    proc.cpu_percent()
    mem_before = proc.memory_info().rss / (1024 * 1024)
    t_steady_0 = time.perf_counter()

    for _ in range(num_frames):
        if op_mode == "FOCUS":
            mcm.step_focus("CAM-01", step_background=True)
        else:
            mcm.step_all()

    steady_dur = time.perf_counter() - t_steady_0
    cpu_pct = proc.cpu_percent()
    mem_after = proc.memory_info().rss / (1024 * 1024)

    metrics = mcm.get_throughput_metrics()
    grid_fps = metrics.get("grid_display_fps", 0.0)
    inf_fps = metrics.get("yolo_inference_fps", {})
    agg_fps = metrics.get("aggregate_throughput_fps", 0.0)
    loop_iter_fps = num_frames / steady_dur

    mcm.stop_all_cameras()

    print(f"\n[Audit] {name}")
    print(f"  Phase 1 - Model Init Latency:     {init_dur:.1f} ms")
    print(f"  Phase 2 - Warm-up Latency ({warmup_frames}f):   {warmup_dur:.1f} ms ({warmup_dur/warmup_frames:.1f} ms/frame)")
    print(f"  Phase 3 - Steady-State Duration:  {steady_dur:.2f} s ({num_frames} frames @ {loop_iter_fps:.2f} loop-iter/s)")
    print(f"  Telemetry Breakdown:")
    print(f"    - Actual YOLO Inference FPS:    {inf_fps}")
    print(f"    - Rolling Display / Grid FPS:   {grid_fps:.1f} FPS")
    print(f"    - Aggregate Frame Throughput:   {agg_fps:.1f} processed frames/sec")
    print(f"    - CPU Utilization:              {cpu_pct:.1f}%")
    print(f"    - Memory Footprint (Steady):    {mem_after:.1f} MB (delta: {mem_after - mem_before:+.1f} MB)")


if __name__ == "__main__":
    print("=" * 70)
    print("PHASE 11.1 BENCHMARK INTEGRITY AUDIT (STEADY-STATE ISOLATION)")
    print("=" * 70)
    run_workload_audit("Person Mode Focus Feed", "PERSON", "FOCUS", ["CAM-01"])
    run_workload_audit("Head Mode Focus Feed", "HEAD", "FOCUS", ["CAM-01"])
    run_workload_audit("Two-Camera Monitoring (CAM-01, CAM-02)", "PERSON", "GRID", ["CAM-01", "CAM-02"])
    run_workload_audit("Four-Camera 2x2 Grid (All Cameras)", "PERSON", "GRID", ["CAM-01", "CAM-02", "CAM-03", "CAM-04"])
    print("=" * 70)
