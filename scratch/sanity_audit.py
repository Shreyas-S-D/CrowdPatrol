"""
CrowdPatrol Dedicated Model Sanity Audit Script
Performs empirical inspection of:
1. Raw YOLO detections without DeepSORT on Bengaluru video frames
2. Confidence threshold sweep (0.25, 0.40, 0.50, 0.60)
3. Raw YOLO detections -> DeepSORT input -> Active tracks breakdown
4. CrowdHuman / synthetic preparation & label format audit
5. Baseline yolov8n.pt mAP 0.0007 root cause analysis
6. Duplicate box / IoU overlap audit
"""

import os
import sys
import cv2
import json
import numpy as np
from pathlib import Path
from ultralytics import YOLO

BASE_DIR = Path(__file__).parent.parent
sys.path.append(str(BASE_DIR))

from src.detection import PersonDetector
from src.tracking import PersonTracker
from src.utils import FrameAnnotator

VIS_DIR = BASE_DIR / "training" / "visualizations"
VIS_DIR.mkdir(parents=True, exist_ok=True)

BENGALURU_VIDEO = BASE_DIR / "data" / "videos" / "youtube_crowd_test.mp4"
BASELINE_MODEL = "yolov8n.pt"
FINETUNED_MODEL = str(BASE_DIR / "models" / "crowdpatrol_yolov8n_finetuned.pt")


def audit_raw_yolo_detections_on_bengaluru():
    """Task 1: Run raw YOLOv8 without DeepSORT on Bengaluru video frames and save annotated images."""
    print("\n==================================================")
    print("   TASK 1: RAW YOLO DETECTIONS AUDIT (NO DEEPSORT)")
    print("==================================================")
    
    cap = cv2.VideoCapture(str(BENGALURU_VIDEO))
    if not cap.isOpened():
        print(f"[!] Error opening {BENGALURU_VIDEO}")
        return
        
    base_model = YOLO(BASELINE_MODEL)
    fine_model = YOLO(FINETUNED_MODEL)
    
    target_frames = [10, 50, 100, 300, 500]
    frame_count = 0
    
    audit_results = {}
    
    while cap.isOpened() and frame_count < max(target_frames) + 1:
        ret, frame = cap.read()
        if not ret:
            break
        frame_count += 1
        
        if frame_count in target_frames:
            # Baseline predictions (conf=0.25)
            res_base = base_model(frame, conf=0.25, verbose=False)[0]
            boxes_base = res_base.boxes
            
            # Person class (cls=0) filtering for baseline
            person_boxes_base = [box for box in boxes_base if int(box.cls) == 0]
            
            # Fine-tuned predictions (conf=0.25)
            res_fine = fine_model(frame, conf=0.25, verbose=False)[0]
            boxes_fine = res_fine.boxes
            person_boxes_fine = [box for box in boxes_fine if int(box.cls) == 0]
            
            # Save annotated images
            img_base = frame.copy()
            for box in person_boxes_base:
                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                conf = float(box.conf)
                cv2.rectangle(img_base, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(img_base, f"p:{conf:.2f}", (x1, max(15, y1 - 5)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)
                            
            img_fine = frame.copy()
            for box in person_boxes_fine:
                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                conf = float(box.conf)
                cv2.rectangle(img_fine, (x1, y1), (x2, y2), (0, 0, 255), 1)
                
            path_base = VIS_DIR / f"bengaluru_baseline_frame_{frame_count:03d}.jpg"
            path_fine = VIS_DIR / f"bengaluru_finetuned_frame_{frame_count:03d}.jpg"
            
            cv2.imwrite(str(path_base), img_base)
            cv2.imwrite(str(path_fine), img_fine)
            
            # Record summary stats
            confs_base = [float(b.conf) for b in person_boxes_base]
            confs_fine = [float(b.conf) for b in person_boxes_fine]
            
            audit_results[f"frame_{frame_count}"] = {
                "baseline_count": len(person_boxes_base),
                "baseline_avg_conf": float(np.mean(confs_base)) if confs_base else 0.0,
                "finetuned_count": len(person_boxes_fine),
                "finetuned_avg_conf": float(np.mean(confs_fine)) if confs_fine else 0.0,
            }
            
            print(f"[*] Frame {frame_count:03d}:")
            print(f"    - Baseline YOLOv8n Detections: {len(person_boxes_base)} (Avg Conf: {audit_results[f'frame_{frame_count}']['baseline_avg_conf']:.2f})")
            print(f"    - Fine-Tuned YOLOv8n Detections: {len(person_boxes_fine)} (Avg Conf: {audit_results[f'frame_{frame_count}']['finetuned_avg_conf']:.2f})")

    cap.release()
    return audit_results


def audit_confidence_thresholds():
    """Task 2: Evaluate fine-tuned model at confidence thresholds 0.25, 0.40, 0.50, 0.60."""
    print("\n==================================================")
    print("   TASK 2: CONFIDENCE THRESHOLD SWEEP AUDIT")
    print("==================================================")
    
    cap = cv2.VideoCapture(str(BENGALURU_VIDEO))
    fine_model = YOLO(FINETUNED_MODEL)
    
    thresholds = [0.25, 0.40, 0.50, 0.60]
    frame_counts_by_thresh = {t: [] for t in thresholds}
    
    frame_idx = 0
    while cap.isOpened() and frame_idx < 30:
        ret, frame = cap.read()
        if not ret:
            break
        frame_idx += 1
        
        for t in thresholds:
            res = fine_model(frame, conf=t, verbose=False)[0]
            person_boxes = [box for box in res.boxes if int(box.cls) == 0]
            frame_counts_by_thresh[t].append(len(person_boxes))
            
    cap.release()
    
    print("[*] Average Detections/Frame across 30 frames at varying confidence thresholds:")
    sweep_summary = {}
    for t in thresholds:
        avg_cnt = float(np.mean(frame_counts_by_thresh[t]))
        sweep_summary[t] = round(avg_cnt, 1)
        print(f"    - Conf >= {t:.2f}: {avg_cnt:.1f} detections/frame")
        
    return sweep_summary


def audit_yolo_to_deepsort_breakdown():
    """Task 3: Report YOLO Detections -> DeepSORT Input -> Active Tracks per frame."""
    print("\n==================================================")
    print("   TASK 3: RAW YOLO vs DEEPSORT TRACKING BREAKDOWN")
    print("==================================================")
    
    cap = cv2.VideoCapture(str(BENGALURU_VIDEO))
    detector = PersonDetector(model_path=FINETUNED_MODEL, confidence=0.35, device="cpu")
    tracker = PersonTracker(max_age=30)
    
    breakdown_log = []
    
    frame_idx = 0
    while cap.isOpened() and frame_idx < 30:
        ret, frame = cap.read()
        if not ret:
            break
        frame_idx += 1
        
        # Raw YOLO predictions
        if frame_idx == 1 or frame_idx % 3 == 0:
            dets = detector.detect(frame)
            tracks = tracker.update(dets, frame)
            det_count = len(dets)
        else:
            tracks = tracker.predict()
            det_count = 0  # Skipped frame
            
        track_count = len(tracks)
        
        breakdown_log.append({
            "frame": frame_idx,
            "raw_yolo_detections": det_count,
            "active_deepsort_tracks": track_count
        })
        
        if frame_idx in [1, 3, 6, 9, 12, 15, 30]:
            print(f"[*] Frame {frame_idx:02d}: Raw YOLO Dets = {det_count:3d} | DeepSORT Active Tracks = {track_count:3d}")
            
    cap.release()
    return breakdown_log


def audit_baseline_map_root_cause():
    """Task 6 & Task 4: Investigate why stock yolov8n.pt got mAP 0.0007 on test split."""
    print("\n==================================================")
    print("   TASK 6 & 4: BASELINE mAP 0.0007 ROOT CAUSE AUDIT")
    print("==================================================")
    
    test_img_dir = BASE_DIR / "data" / "training" / "yolo" / "images" / "test"
    test_lbl_dir = BASE_DIR / "data" / "training" / "yolo" / "labels" / "test"
    
    base_model = YOLO(BASELINE_MODEL)
    
    test_images = list(test_img_dir.glob("*.jpg"))[:5]
    print(f"[*] Inspecting {len(test_images)} test split images and label files...")
    
    for img_file in test_images:
        lbl_file = test_lbl_dir / (img_file.stem + ".txt")
        
        # Read GT labels
        gt_boxes = []
        if lbl_file.exists():
            with open(lbl_file, 'r') as f:
                for line in f:
                    parts = line.strip().split()
                    if parts:
                        cls_id = int(parts[0])
                        xc, yc, w, h = map(float, parts[1:5])
                        gt_boxes.append((cls_id, xc, yc, w, h))
                        
        img = cv2.imread(str(img_file))
        h_img, w_img = img.shape[:2]
        
        # Stock YOLOv8n predictions
        res = base_model(img, conf=0.10, verbose=False)[0]
        pred_boxes = res.boxes
        
        person_preds = [b for b in pred_boxes if int(b.cls) == 0]
        other_preds = [b for b in pred_boxes if int(b.cls) != 0]
        
        print(f"\n[*] Image '{img_file.name}' ({w_img}x{h_img}):")
        print(f"    - GT Ground Truth Boxes: {len(gt_boxes)} (Class IDs: {set(b[0] for b in gt_boxes)})")
        print(f"    - Stock YOLOv8n Person Detections (Class 0): {len(person_preds)}")
        print(f"    - Stock YOLOv8n Other Class Detections:       {len(other_preds)} (Classes: {[int(b.cls) for b in other_preds][:5]})")
        
        if len(gt_boxes) > 0 and len(gt_boxes) <= 3:
            print(f"    - GT Box 0: Class={gt_boxes[0][0]}, Coords=({gt_boxes[0][1]:.3f}, {gt_boxes[0][2]:.3f}, {gt_boxes[0][3]:.3f}, {gt_boxes[0][4]:.3f})")


def audit_duplicate_detections_and_iou():
    """Task 7: Check IoU overlap and duplicate box generation in fine-tuned model."""
    print("\n==================================================")
    print("   TASK 7: DUPLICATE BOX GENERATION & IoU AUDIT")
    print("==================================================")
    
    cap = cv2.VideoCapture(str(BENGALURU_VIDEO))
    fine_model = YOLO(FINETUNED_MODEL)
    
    ret, frame = cap.read()
    cap.release()
    
    if not ret:
        print("[!] Error reading frame")
        return
        
    res = fine_model(frame, conf=0.25, verbose=False)[0]
    boxes = res.boxes.xyxy.cpu().numpy()
    confs = res.boxes.conf.cpu().numpy()
    
    num_boxes = len(boxes)
    print(f"[*] Raw Fine-Tuned Bounding Boxes at conf=0.25: {num_boxes}")
    
    if num_boxes > 1:
        # Calculate pairwise IoU matrix
        ious = []
        for i in range(min(num_boxes, 100)):
            for j in range(i + 1, min(num_boxes, 100)):
                boxA = boxes[i]
                boxB = boxes[j]
                
                xA = max(boxA[0], boxB[0])
                yA = max(boxA[1], boxB[1])
                xB = min(boxA[2], boxB[2])
                yB = min(boxA[3], boxB[3])
                
                interArea = max(0, xB - xA) * max(0, yB - yA)
                boxAArea = (boxA[2] - boxA[0]) * (boxA[3] - boxA[1])
                boxBArea = (boxB[2] - boxB[0]) * (boxB[3] - boxB[1])
                
                iou = interArea / float(boxAArea + boxBArea - interArea + 1e-6)
                if iou > 0.5:
                    ious.append(iou)
                    
        print(f"[*] Pairwise Box Overlaps with IoU > 0.5: {len(ious)} pairs")
        if len(ious) > 0:
            print(f"[*] Average high IoU overlap: {np.mean(ious):.2f}")


def main():
    print("==================================================")
    print("   CROWDPATROL COMPREHENSIVE SANITY AUDIT")
    print("==================================================")
    
    audit_raw_yolo_detections_on_bengaluru()
    audit_confidence_thresholds()
    audit_yolo_to_deepsort_breakdown()
    audit_baseline_map_root_cause()
    audit_duplicate_detections_and_iou()
    
    print("\n[OK] Dedicated Sanity Audit Script Complete.")


if __name__ == "__main__":
    main()
