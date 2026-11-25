"""
Benchmark script to profile every stage of dashboard/simple_dashboard.py execution.
"""
import sys
import time
import os
from pathlib import Path
import numpy as np
import cv2
import pandas as pd
from collections import deque
from datetime import datetime

# Add project root to sys.path
sys.path.append(str(Path(__file__).parent.parent))

from src.detection import PersonDetector
from src.tracking import PersonTracker
from src.density import DensityEstimator
from src.motion_analysis import CrowdMotionAnalyzer
from src.risk_assessment import RiskAssessor
from src.heatmap import generate_heatmap
from src.utils import VideoProcessor, MetricsLogger, FrameAnnotator

def run_streamlit_benchmark(video_path="data/videos/youtube_crowd_test.mp4", model_path="models/crowdpatrol_yolov8n_finetuned_v2.pt", num_frames=150):
    print(f"=== Starting Streamlit Dashboard Pipeline Benchmark ===")
    print(f"Video: {video_path}")
    print(f"Model: {model_path}")
    
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Error opening video {video_path}")
        return
        
    detector = PersonDetector(model_path=model_path, confidence=0.35, device="cpu")
    tracker = PersonTracker(max_age=30)
    density_estimator = DensityEstimator(grid_size=(4, 4))
    motion_analyzer = CrowdMotionAnalyzer(grid_size=(4, 4))
    risk_assessor = RiskAssessor()
    metrics_logger = MetricsLogger()
    
    preview_resolution = (854, 480)
    jpeg_quality = 80
    detect_interval = 3
    
    t_detection = []
    t_motion = []
    t_density_risk = []
    t_heatmap_annotate = []
    t_jpeg_encode = []
    t_total_frame = []
    
    frame_count = 0
    current_tracks = []
    
    while frame_count < num_frames:
        t_start = time.perf_counter()
        ret, frame = cap.read()
        if not ret:
            break
            
        frame_count += 1
        
        # 1. Detection & Tracking
        t0 = time.perf_counter()
        if frame_count == 1 or (frame_count % detect_interval == 0):
            detections = detector.detect(frame)
            current_tracks = tracker.update(detections, frame)
        else:
            current_tracks = tracker.predict()
        t1 = time.perf_counter()
        t_detection.append((t1 - t0) * 1000.0)
        
        # 2. Optical Flow Motion Analysis
        t0 = time.perf_counter()
        grid_matrix, motion_summary = motion_analyzer.analyze_frame(frame)
        t1 = time.perf_counter()
        t_motion.append((t1 - t0) * 1000.0)
        
        # 3. Density & Risk
        t0 = time.perf_counter()
        density_map, max_density = density_estimator.calculate_density(current_tracks, frame.shape)
        anomaly_score = risk_assessor.calculate_movement_anomaly(current_tracks, frame.shape)
        risk_res = risk_assessor.assess_frame(
            max_density=max_density,
            motion_summary=motion_summary,
            tracks=current_tracks,
            timestamp=time.time(),
            anomaly_score=anomaly_score
        )
        t1 = time.perf_counter()
        t_density_risk.append((t1 - t0) * 1000.0)
        
        # 4. Heatmap & Annotation
        t0 = time.perf_counter()
        heatmap_base, _ = generate_heatmap(frame, current_tracks, draw_grid=False)
        annotated_frame = FrameAnnotator.create_dashboard_frame(
            heatmap_base,
            {
                "person_count": len(current_tracks),
                "density": max_density,
                "anomaly": anomaly_score,
                "avg_speed": motion_summary.get("avg_speed", 0.0),
                "dominant_direction": motion_summary.get("dominant_direction", "STATIONARY"),
                "risk": risk_res["risk"],
                "combined_score": risk_res["combined_score"]
            },
            density_map,
            grid_size=(4, 4),
            grid_matrix=grid_matrix,
            tracks=current_tracks
        )
        t1 = time.perf_counter()
        t_heatmap_annotate.append((t1 - t0) * 1000.0)
        
        # 5. JPEG Stream Compression & Preview Resize
        t0 = time.perf_counter()
        display_frame = cv2.resize(annotated_frame, preview_resolution)
        _, jpeg_buffer = cv2.imencode('.jpg', display_frame, [int(cv2.IMWRITE_JPEG_QUALITY), jpeg_quality])
        jpeg_bytes = jpeg_buffer.tobytes()
        t1 = time.perf_counter()
        t_jpeg_encode.append((t1 - t0) * 1000.0)
        
        t_end = time.perf_counter()
        t_total_frame.append((t_end - t_start) * 1000.0)

    cap.release()
    
    print("\n--- BENCHMARK RESULTS (over {} frames) ---".format(frame_count))
    print(f"1. Detection & DeepSORT: avg {np.mean(t_detection):.2f} ms (min {np.min(t_detection):.2f}, max {np.max(t_detection):.2f})")
    print(f"2. Optical Flow Motion:  avg {np.mean(t_motion):.2f} ms")
    print(f"3. Density & Risk Eval:  avg {np.mean(t_density_risk):.2f} ms")
    print(f"4. Heatmap & Annotation: avg {np.mean(t_heatmap_annotate):.2f} ms")
    print(f"5. JPEG Encode & Resize: avg {np.mean(t_jpeg_encode):.2f} ms")
    print(f"Total Computation / Frame: avg {np.mean(t_total_frame):.2f} ms")
    print(f"Estimated Core Pipeline FPS: {1000.0 / np.mean(t_total_frame):.2f} FPS")

if __name__ == "__main__":
    run_streamlit_benchmark()
