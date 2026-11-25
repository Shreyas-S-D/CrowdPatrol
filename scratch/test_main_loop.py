import cv2
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.detection import PersonDetector
from src.tracking import PersonTracker
from src.density import DensityEstimator
from src.motion_analysis import CrowdMotionAnalyzer
from src.risk_assessment import RiskAssessor

def test_loop():
    detector = PersonDetector(model_path="yolov8n.pt", confidence=0.35, device="cpu")
    tracker = PersonTracker(max_age=30)
    density_estimator = DensityEstimator(grid_size=(4, 4))
    
    cap = cv2.VideoCapture("data/videos/youtube_crowd_test.mp4")
    
    for frame_count in range(1, 15):
        ret, frame = cap.read()
        if not ret:
            break
            
        if frame_count == 1 or (frame_count % 3 == 0):
            detections = detector.detect(frame)
            tracks = tracker.update(detections, frame)
        else:
            detections = []
            tracks = tracker.predict()
            
        density_map, max_density = density_estimator.calculate_density(tracks, frame.shape)
        
        print(f"Frame #{frame_count:02d}: Detections={len(detections)}, Active Tracks={len(tracks)}, Max Density={max_density}")
        if len(tracks) > 0:
            print(f"   First Track ID: {tracks[0][4]}")
            
    cap.release()

if __name__ == "__main__":
    test_loop()
