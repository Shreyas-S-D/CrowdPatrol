"""
CrowdPatrol Phase 4.1 - Comprehensive Head Detection Accuracy Audit Script.
Traces the full pipeline on representative dense crowd frames:
  Video Frame -> YOLO Raw Predictions -> Confidence Filtering (conf=0.25) -> NMS -> DeepSORT Tracking.
Analyzes bounding box size distributions, micro-head limitations, and tiled mode comparison.
"""

import os
import sys
import time
import cv2
import numpy as np
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
sys.path.append(str(BASE_DIR))

from src.experimental_head_mode import ExperimentalHeadDetector, DEFAULT_HEAD_MODEL_PATH
from src.tracking import PersonTracker

def run_audit(video_path: str, num_sample_frames: int = 10):
    print(f"\n=======================================================")
    print(f"AUDITING HEAD DETECTION ACCURACY: {video_path}")
    print(f"=======================================================")
    
    if not os.path.exists(video_path):
        print(f"Error: Video file not found: {video_path}")
        return None
        
    cap = cv2.VideoCapture(video_path)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    video_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    video_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    print(f"Video Resolution: {video_w}x{video_h} | Total Frames: {total_frames} | Video FPS: {fps:.1f}")

    detector = ExperimentalHeadDetector(model_path=DEFAULT_HEAD_MODEL_PATH, confidence=0.25, device="cpu", imgsz=640)
    tracker = PersonTracker(max_age=15, n_init=1)
    
    # Also detector with low threshold (conf=0.05) to measure raw candidate boxes before filtering
    detector_low_conf = ExperimentalHeadDetector(model_path=DEFAULT_HEAD_MODEL_PATH, confidence=0.05, device="cpu", imgsz=640)
    
    # Pick 10 evenly spaced frames
    step = max(1, total_frames // (num_sample_frames + 2))
    sample_indices = [step * (i + 1) for i in range(num_sample_frames)]
    
    results = []
    
    frame_idx = 0
    sampled_count = 0
    
    while cap.isOpened() and sampled_count < num_sample_frames:
        ret, frame = cap.read()
        if not ret:
            break
        frame_idx += 1
        
        if frame_idx in sample_indices:
            sampled_count += 1
            
            # 1. Low-confidence raw candidates (conf >= 0.05)
            low_conf_dets = detector_low_conf.detect_full_frame(frame)
            raw_candidate_count = len(low_conf_dets)
            
            # 2. Standard threshold full-frame detections (conf >= 0.25)
            t_det_start = time.perf_counter()
            std_dets = detector.detect_full_frame(frame)
            t_det_ms = (time.perf_counter() - t_det_start) * 1000.0
            conf_25_count = len(std_dets)
            
            # 3. Tiled 2x2 detections (conf >= 0.25)
            t_tile_start = time.perf_counter()
            tiled_dets = detector.detect_tiled_2x2(frame)
            t_tile_ms = (time.perf_counter() - t_tile_start) * 1000.0
            tiled_count = len(tiled_dets)
            
            # 4. DeepSORT tracker update with standard detections
            t_trk_start = time.perf_counter()
            active_tracks = tracker.update(std_dets, frame)
            visible_tracks = tracker.get_visible_tracks()
            t_trk_ms = (time.perf_counter() - t_trk_start) * 1000.0
            
            active_track_count = len(active_tracks)
            visible_track_count = len(visible_tracks)
            
            # 5. Box size statistics for conf >= 0.25 detections
            widths = [d[0][2] for d in std_dets]
            heights = [d[0][3] for d in std_dets]
            
            small_heads = sum(1 for w, h in zip(widths, heights) if max(w, h) < 24)
            medium_heads = sum(1 for w, h in zip(widths, heights) if 24 <= max(w, h) <= 48)
            large_heads = sum(1 for w, h in zip(widths, heights) if max(w, h) > 48)
            
            avg_w = np.mean(widths) if widths else 0.0
            avg_h = np.mean(heights) if heights else 0.0
            
            record = {
                "frame_idx": frame_idx,
                "raw_candidate_count_005": raw_candidate_count,
                "conf_25_count": conf_25_count,
                "tiled_count": tiled_count,
                "active_track_count": active_track_count,
                "visible_track_count": visible_track_count,
                "small_heads_lt24": small_heads,
                "medium_heads_24_48": medium_heads,
                "large_heads_gt48": large_heads,
                "avg_box_wh": (round(float(avg_w), 1), round(float(avg_h), 1)),
                "det_time_ms": round(t_det_ms, 1),
                "tiled_time_ms": round(t_tile_ms, 1),
                "trk_time_ms": round(t_trk_ms, 1),
            }
            results.append(record)
            
            print(f"Frame {frame_idx:4d} | Raw(>=0.05): {raw_candidate_count:3d} | Conf>=0.25: {conf_25_count:3d} | Tiled: {tiled_count:3d} | Tracks(vis/act): {visible_track_count:2d}/{active_track_count:2d} | Box Sizes(<24/24-48/>48): {small_heads:2d}/{medium_heads:2d}/{large_heads:2d} | Avg WH: {avg_w:.1f}x{avg_h:.1f} | Det: {t_det_ms:.1f}ms | Trk: {t_trk_ms:.1f}ms")
            
    cap.release()
    return results

if __name__ == "__main__":
    v1 = "data/videos/dense_crowd_test.mp4"
    v2 = "data/videos/youtube_crowd_test.mp4"
    
    r1 = run_audit(v1, num_sample_frames=10)
    r2 = run_audit(v2, num_sample_frames=10)
    
    print("\nAUDIT COMPLETE.")
