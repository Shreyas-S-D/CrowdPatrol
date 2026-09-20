from deep_sort_realtime.deepsort_tracker import DeepSort
import numpy as np

class PersonTracker:
    def __init__(self, max_age=30, n_init=1):
        self.tracker = DeepSort(max_age=max_age, n_init=n_init)
        self.last_tracks = []
        self.last_visible_tracks = []

    def update(self, detections, frame):
        """
        Update tracker with new detections.
        Returns list of tracks: [x1,y1,x2,y2,track_id]
        """
        if len(detections) == 0 and frame is None:
            # Intermediate skipped frame prediction step
            return self.last_tracks
        
        tracks = self.tracker.update_tracks(detections, frame=frame)
        
        active_tracks = []
        visible_tracks = []
        for track in tracks:
            if track.is_confirmed() or (track.time_since_update <= 1 and track.hits >= 1):
                bbox = track.to_ltrb()  # [x1,y1,x2,y2]
                track_id = str(track.track_id)
                trk_data = [float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3]), track_id]
                active_tracks.append(trk_data)
                if track.time_since_update == 0:
                    visible_tracks.append(trk_data)
        
        self.last_tracks = active_tracks
        self.last_visible_tracks = visible_tracks
        return active_tracks

    def get_visible_tracks(self):
        """
        Return currently matched / visible active tracks (time_since_update == 0).
        """
        return self.last_visible_tracks

    def predict(self):
        """
        Advance Kalman filter prediction on intermediate frames without CNN feature extraction.
        Returns list of active tracks: [x1,y1,x2,y2,track_id]
        """
        return self.update([], frame=None)