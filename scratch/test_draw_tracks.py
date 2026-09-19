import cv2
import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.detection import PersonDetector
from src.tracking import PersonTracker
from src.density import DensityEstimator
from src.utils import FrameAnnotator

def test_draw_tracks_rendering():
    detector = PersonDetector(model_path="yolov8n.pt", confidence=0.35, device="cpu")
    tracker = PersonTracker(max_age=30)
    density_estimator = DensityEstimator(grid_size=(4, 4))

    cap = cv2.VideoCapture("data/videos/youtube_crowd_test.mp4")
    assert cap.isOpened(), "Could not open data/videos/youtube_crowd_test.mp4"

    for i in range(1, 10):
        ret, frame = cap.read()
        if not ret:
            break
            
        detections = detector.detect(frame)
        tracks = tracker.update(detections, frame)
        density_map, max_density = density_estimator.calculate_density(tracks, frame.shape)
        
        print(f"Frame #{i}: Detections={len(detections)}, Active Tracks={len(tracks)}, Max Density={max_density}")
        
        if len(tracks) > 0:
            for t in tracks:
                print(f"   Track: ID={t[4]}, Box=({t[0]:.1f}, {t[1]:.1f}, {t[2]:.1f}, {t[3]:.1f})")
                
    cap.release()
    print("[OK] Test finished successfully.")

if __name__ == "__main__":
    test_draw_tracks_rendering()
