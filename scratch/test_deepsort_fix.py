import cv2
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.detection import PersonDetector
from deep_sort_realtime.deepsort_tracker import DeepSort

def test_n_init_fix():
    video_path = "data/videos/youtube_crowd_test.mp4"
    detector = PersonDetector(model_path="yolov8n.pt", confidence=0.35, device="cpu")
    
    # Test DeepSort with n_init=1 (Confirm track on first detection match)
    tracker = DeepSort(max_age=30, n_init=1)
    
    cap = cv2.VideoCapture(video_path)
    print("==================================================")
    print("   TESTING DEEPSORT WITH n_init=1 & detect_interval=3")
    print("==================================================")

    for f in range(1, 15):
        ret, frame = cap.read()
        if not ret: break
        
        if f == 1 or (f % 3 == 0):
            detections = detector.detect(frame)
            tracks = tracker.update_tracks(detections, frame=frame)
            stype = "DETECT"
        else:
            detections = []
            tracks = tracker.update_tracks([], frame=frame)
            stype = "PREDICT"
            
        confirmed_tracks = [t for t in tracks if t.is_confirmed()]
        print(f"Frame #{f:02d} [{stype}]: Raw Detections={len(detections)}, Confirmed Tracks={len(confirmed_tracks)}")

    cap.release()

if __name__ == "__main__":
    test_n_init_fix()
