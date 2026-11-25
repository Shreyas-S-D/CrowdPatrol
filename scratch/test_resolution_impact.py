"""
Controlled Experiment: Testing the Impact of Input Resolution (imgsz) on Dense Crowd Detection.
Runs models/crowdpatrol_yolov8n_finetuned_v2.pt on data/videos/dense_crowd_test.mp4 at imgsz=640, 800, and 960.
"""

import os
import sys
import json
import time
import cv2
import numpy as np
import torch
from pathlib import Path
from ultralytics import YOLO

def run_resolution_experiment(max_eval_frames=300):
    video_path = "data/videos/dense_crowd_test.mp4"
    model_path = "models/crowdpatrol_yolov8n_finetuned_v2.pt"
    viz_dir = Path("training/visualizations/dense_crowd_diagnostics/resolution_test")
    viz_dir.mkdir(parents=True, exist_ok=True)
    
    print("=== CONTROLLED EXPERIMENT: INPUT RESOLUTION (imgsz) IMPACT ===")
    print(f"Video: {video_path}")
    print(f"Model: {model_path}")
    
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {video_path}")
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    
    print(f"Native Video Resolution: {width}x{height}, Total Frames: {total_frames}, Test Frames: {max_eval_frames}")
    
    model = YOLO(model_path)
    resolutions = [640, 800, 960]
    conf_thresh = 0.35
    
    experiment_results = {}
    
    for imgsz in resolutions:
        print(f"\n--- Testing imgsz={imgsz} (conf={conf_thresh}) ---")
        cap = cv2.VideoCapture(video_path)
        
        counts = []
        confs_all = []
        frames_0 = 0
        frame_times = []
        
        fc = 0
        while fc < max_eval_frames:
            ret, frame = cap.read()
            if not ret:
                break
            fc += 1
            
            t0 = time.perf_counter()
            results = model(frame, imgsz=imgsz, conf=conf_thresh, device="cpu", verbose=False)[0]
            t1 = time.perf_counter()
            frame_times.append((t1 - t0) * 1000.0)
            
            dets = []
            for box in results.boxes:
                if int(box.cls) == 0 and float(box.conf) >= conf_thresh:
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    conf = float(box.conf)
                    dets.append(([x1, y1, x2, y2], conf))
                    confs_all.append(conf)
                    
            cnt = len(dets)
            counts.append(cnt)
            if cnt == 0:
                frames_0 += 1
                
            # Render representative frame visuals
            if fc in [1, 30, 60, 90, 120, 150, 200, 250, 300]:
                vis = frame.copy()
                for box, conf in dets:
                    x1, y1, x2, y2 = map(int, box)
                    cv2.rectangle(vis, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    cv2.putText(vis, f"{conf:.2f}", (x1, max(y1-5, 15)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)
                cv2.putText(vis, f"imgsz={imgsz} | Raw Detections: {cnt} | Avg Speed: {1000.0/np.mean(frame_times):.1f} FPS", 
                            (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
                cv2.imwrite(str(viz_dir / f"raw_det_imgsz_{imgsz}_frame_{fc:03d}.jpg"), vis)
                
        cap.release()
        
        avg_ms = float(np.mean(frame_times))
        proc_fps = 1000.0 / avg_ms if avg_ms > 0 else 0.0
        
        stats = {
            "imgsz": imgsz,
            "avg_detections_per_frame": float(np.mean(counts)),
            "max_detections_per_frame": int(np.max(counts)),
            "min_detections_per_frame": int(np.min(counts)),
            "mean_confidence": float(np.mean(confs_all)) if confs_all else 0.0,
            "median_confidence": float(np.median(confs_all)) if confs_all else 0.0,
            "frames_with_0_detections": int(frames_0),
            "processing_fps": float(proc_fps),
            "avg_ms_per_frame": float(avg_ms)
        }
        
        experiment_results[f"imgsz_{imgsz}"] = stats
        print(f"Results for imgsz={imgsz}:")
        print(f"  Avg Detections/Frame: {stats['avg_detections_per_frame']:.2f} (Max: {stats['max_detections_per_frame']}, Min: {stats['min_detections_per_frame']})")
        print(f"  Mean Confidence:      {stats['mean_confidence']:.3f} (Median: {stats['median_confidence']:.3f})")
        print(f"  0-Detection Frames:   {stats['frames_with_0_detections']} / {max_eval_frames}")
        print(f"  Processing FPS:       {stats['processing_fps']:.2f} FPS ({stats['avg_ms_per_frame']:.1f} ms/frame)")

    json_path = Path("training/visualizations/dense_crowd_diagnostics/resolution_test/resolution_test_results.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(experiment_results, f, indent=2)
    print(f"\n[OK] Saved Resolution Experiment JSON to {json_path}")
    
    return experiment_results

if __name__ == "__main__":
    run_resolution_experiment(max_eval_frames=300)
