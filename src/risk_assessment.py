import numpy as np
from enum import Enum

class RiskLevel(Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"

class RiskAssessor:
    def __init__(self, density_thresholds=None):
        self.thresholds = density_thresholds or {
            "low": 5, "medium": 15, "high": 30
        }
        self.previous_centroids = {}
        self.anomaly_threshold = 10  # pixels/frame
    
    def calculate_movement_anomaly(self, tracks, frame_shape):
        """Calculate movement anomaly score based on sudden velocity changes"""
        current_centroids = {}
        anomaly_score = 0
        
        for track in tracks:
            x1, y1, x2, y2, track_id = track
            centroid = np.array([(x1 + x2) / 2, (y1 + y2) / 2])
            current_centroids[track_id] = centroid
            
            if track_id in self.previous_centroids:
                velocity = np.linalg.norm(centroid - self.previous_centroids[track_id])
                if velocity > self.anomaly_threshold:
                    anomaly_score += 1
        
        self.previous_centroids = current_centroids
        return min(anomaly_score / max(len(tracks), 1), 1.0)
    
    def assess_risk(self, max_density, anomaly_score):
        """Combine density and anomaly to determine risk level"""
        density_risk = 0
        if max_density >= self.thresholds["high"]:
            density_risk = 3
        elif max_density >= self.thresholds["medium"]:
            density_risk = 2
        elif max_density >= self.thresholds["low"]:
            density_risk = 1
        
        # Combined risk score (0-100)
        combined_score = (density_risk / 3) * 70 + anomaly_score * 30
        
        if combined_score >= 70:
            return RiskLevel.HIGH, combined_score
        elif combined_score >= 40:
            return RiskLevel.MEDIUM, combined_score
        else:
            return RiskLevel.LOW, combined_score