import os
from pathlib import Path
from ultralytics import YOLO
import cv2
import torch
import numpy as np

DEFAULT_MODEL_PATH = "models/crowdpatrol_yolov8n_finetuned_v2.pt" if os.path.exists("models/crowdpatrol_yolov8n_finetuned_v2.pt") else "yolov8n.pt"

class PersonDetector:
    def __init__(self, model_path=None, confidence=0.35, device="cpu", imgsz=640):
        if model_path is None:
            model_path = DEFAULT_MODEL_PATH
        self.model_path = str(model_path)
        self.model = YOLO(self.model_path)
        self.confidence = confidence
        self.device = device
        self.imgsz = imgsz
        self.class_ids = [0]  # COCO: 0 = person

        # Fallback to standard COCO weights if fine-tuned aerial model misses close-up webcam framing
        self._coco_fallback = None
        if "finetuned" in self.model_path.lower():
            for candidate in ["yolov8n.pt", str(Path(__file__).resolve().parent.parent / "yolov8n.pt")]:
                if os.path.exists(candidate):
                    try:
                        self._coco_fallback = YOLO(candidate)
                        break
                    except Exception:
                        pass
    
    def detect(self, frame):
        with torch.inference_mode():
            results = self.model(frame, imgsz=self.imgsz, device=self.device, verbose=False)[0]
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
        
        # If fine-tuned aerial model detected 0 persons (e.g. close-up webcam view), fallback to standard COCO person weights
        if len(detections) == 0 and self._coco_fallback is not None:
            with torch.inference_mode():
                fb_results = self._coco_fallback(frame, imgsz=self.imgsz, device=self.device, verbose=False)[0]
            for box in fb_results.boxes:
                if int(box.cls) in self.class_ids and float(box.conf) >= self.confidence:
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    conf = float(box.conf)
                    cls = int(box.cls)
                    w = x2 - x1
                    h = y2 - y1
                    detections.append(([x1, y1, w, h], conf, cls))

        return detections

    def detect_batch(self, frames):
        """Perform batched multi-frame YOLO inference in a single forward pass."""
        if not frames:
            return []
        with torch.inference_mode():
            results = self.model(frames, imgsz=self.imgsz, device=self.device, verbose=False)
        batch_detections = []
        for res in results:
            dets = []
            for box in res.boxes:
                if int(box.cls) in self.class_ids and float(box.conf) >= self.confidence:
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    conf = float(box.conf)
                    cls = int(box.cls)
                    w = x2 - x1
                    h = y2 - y1
                    dets.append(([x1, y1, w, h], conf, cls))
            batch_detections.append(dets)
        return batch_detections