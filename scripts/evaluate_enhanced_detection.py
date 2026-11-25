"""
Evaluate Enhanced Head Detection: CLAHE + Batched Sliced Inference + Global NMS.
"""

import sys
import time
import cv2
import numpy as np
import torch
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
sys.path.append(str(BASE_DIR))

from src.experimental_head_mode import ExperimentalHeadDetector, DEFAULT_HEAD_MODEL_PATH, nms_cpu
from src.tracking import PersonTracker

def apply_clahe(img):
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    cl = clahe.apply(l)
    return cv2.cvtColor(cv2.merge((cl, a, b)), cv2.COLOR_LAB2BGR)

def evaluate():
    detector = ExperimentalHeadDetector(model_path=DEFAULT_HEAD_MODEL_PATH, confidence=0.25, device="cpu", imgsz=640)
    tracker = PersonTracker(max_age=15, n_init=1)
    
    print("=" * 70)
    print("EVALUATING ENHANCED DENSE CROWD DETECTION")
    print("=" * 70)
    
    for video_name in ["data/videos/dense_crowd_test.mp4", "data/videos/youtube_crowd_test.mp4"]:
        cap = cv2.VideoCapture(video_name)
        total_f = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        sample_frames = [int(total_f * r) for r in [0.1, 0.25, 0.5, 0.7, 0.85]]
        
        print(f"\nVideo: {video_name}")
        for fid in sample_frames:
            cap.set(cv2.CAP_PROP_POS_FRAMES, fid)
            ret, frame = cap.read()
            if not ret: continue
            
            # Baseline: Standard Full Frame (conf >= 0.25)
            dets_base = detector.detect_full_frame(frame)
            
            # Enhanced: CLAHE + Batched Combined Sliced Inference
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
            
            # Batch: 1 full-frame + 4 tiles
            frame_enhanced = apply_clahe(frame)
            batch = [frame_enhanced] + [frame_enhanced[y1:y2, x1:x2] for (x1, y1, x2, y2) in tiles_offsets]
            
            with torch.inference_mode():
                results = detector.model(batch, imgsz=640, conf=0.25, device="cpu", verbose=False)
                
            all_boxes = []
            all_scores = []
            
            # 1. Full-frame boxes
            for box in results[0].boxes:
                if int(box.cls) == 0 and float(box.conf) >= 0.25:
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    all_boxes.append([x1, y1, x2, y2])
                    all_scores.append(float(box.conf))
                    
            # 2. Tile boxes with coordinate offsets
            for t_idx, (ox1, oy1, ox2, oy2) in enumerate(tiles_offsets):
                t_res = results[t_idx + 1]
                for box in t_res.boxes:
                    if int(box.cls) == 0 and float(box.conf) >= 0.25:
                        tx1, ty1, tx2, ty2 = box.xyxy[0].tolist()
                        all_boxes.append([ox1 + tx1, oy1 + ty1, ox1 + tx2, oy1 + ty2])
                        all_scores.append(float(box.conf))
                        
            keep = nms_cpu(all_boxes, all_scores, iou_threshold=0.50)
            enhanced_dets = []
            for k in keep:
                b = all_boxes[k]
                enhanced_dets.append(([b[0], b[1], b[2] - b[0], b[3] - b[1]], all_scores[k], 0))
                
            # DeepSORT tracking on enhanced detections
            tracks = tracker.update(enhanced_dets, frame)
            vis_tracks = tracker.get_visible_tracks()
            
            print(f"Frame {fid:4d} | Baseline: {len(dets_base):2d} heads | Raw Dets: {len(all_boxes):2d} | Enhanced (Post-NMS): {len(enhanced_dets):2d} heads | Tracked: {len(vis_tracks):2d} tracks")
            
        cap.release()

if __name__ == "__main__":
    evaluate()
