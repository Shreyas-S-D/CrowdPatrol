from deep_sort_realtime.deepsort_tracker import DeepSort
import numpy as np

class PersonTracker:
    def __init__(self, max_age=30):
        self.tracker = DeepSort(max_age=max_age)
    
    def update(self, detections, frame):
        """
        Update tracker with new detections.
        Returns list of tracks: [x1,y1,x2,y2,track_id]
        """
        if len(detections) == 0:
            tracks = self.tracker.update_tracks([], embeds=[])
        else:
            tracks = self.tracker.update_tracks(detections, frame=frame)
        
        active_tracks = []
        for track in tracks:
            if track.is_confirmed():
                bbox = track.to_ltrb()  # [x1,y1,x2,y2]
                track_id = str(track.track_id)
                active_tracks.append([float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3]), track_id])
        
        return active_tracks

    def predict(self):
        """
        Advance Kalman filter prediction on intermediate frames without CNN feature extraction.
        Returns list of active tracks: [x1,y1,x2,y2,track_id]
        """
        return self.update([], frame=None)