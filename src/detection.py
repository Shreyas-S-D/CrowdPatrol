import os
from pathlib import Path
from ultralytics import YOLO
import cv2
import numpy as np

DEFAULT_MODEL_PATH = "models/crowdpatrol_yolov8n_finetuned_v2.pt" if os.path.exists("models/crowdpatrol_yolov8n_finetuned_v2.pt") else "yolov8n.pt"

class PersonDetector:
    def __init__(self, model_path=None, confidence=0.5, device="cpu"):
        if model_path is None:
            model_path = DEFAULT_MODEL_PATH
        self.model_path = model_path
        self.model = YOLO(model_path)
        self.confidence = confidence
        self.device = device
        self.class_ids = [0]  # COCO: 0 = person
    
    def detect(self, frame):
        results = self.model(frame, device=self.device, verbose=False)[0]
        detections = []
        
        for box in results.boxes:
            if int(box.cls) in self.class_ids and float(box.conf) >= self.confidence:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                conf = float(box.conf)
                cls = int(box.cls)

                # Convert to [x, y, w, h]
                w = x2 - x1
                h = y2 - y1

                detections.append(([x1, y1, w, h], conf, cls))
        
        return detections