"""
Test preprocessing (e.g. CLAHE, histogram equalization) for head detection in dense crowds.
"""

import sys
import cv2
import numpy as np
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
sys.path.append(str(BASE_DIR))

from src.experimental_head_mode import ExperimentalHeadDetector, DEFAULT_HEAD_MODEL_PATH

def apply_clahe(img):
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    cl = clahe.apply(l)
    limg = cv2.merge((cl, a, b))
    return cv2.cvtColor(limg, cv2.COLOR_LAB2BGR)

def test_preprocessing():
    detector = ExperimentalHeadDetector(model_path=DEFAULT_HEAD_MODEL_PATH, confidence=0.25, device="cpu", imgsz=640)
    
    cap = cv2.VideoCapture("data/videos/dense_crowd_test.mp4")
    
    for f_id in [465, 2790, 3255, 3720, 4650]:
        cap.set(cv2.CAP_PROP_POS_FRAMES, f_id)
        ret, frame = cap.read()
        if not ret:
            continue
            
        # Standard
        dets_std = detector.detect_full_frame(frame)
        
        # With CLAHE
        frame_clahe = apply_clahe(frame)
        dets_clahe = detector.detect_full_frame(frame_clahe)
        
        print(f"Frame {f_id:4d} | Standard: {len(dets_std):2d} heads | CLAHE: {len(dets_clahe):2d} heads")
        
    cap.release()

if __name__ == "__main__":
    test_preprocessing()
