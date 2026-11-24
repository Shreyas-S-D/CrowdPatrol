"""
CrowdPatrol Phase 4 — Experimental Head Mode Detector Module.
Isolated experimental module loading models/crowdpatrol_yolov8n_head_v4.pt.
Explicitly detects head bounding boxes (class 0 = head).
Supports both Full-Frame and 2x2 Spatial Tiling inference modes.

IMPORTANT: This is an experimental module for dense crowd research only.
Does NOT modify or replace production PersonDetector (V2).
"""

import os
import sys
import time
import cv2
import numpy as np
import torch
from pathlib import Path
from ultralytics import YOLO

BASE_DIR = Path(__file__).parent.parent
DEFAULT_HEAD_MODEL_PATH = str(BASE_DIR / "models" / "crowdpatrol_yolov8n_head_v4.pt")

def apply_clahe(img):
    """
    Adaptive histogram equalization in LAB color space.
    Enhances local contrast to reveal shadowed and low-contrast heads
    in dense outdoor/indoor crowds without altering input image geometry.
    """
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    cl = clahe.apply(l)
    return cv2.cvtColor(cv2.merge((cl, a, b)), cv2.COLOR_LAB2BGR)

def nms_cpu(boxes, scores, iou_threshold=0.50):
    if len(boxes) == 0:
        return []
    boxes = np.array(boxes)
    scores = np.array(scores)
    
    x1, y1, x2, y2 = boxes[:, 0], boxes[:, 1], boxes[:, 2], boxes[:, 3]
    areas = (x2 - x1) * (y2 - y1)
    order = scores.argsort()[::-1]
    keep = []
    
    while order.size > 0:
        i = order[0]
        keep.append(i)
        
        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])
        
        w = np.maximum(0.0, xx2 - xx1)
        h = np.maximum(0.0, yy2 - yy1)
        inter = w * h
        ovr = inter / (areas[i] + areas[order[1:]] - inter)
        inds = np.where(ovr <= iou_threshold)[0]
        order = order[inds + 1]
        
    return keep

class ExperimentalHeadDetector:
    """
    Experimental Head Detector for dense crowd monitoring.
    Outputs detections formatted as ([x, y, w, h], conf, cls) with class 0 = head.
    """
    def __init__(self, model_path=None, confidence=0.25, device="cpu", imgsz=640):
        if model_path is None:
            model_path = DEFAULT_HEAD_MODEL_PATH
        self.model_path = model_path
        self.model = YOLO(model_path)
        self.confidence = confidence
        self.device = device
        self.imgsz = imgsz
        self.target_type = "head"  # Explicit target type
        
    def detect_full_frame(self, frame, enhance_contrast=True):
        """Standard full-frame YOLO inference with adaptive contrast preprocessing."""
        proc_frame = apply_clahe(frame) if enhance_contrast else frame
        with torch.inference_mode():
            results = self.model(proc_frame, imgsz=self.imgsz, conf=self.confidence, device=self.device, verbose=False)[0]
        detections = []
        
        for box in results.boxes:
            if int(box.cls) == 0 and float(box.conf) >= self.confidence:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                conf = float(box.conf)
                w = x2 - x1
                h = y2 - y1
                detections.append(([x1, y1, w, h], conf, 0))
                
        return detections

    def detect_tiled_2x2(self, frame, overlap=0.15, enhance_contrast=True):
        """
        Batched multi-scale sliced inference for micro head feature detection.
        Combines full-frame context (for large/central heads) with 4 localized quadrant tiles
        (for distant micro-heads) executed in a single batched tensor forward pass.
        Eliminates tile boundary slicing losses through unified global NMS.
        """
        h, w = frame.shape[:2]
        tile_w = int(w * (0.5 + overlap / 2))
        tile_h = int(h * (0.5 + overlap / 2))
        
        tiles_offsets = [
            (0, 0, tile_w, tile_h),
            (w - tile_w, 0, w, tile_h),
            (0, h - tile_h, tile_w, h),
            (w - tile_w, h - tile_h, w, h)
        ]
        
        proc_frame = apply_clahe(frame) if enhance_contrast else frame
        tile_crops = [proc_frame[y_min:y_max, x_min:x_max] for (x_min, y_min, x_max, y_max) in tiles_offsets]
        
        # Batch: 1 full-frame + 4 quadrant tiles in a single forward pass
        batch = [proc_frame] + tile_crops
        with torch.inference_mode():
            results = self.model(batch, imgsz=self.imgsz, conf=self.confidence, device=self.device, verbose=False)
            
        all_boxes = []
        all_scores = []
        
        # 1. Global Full-Frame Detections
        for box in results[0].boxes:
            if int(box.cls) == 0 and float(box.conf) >= self.confidence:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                all_boxes.append([x1, y1, x2, y2])
                all_scores.append(float(box.conf))
                
        # 2. Localized Tile Detections with Coordinate Offsets
        for t_idx, (ox1, oy1, ox2, oy2) in enumerate(tiles_offsets):
            t_res = results[t_idx + 1]
            for box in t_res.boxes:
                if int(box.cls) == 0 and float(box.conf) >= self.confidence:
                    tx1, ty1, tx2, ty2 = box.xyxy[0].tolist()
                    all_boxes.append([ox1 + tx1, oy1 + ty1, ox1 + tx2, oy1 + ty2])
                    all_scores.append(float(box.conf))
                    
        keep_indices = nms_cpu(all_boxes, all_scores, iou_threshold=0.50)
        
        detections = []
        for idx in keep_indices:
            box = all_boxes[idx]
            conf = all_scores[idx]
            w_b = box[2] - box[0]
            h_b = box[3] - box[1]
            detections.append(([box[0], box[1], w_b, h_b], conf, 0))
            
        return detections

    def detect(self, frame, tiled=False):
        if tiled:
            return self.detect_tiled_2x2(frame)
        else:
            return self.detect_full_frame(frame)
