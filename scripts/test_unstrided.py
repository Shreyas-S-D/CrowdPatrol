"""
Test Focus Feed YOLO inference FPS with dedicated detect_interval (unstrided by background cams).
"""

import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
sys.path.append(str(BASE_DIR))

from src.multi_camera_manager import MultiCameraManager

def test_unstrided():
    mgr = MultiCameraManager(device="cpu", detect_interval=2, stagger_detections=False)
    mgr.start_all_cameras()
    
    # Warmup
    for _ in range(5):
        mgr.step_focus("CAM-01", step_background=True)
        
    t0 = time.perf_counter()
    cycles = 30
    for _ in range(cycles):
        mgr.step_focus("CAM-01", step_background=True)
    t_tot = time.perf_counter() - t0
    
    cam1 = mgr.cameras["CAM-01"]
    metrics = mgr.get_throughput_metrics()
    
    print(f"Cycles: {cycles} in {t_tot:.2f}s ({cycles/t_tot:.2f} cycles/s)")
    print(f"CAM-01 Display FPS: {cam1.fps:.2f}")
    print(f"CAM-01 Actual YOLO Inferences: {cam1.yolo_inferences_count}")
    print(f"CAM-01 Actual YOLO Inference FPS: {cam1.yolo_inference_fps:.2f}")
    print(f"Aggregate System Throughput: {metrics['aggregate_throughput_fps']:.2f} frames/sec")
    
    mgr.stop_all_cameras()

if __name__ == "__main__":
    test_unstrided()
