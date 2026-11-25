"""
Test batched 2x2 tiled inference in Ultralytics YOLO.
"""

import sys
import time
import cv2
import numpy as np
import torch
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
sys.path.append(str(BASE_DIR))

from src.experimental_head_mode import ExperimentalHeadDetector, DEFAULT_HEAD_MODEL_PATH

def test_batched_tiling():
    detector = ExperimentalHeadDetector(model_path=DEFAULT_HEAD_MODEL_PATH, confidence=0.25, device="cpu", imgsz=640)
    
    cap = cv2.VideoCapture("data/videos/dense_crowd_test.mp4")
    cap.set(cv2.CAP_PROP_POS_FRAMES, 2790)
    ret, frame = cap.read()
    cap.release()
    
    # Sequential 4-call tiling
    for _ in range(2):
        _ = detector.detect_tiled_2x2(frame)
        
    t_seq = []
    for _ in range(10):
        t0 = time.perf_counter()
        dets_seq = detector.detect_tiled_2x2(frame)
        t_seq.append((time.perf_counter() - t0) * 1000)
    print(f"Sequential 4-call Tiled: {np.mean(t_seq):.2f} ms | Detections: {len(dets_seq)}")
    
    # Batched 1-call tiling
    h, w = frame.shape[:2]
    overlap = 0.15
    tile_w = int(w * (0.5 + overlap / 2))
    tile_h = int(h * (0.5 + overlap / 2))
    tiles_offsets = [
        (0, 0, tile_w, tile_h),
        (w - tile_w, 0, w, tile_h),
        (0, h - tile_h, tile_w, h),
        (w - tile_w, h - tile_h, w, h)
    ]
    
    tile_crops = [frame[y_min:y_max, x_min:x_max] for (x_min, y_min, x_max, y_max) in tiles_offsets]
    
    t_batch = []
    for _ in range(10):
        t0 = time.perf_counter()
        with torch.inference_mode():
            batch_results = detector.model(tile_crops, imgsz=detector.imgsz, conf=detector.confidence, device=detector.device, verbose=False)
        t_batch.append((time.perf_counter() - t0) * 1000)
    print(f"Batched 1-call Tiled YOLO forward: {np.mean(t_batch):.2f} ms")

if __name__ == "__main__":
    test_batched_tiling()
