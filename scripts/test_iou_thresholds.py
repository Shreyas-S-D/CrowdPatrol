"""
Test NMS IoU threshold effects on dense crowd frames.
"""

import sys
import cv2
import numpy as np
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
sys.path.append(str(BASE_DIR))

from src.experimental_head_mode import ExperimentalHeadDetector, DEFAULT_HEAD_MODEL_PATH

def test_iou_thresholds():
    detector = ExperimentalHeadDetector(model_path=DEFAULT_HEAD_MODEL_PATH, confidence=0.25, device="cpu", imgsz=640)
    
    cap = cv2.VideoCapture("data/videos/dense_crowd_test.mp4")
    
    for frame_id in [465, 2790, 3720, 4650]:
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_id)
        ret, frame = cap.read()
        if not ret:
            continue
            
        print(f"\n--- Frame {frame_id} ---")
        full_dets = detector.detect_full_frame(frame)
        print(f"Full Frame (conf>=0.25): {len(full_dets)} heads")
        
        # Test tiled with different IoU thresholds
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
        batch_results = detector.model(tile_crops, imgsz=detector.imgsz, conf=detector.confidence, device=detector.device, verbose=False)
        
        all_boxes = []
        all_scores = []
        for idx, (x_min, y_min, x_max, y_max) in enumerate(tiles_offsets):
            res = batch_results[idx]
            for box in res.boxes:
                if int(box.cls) == 0 and float(box.conf) >= detector.confidence:
                    tx1, ty1, tx2, ty2 = box.xyxy[0].tolist()
                    all_boxes.append([x_min + tx1, y_min + ty1, x_min + tx2, y_min + ty2])
                    all_scores.append(float(box.conf))
                    
        print(f"Raw Tiled Detections before NMS: {len(all_boxes)}")
        
        from src.experimental_head_mode import nms_cpu
        for iou in [0.40, 0.45, 0.50, 0.55, 0.60]:
            keep = nms_cpu(all_boxes, all_scores, iou_threshold=iou)
            print(f"  NMS iou={iou:.2f}: {len(keep)} retained heads")
            
    cap.release()

if __name__ == "__main__":
    test_iou_thresholds()
