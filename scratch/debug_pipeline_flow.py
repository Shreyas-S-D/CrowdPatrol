import cv2
import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.detection import PersonDetector
from src.tracking import PersonTracker
from src.density import DensityEstimator
from src.motion_analysis import CrowdMotionAnalyzer
from src.risk_assessment import RiskAssessor
from src.utils import FrameAnnotator

def debug_full_pipeline_flow():
    video_path = "data/videos/youtube_crowd_test.mp4"
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"[!] Unable to open video: {video_path}")
        return

    print("==================================================")
    print("   FULL PIPELINE DATA FLOW DIAGNOSTIC TEST")
    print("==================================================")

    detector = PersonDetector(model_path="yolov8n.pt", confidence=0.4, device="cpu")
    tracker = PersonTracker(max_age=30)
    density_estimator = DensityEstimator(grid_size=(4, 4))
    motion_analyzer = CrowdMotionAnalyzer(grid_size=(4, 4))
    risk_assessor = RiskAssessor()

    for frame_count in range(1, 15):
        ret, frame = cap.read()
        if not ret or frame is None:
            break

        # Step 1: Detect
        if frame_count == 1 or (frame_count % 3 == 0):
            detections = detector.detect(frame)
            tracks = tracker.update(detections, frame)
            step_type = "DETECT + TRACK"
        else:
            detections = []
            tracks = tracker.predict()
            step_type = "KALMAN PREDICT"

        # Step 2: Density
        density_map, max_density = density_estimator.calculate_density(tracks, frame.shape)
        
        # Step 3: Motion
        grid_matrix, motion_summary = motion_analyzer.analyze_frame(frame)
        
        # Step 4: Risk
        risk_res = risk_assessor.assess_frame(max_density=max_density, motion_summary=motion_summary, tracks=tracks, timestamp=1.0)

        print(f"Frame #{frame_count:02d} [{step_type}]: Raw Detections={len(detections)}, Active Tracks={len(tracks)}, Max Density={max_density}, Risk={risk_res['risk']}")

        # Inspect format of tracks
        if len(tracks) > 0:
            print(f"   Sample Track [0]: {tracks[0]}")

        # Check annotated frame rendering
        annotated_frame = FrameAnnotator.create_dashboard_frame(
            frame, 
            {
                "person_count": len(tracks),
                "density": max_density,
                "anomaly": 0.0,
                "avg_speed": motion_summary["avg_speed"],
                "dominant_direction": motion_summary["dominant_direction"],
                "risk": risk_res["risk"],
                "combined_score": risk_res["combined_score"]
            },
            density_map,
            grid_size=(4, 4),
            grid_matrix=grid_matrix,
            tracks=tracks
        )

        if frame_count == 3:
            cv2.imwrite("scratch/annotated_debug_frame3.jpg", annotated_frame)
            print("   [OK] Saved annotated debug frame 3 to scratch/annotated_debug_frame3.jpg")

    cap.release()

if __name__ == "__main__":
    debug_full_pipeline_flow()
