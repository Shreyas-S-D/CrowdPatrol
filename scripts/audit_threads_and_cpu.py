"""
CrowdPatrol Phase 11.1 — CPU & Thread Contention Audit
Measures inference latency, aggregate throughput, CPU%, and RAM across thread counts.
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


def test_thread_allocation(threads_list=[2, 4, 6, 8, 10, 14], num_frames=20):
    proc = psutil.Process()
    print("=" * 70)
    print("THREAD CONTENTION & OVERSUBSCRIPTION AUDIT (4-CAMERA 2x2 GRID)")
    print("=" * 70)
    print(f"Physical CPU Cores: {psutil.cpu_count(logical=False)} | Logical Processors: {psutil.cpu_count(logical=True)}")

    results = []

    for th in threads_list:
        torch.set_num_threads(th)
        cv2.setNumThreads(th)
        
        mcm = MultiCameraManager(
            detection_mode="PERSON",
            device="cpu",
            detect_interval=3,
            flow_interval=2,
            yolo_imgsz=640
        )
        mcm.start_all_cameras()

        # Warmup 3 frames
        for _ in range(3):
            mcm.step_all()

        # Measure steady-state
        proc.cpu_percent()
        mem_before = proc.memory_info().rss / (1024 * 1024)
        t_start = time.perf_counter()

        for _ in range(num_frames):
            mcm.step_all()

        dur = time.perf_counter() - t_start
        cpu_pct = proc.cpu_percent()
        mem_after = proc.memory_info().rss / (1024 * 1024)

        metrics = mcm.get_throughput_metrics()
        loop_fps = num_frames / dur
        yolo_fps = metrics.get("yolo_inference_fps", {})
        grid_fps = metrics.get("grid_display_fps", 0.0)

        mcm.stop_all_cameras()

        print(f"Threads: {th:2d} | Dur: {dur:5.2f}s ({loop_fps:4.2f} iter/s) | CPU: {cpu_pct:5.1f}% | RAM: {mem_after:6.1f}MB | YOLO FPS: {yolo_fps}")
        results.append((th, dur, loop_fps, cpu_pct, mem_after, yolo_fps))

    print("=" * 70)
    return results


if __name__ == "__main__":
    test_thread_allocation([2, 4, 6, 8, 10, 14], num_frames=20)
