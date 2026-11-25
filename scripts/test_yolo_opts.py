"""
Test YOLOv8 with torch.inference_mode and channels-last memory format on CPU.
"""

import sys
import time
import torch
import numpy as np
import cv2
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
sys.path.append(str(BASE_DIR))

from src.experimental_head_mode import ExperimentalHeadDetector, DEFAULT_HEAD_MODEL_PATH

def test_yolo_opts():
    detector = ExperimentalHeadDetector(model_path=DEFAULT_HEAD_MODEL_PATH, confidence=0.25, device="cpu", imgsz=640)
    
    cap = cv2.VideoCapture("data/videos/dense_crowd_test.mp4")
    cap.set(cv2.CAP_PROP_POS_FRAMES, 2790)
    ret, frame = cap.read()
    cap.release()
    
    # 1. Standard full frame
    for _ in range(3):
        _ = detector.detect_full_frame(frame)
        
    t_std = []
    for _ in range(15):
        t0 = time.perf_counter()
        dets1 = detector.detect_full_frame(frame)
        t_std.append((time.perf_counter() - t0) * 1000)
    print(f"Standard YOLOv8: {np.mean(t_std):.2f} ms")
    
    # 2. Inside torch.inference_mode()
    t_inf = []
    for _ in range(15):
        t0 = time.perf_counter()
        with torch.inference_mode():
            dets2 = detector.detect_full_frame(frame)
        t_inf.append((time.perf_counter() - t0) * 1000)
    print(f"YOLOv8 inside torch.inference_mode: {np.mean(t_inf):.2f} ms")
    
    # 3. Channels Last on YOLO model
    try:
        detector.model.model.to(memory_format=torch.channels_last)
        t_cl = []
        for _ in range(15):
            t0 = time.perf_counter()
            with torch.inference_mode():
                dets3 = detector.detect_full_frame(frame)
            t_cl.append((time.perf_counter() - t0) * 1000)
        print(f"YOLOv8 Channels-Last: {np.mean(t_cl):.2f} ms")
        print(f"Detections match: count1={len(dets1)}, count3={len(dets3)}")
    except Exception as e:
        print(f"Channels last error: {e}")

if __name__ == "__main__":
    test_yolo_opts()
