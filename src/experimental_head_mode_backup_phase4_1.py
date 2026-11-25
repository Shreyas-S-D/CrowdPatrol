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

def nms_cpu(boxes, scores, iou_threshold=0.45):
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
        
    def detect_full_frame(self, frame):
        """Standard full-frame YOLO inference."""
        results = self.model(frame, imgsz=self.imgsz, conf=self.confidence, device=self.device, verbose=False)[0]
        detections = []
        
        for box in results.boxes:
            if int(box.cls) == 0 and float(box.conf) >= self.confidence:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                conf = float(box.conf)
                w = x2 - x1
                h = y2 - y1
                detections.append(([x1, y1, w, h], conf, 0))
                
        return detections

    def detect_tiled_2x2(self, frame, overlap=0.15):
        """2x2 Spatial tiled inference for micro head feature detection."""
        h, w = frame.shape[:2]
        tile_w = int(w * (0.5 + overlap / 2))
        tile_h = int(h * (0.5 + overlap / 2))
        
        tiles_offsets = [
            (0, 0, tile_w, tile_h),
            (w - tile_w, 0, w, tile_h),
            (0, h - tile_h, tile_w, h),
            (w - tile_w, h - tile_h, w, h)
        ]
        
        all_boxes = []
        all_scores = []
        
        for (x_min, y_min, x_max, y_max) in tiles_offsets:
            tile_crop = frame[y_min:y_max, x_min:x_max]
            results = self.model(tile_crop, imgsz=self.imgsz, conf=self.confidence, device=self.device, verbose=False)[0]
            
            for box in results.boxes:
                if int(box.cls) == 0 and float(box.conf) >= self.confidence:
                    tx1, ty1, tx2, ty2 = box.xyxy[0].tolist()
                    conf = float(box.conf)
                    
                    gx1 = x_min + tx1
                    gy1 = y_min + ty1
                    gx2 = x_min + tx2
                    gy2 = y_min + ty2
                    
                    all_boxes.append([gx1, gy1, gx2, gy2])
                    all_scores.append(conf)
                    
        keep_indices = nms_cpu(all_boxes, all_scores, iou_threshold=0.45)
        
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
