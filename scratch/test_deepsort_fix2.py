import cv2
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.detection import PersonDetector
from deep_sort_realtime.deepsort_tracker import DeepSort

class FixedPersonTracker:
    def __init__(self, max_age=30):
        self.tracker = DeepSort(max_age=max_age)
        self.last_confirmed_tracks = []
        
    def update(self, detections, frame):
        if len(detections) > 0 or frame is not None:
            tracks = self.tracker.update_tracks(detections, frame=frame)
        else:
            # On skipped frames, return current active tracks without resetting DeepSORT
            return self.last_confirmed_tracks
            
        active_tracks = []
        for track in tracks:
            # Return both confirmed and unconfirmed/tentative tracks if confirmed exist, or confirmed
            if track.is_confirmed() or (track.time_since_update <= 1 and track.hits >= 1):
                bbox = track.to_ltrb()
                track_id = str(track.track_id)
                active_tracks.append([float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3]), track_id])
                
        self.last_confirmed_tracks = active_tracks
        return active_tracks

    def predict(self):
        # Step internal Kalman filter predictions without resetting DeepSORT with empty detections
        self.tracker.tracker.predict()
        active_tracks = []
        for track in self.tracker.tracker.tracks:
            if track.is_confirmed() or (track.time_since_update <= 1 and track.hits >= 1):
                bbox = track.to_ltwh() # or convert mean to ltrb
                # convert to [x1, y1, x2, y2]
                x1, y1, w, h = bbox
                active_tracks.append([float(x1), float(y1), float(x1 + w), float(y1 + h), str(track.track_id)])
        self.last_confirmed_tracks = active_tracks
        return active_tracks


def test_fix():
    video_path = "data/videos/youtube_crowd_test.mp4"
    detector = PersonDetector(model_path="yolov8n.pt", confidence=0.35, device="cpu")
    tracker = FixedPersonTracker(max_age=30)
    
    cap = cv2.VideoCapture(video_path)
    print("==================================================")
    print("   TESTING FIXED PERSON TRACKER WITH detect_interval=3")
    print("==================================================")

    for f in range(1, 15):
        ret, frame = cap.read()
        if not ret: break
        
        if f == 1 or (f % 3 == 0):
            detections = detector.detect(frame)
            tracks = tracker.update(detections, frame)
            stype = "DETECT"
        else:
            detections = []
            tracks = tracker.predict()
            stype = "PREDICT"
            
        print(f"Frame #{f:02d} [{stype}]: Raw Detections={len(detections)}, Active Tracks={len(tracks)}")
        if len(tracks) > 0:
            print(f"   First Track ID: {tracks[0][4]}")

    cap.release()

if __name__ == "__main__":
    test_fix()
