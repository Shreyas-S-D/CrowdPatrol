"""
CrowdPatrol: Autonomous Public Safety & Monitoring Core
Main pipeline execution script with performance optimization & Firebase integration.
"""

import argparse
import time
import cv2
import numpy as np
import os
from pathlib import Path

from src.detection import PersonDetector
from src.tracking import PersonTracker
from src.density import DensityEstimator
from src.risk_assessment import RiskAssessor
from src.heatmap import generate_heatmap
from src.alerts import FirebaseAlertManager
from src.motion_analysis import CrowdMotionAnalyzer
from src.utils import VideoProcessor, MetricsLogger, FrameAnnotator


def parse_args():
    parser = argparse.ArgumentParser(description="CrowdPatrol Live Monitoring Core")
    parser.add_argument("--source", type=str, default="0",
                        help="Video source: '0' for webcam, file path ('data/videos/crowd.mp4'), or 'rtsp://...'")
    parser.add_argument("--model", type=str, default="yolov8n.pt",
                        help="YOLOv8 model weight path or model type (e.g. yolov8n.pt)")
    parser.add_argument("--confidence", type=float, default=0.5,
                        help="Person detection confidence threshold (0.1 - 1.0)")
    parser.add_argument("--device", type=str, default="cpu", choices=["cpu", "cuda"],
                        help="Execution device: 'cpu' or 'cuda'")
    parser.add_argument("--detect-interval", type=int, default=3,
                        help="Detection & DeepSORT re-ID interval in frames for high FPS (1 = every frame)")
    parser.add_argument("--save-video", type=str, default="",
                        help="Optional output video save path (e.g. 'output/output.mp4')")
    parser.add_argument("--alerts", action="store_true",
                        help="Enable Firebase Realtime DB synchronization & alerts")
    parser.add_argument("--no-show", action="store_true",
                        help="Disable live OpenCV preview window display")
    return parser.parse_args()


def main():
    args = parse_args()
    
    # Parse video source (int if numeric string)
    source = int(args.source) if args.source.isdigit() else args.source
    
    print("==================================================")
    print("   CROWDPATROL: AUTONOMOUS MONITORING CORE")
    print("==================================================")
    print(f"[*] Video Source:       {source}")
    print(f"[*] YOLOv8 Model:       {args.model}")
    print(f"[*] Confidence:         {args.confidence}")
    print(f"[*] Execution Device:   {args.device}")
    print(f"[*] Detection Interval: Every {args.detect_interval} frame(s)")
    print(f"[*] Firebase Alerts:    {'Enabled' if args.alerts else 'Disabled'}")
    
    # Initialize pipeline modules
    detector = PersonDetector(model_path=args.model, confidence=args.confidence, device=args.device)
    tracker = PersonTracker(max_age=30)
    density_estimator = DensityEstimator(grid_size=(4, 4))
    motion_analyzer = CrowdMotionAnalyzer(grid_size=(4, 4))
    risk_assessor = RiskAssessor()
    metrics_logger = MetricsLogger()
    
    alert_manager = None
    if args.alerts:
        try:
            alert_manager = FirebaseAlertManager()
            print("[✓] Firebase Alert Manager active")
        except Exception as e:
            print(f"[!] Warning: Firebase initialization failed ({e}). Proceeding without Firebase sync.")
    
    cap = VideoProcessor.get_video_source(source)
    if not cap.isOpened():
        print(f"[!] Error: Unable to open video source '{source}'")
        return
    
    info = VideoProcessor.get_video_info(cap)
    print(f"[✓] Stream Opened: {info['width']}x{info['height']} @ {info['fps']} FPS")
    
    writer = None
    if args.save_video:
        os.makedirs(os.path.dirname(args.save_video), exist_ok=True)
        writer = VideoProcessor.create_video_writer(
            args.save_video, 
            fps=info['fps'] if info['fps'] > 0 else 15, 
            width=info['width'], 
            height=info['height']
        )
        print(f"[✓] Saving video output to: {args.save_video}")
    
    frame_count = 0
    fps_deque = []
    current_tracks = []
    last_firebase_update = 0
    
    try:
        while True:
            t_start = time.perf_counter()
            ret, frame = cap.read()
            if not ret:
                print("[*] End of video stream reached.")
                break
            
            frame_count += 1
            
            # Controlled Detection Interval with Kalman Motion Prediction
            if frame_count == 1 or (frame_count % args.detect_interval == 0):
                detections = detector.detect(frame)
                current_tracks = tracker.update(detections, frame)
            else:
                # Step Kalman filter forward for smooth motion without CNN feature extraction
                current_tracks = tracker.predict()
            
            # Optical Flow Crowd Motion Analysis
            grid_matrix, motion_summary = motion_analyzer.analyze_frame(frame)
            
            # Density & Risk calculation
            density_map, max_density = density_estimator.calculate_density(current_tracks, frame.shape)
            anomaly_score = risk_assessor.calculate_movement_anomaly(current_tracks, frame.shape)
            
            # Phase 3 Enhanced Multi-Factor Risk Assessment
            risk_res = risk_assessor.assess_frame(
                max_density=max_density,
                motion_summary=motion_summary,
                tracks=current_tracks,
                timestamp=time.time(),
                anomaly_score=anomaly_score
            )
            
            risk_level_str = risk_res["risk"]
            combined_score = risk_res["combined_score"]
            person_count = len(current_tracks)
            
            # Annotations & Visualization Overlay (including motion arrows)
            annotated_frame = FrameAnnotator.create_dashboard_frame(
                frame, 
                {
                    "person_count": person_count,
                    "density": max_density,
                    "anomaly": anomaly_score,
                    "avg_speed": motion_summary["avg_speed"],
                    "dominant_direction": motion_summary["dominant_direction"],
                    "risk": risk_level_str,
                    "combined_score": combined_score
                },
                density_map,
                grid_size=(4, 4),
                grid_matrix=grid_matrix
            )
            
            # Optional Heatmap blending
            heatmap_overlay, _ = generate_heatmap(annotated_frame, current_tracks)
            
            t_end = time.perf_counter()
            frame_ms = (t_end - t_start) * 1000.0
            current_fps = 1000.0 / frame_ms if frame_ms > 0 else 0.0
            fps_deque.append(current_fps)
            if len(fps_deque) > 30:
                fps_deque.pop(0)
            avg_fps = float(np.mean(fps_deque))
            
            # Draw FPS overlay
            cv2.putText(heatmap_overlay, f"FPS: {avg_fps:.1f}", (20, frame.shape[0] - 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
            
            # Log CSV metrics
            metrics_payload = {
                "person_count": person_count,
                "density": max_density,
                "anomaly": anomaly_score,
                "risk": risk_level_str,
                "combined_score": combined_score,
                "raw_score": risk_res["raw_score"],
                "smoothed_score": risk_res["smoothed_score"],
                "data_quality_score": risk_res["data_quality_score"],
                "growth_rate": risk_res["growth_rate"],
                "fps": avg_fps
            }
            metrics_logger.log(metrics_payload, frame_count)
            
            # Firebase Sync (throttled to 1 sec)
            if alert_manager and (time.time() - last_firebase_update > 1.0):
                alert_manager.update_dashboard_data(metrics_payload)
                if risk_level_str in ["Medium", "High"]:
                    alert_manager.store_alert(
                        risk_level=risk_level_str,
                        density=max_density,
                        anomaly_score=anomaly_score,
                        person_count=person_count,
                        combined_score=combined_score,
                        growth_rate=risk_res["growth_rate"],
                        data_quality_score=risk_res["data_quality_score"]
                    )
                last_firebase_update = time.time()
            
            # Save video frame
            if writer:
                writer.write(heatmap_overlay)
            
            # Display window stream
            if not args.no_show:
                cv2.imshow("CrowdPatrol - Live Monitoring Core", heatmap_overlay)
                key = cv2.waitKey(1) & 0xFF
                if key == 27 or key == ord('q'):
                    print("[*] Monitoring stopped by user.")
                    break
                    
    finally:
        cap.release()
        if writer:
            writer.release()
        cv2.destroyAllWindows()
        print("[✓] Pipeline shut down cleanly.")


if __name__ == "__main__":
    main()
