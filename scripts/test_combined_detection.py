"""
Test Combined Full-Frame + Tiled inference with Global NMS vs Individual Modes.
"""

import sys
import cv2
import numpy as np
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
sys.path.append(str(BASE_DIR))

from src.experimental_head_mode import ExperimentalHeadDetector, DEFAULT_HEAD_MODEL_PATH, nms_cpu

def test_combined():
    detector = ExperimentalHeadDetector(model_path=DEFAULT_HEAD_MODEL_PATH, confidence=0.25, device="cpu", imgsz=640)
    cap = cv2.VideoCapture("data/videos/dense_crowd_test.mp4")
    
    frames_to_test = [465, 2790, 3255, 3720, 4650]
    
    for f_id in frames_to_test:
        cap.set(cv2.CAP_PROP_POS_FRAMES, f_id)
        ret, frame = cap.read()
        if not ret:
            continue
            
        h, w = frame.shape[:2]
        
        # 1. Full frame detections
        full_dets = detector.detect_full_frame(frame)
        
        # 2. Tiled detections
        tiled_dets = detector.detect_tiled_2x2(frame)
        
        # 3. Combined Full + Tiled
        all_boxes = []
        all_scores = []
        
        # Add full frame
        for d in full_dets:
            x, y, bw, bh = d[0]
            all_boxes.append([x, y, x + bw, y + bh])
            all_scores.append(d[1])
            
        # Add tiled
        for d in tiled_dets:
            x, y, bw, bh = d[0]
            all_boxes.append([x, y, x + bw, y + bh])
            all_scores.append(d[1])
            
        keep = nms_cpu(all_boxes, all_scores, iou_threshold=0.50)
        combined_count = len(keep)
        
        print(f"Frame {f_id:4d} | Full-Frame: {len(full_dets):2d} | Tiled-Only: {len(tiled_dets):2d} | COMBINED (Full+Tiled): {combined_count:2d}")
        
    cap.release()

if __name__ == "__main__":
    test_combined()
