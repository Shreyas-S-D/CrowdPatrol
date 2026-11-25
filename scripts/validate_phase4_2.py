"""
CrowdPatrol Phase 4.2 Comprehensive Validation Script.
Measures:
  1. Actual AI Inference FPS (per-camera) and Display FPS
  2. Aggregate Throughput (frames/sec across system)
  3. Dense Crowd Head Detection Accuracy Comparison:
     - Baseline vs Enhanced (CLAHE + Sliced Multi-Scale)
     - Raw Detections, Post-NMS Detections, and Tracked Heads
     - Tested on both dense_crowd_test.mp4 and youtube_crowd_test.mp4
"""

import sys
import time
import cv2
import numpy as np
import torch
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
sys.path.append(str(BASE_DIR))

from src.experimental_head_mode import ExperimentalHeadDetector, DEFAULT_HEAD_MODEL_PATH
from src.tracking import PersonTracker
from src.multi_camera_manager import MultiCameraManager

def validate_detection_accuracy():
    print("=" * 70)
    print("1. EVALUATING DENSE-CROWD HEAD DETECTION ACCURACY")
    print("=" * 70)
    
    detector = ExperimentalHeadDetector(model_path=DEFAULT_HEAD_MODEL_PATH, confidence=0.25, device="cpu", imgsz=640)
    tracker = PersonTracker(max_age=15, n_init=1)
    
    results = {}
    
    for vname in ["data/videos/dense_crowd_test.mp4", "data/videos/youtube_crowd_test.mp4"]:
        cap = cv2.VideoCapture(vname)
        total_f = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        sample_indices = [int(total_f * r) for r in [0.1, 0.25, 0.5, 0.7, 0.85]]
        
        v_results = []
        print(f"\nVideo: {vname} (Total Frames: {total_f})")
        
        for fid in sample_indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, fid)
            ret, frame = cap.read()
            if not ret: continue
            
            # Baseline: Full-frame without CLAHE
            dets_base = detector.detect_full_frame(frame, enhance_contrast=False)
            
            # Enhanced: Full-frame with CLAHE
            dets_clahe = detector.detect_full_frame(frame, enhance_contrast=True)
            
            # Enhanced Sliced: Multi-Scale Sliced with CLAHE
            t0 = time.perf_counter()
            dets_sliced = detector.detect_tiled_2x2(frame, enhance_contrast=True)
            t_slice_ms = (time.perf_counter() - t0) * 1000
            
            # Tracking on Enhanced Sliced
            tracks = tracker.update(dets_sliced, frame)
            vis_tracks = tracker.get_visible_tracks()
            
            record = {
                "frame": fid,
                "baseline_full": len(dets_base),
                "clahe_full": len(dets_clahe),
                "enhanced_sliced": len(dets_sliced),
                "tracked_heads": len(vis_tracks),
                "slice_time_ms": round(t_slice_ms, 1)
            }
            v_results.append(record)
            print(f"Frame {fid:4d} | Baseline (640x640): {len(dets_base):2d} | CLAHE (640x640): {len(dets_clahe):2d} | Enhanced Sliced: {len(dets_sliced):2d} | Tracked: {len(vis_tracks):2d} | Time: {t_slice_ms:.1f}ms")
            
        cap.release()
        results[vname] = v_results
        
    return results

def validate_inference_fps():
    print("\n" + "=" * 70)
    print("2. EVALUATING ACTUAL AI INFERENCE FPS & SYSTEM THROUGHPUT")
    print("=" * 70)
    
    fps_results = {}
    
    for mode_name, is_tiled in [("Full-Frame Mode (640x640)", False), ("Enhanced Sliced Mode", True)]:
        print(f"\n--- Testing Mode: {mode_name} ---")
        mgr = MultiCameraManager(device="cpu", detect_interval=2, tiled_mode=is_tiled)
        mgr.start_all_cameras()
        
        # Warmup
        for _ in range(5):
            mgr.step_focus("CAM-01", step_background=True)
            
        t0 = time.perf_counter()
        cycles = 30
        for _ in range(cycles):
            mgr.step_focus("CAM-01", step_background=True)
        t_tot = time.perf_counter() - t0
        
        cam1 = mgr.cameras["CAM-01"]
        metrics = mgr.get_throughput_metrics()
        
        res = {
            "mode": mode_name,
            "cycles_per_sec": round(cycles / t_tot, 2),
            "cam1_display_fps": round(cam1.fps, 2),
            "cam1_yolo_inferences": cam1.yolo_inferences_count,
            "cam1_yolo_inference_fps": round(cam1.yolo_inference_fps, 2),
            "all_yolo_fps": metrics["yolo_inference_fps"],
            "aggregate_throughput_fps": round(metrics["aggregate_throughput_fps"], 2)
        }
        fps_results[mode_name] = res
        
        print(f"Loop Speed: {res['cycles_per_sec']} cycles/sec ({cycles} in {t_tot:.2f}s)")
        print(f"CAM-01 Display FPS: {res['cam1_display_fps']}")
        print(f"CAM-01 Actual YOLO Inference FPS: {res['cam1_yolo_inference_fps']}")
        print(f"All Camera Inference FPS: {res['all_yolo_fps']}")
        print(f"Aggregate System Throughput: {res['aggregate_throughput_fps']} frames/sec")
        
        mgr.stop_all_cameras()
        
    return fps_results

if __name__ == "__main__":
    det_res = validate_detection_accuracy()
    fps_res = validate_inference_fps()
    print("\nVALIDATION COMPLETE.")
