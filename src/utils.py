import cv2
import numpy as np
from datetime import datetime
import os
import json
import csv
from pathlib import Path

class VideoProcessor:
    """Utility class for video I/O operations"""
    
    @staticmethod
    def get_video_source(source):
        """
        Determine video source type and return cv2.VideoCapture object.
        source: 0 for webcam, 'video.mp4' for file, 'rtsp://...' for IP camera
        """
        if isinstance(source, int):
            return cv2.VideoCapture(source)
        elif source.startswith("rtsp://"):
            return cv2.VideoCapture(source)
        else:
            return cv2.VideoCapture(source)
    
    @staticmethod
    def get_video_info(cap):
        """Get video metadata"""
        return {
            "fps": int(cap.get(cv2.CAP_PROP_FPS)),
            "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            "total_frames": int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        }
    
    @staticmethod
    def create_video_writer(output_path, fps, width, height):
        """Create VideoWriter for saving output"""
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        return cv2.VideoWriter(output_path, fourcc, fps, (width, height))


class MetricsLogger:
    """Log detection, density, and risk metrics for analysis"""
    
    def __init__(self, log_dir="logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.csv_file = self.log_dir / f"metrics_{self.session_id}.csv"
        self._init_csv()
    
    def _init_csv(self):
        """Initialize CSV with headers"""
        with open(self.csv_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                "timestamp", "person_count", "max_density", 
                "anomaly_score", "risk_level", "combined_score", "frame_number"
            ])
    
    def log(self, metrics, frame_number):
        """Log metrics for current frame"""
        with open(self.csv_file, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                datetime.now().isoformat(),
                metrics.get("person_count", 0),
                metrics.get("density", 0),
                metrics.get("anomaly", 0),
                metrics.get("risk", "Low"),
                metrics.get("combined_score", 0),
                frame_number
            ])
    
    def save_alert_event(self, metrics):
        """Save high-risk events separately"""
        alert_file = self.log_dir / f"alerts_{self.session_id}.json"
        alert_data = {
            "timestamp": datetime.now().isoformat(),
            "risk_level": metrics.get("risk"),
            "person_count": metrics.get("person_count"),
            "max_density": metrics.get("density"),
            "anomaly_score": metrics.get("anomaly"),
            "combined_score": metrics.get("combined_score")
        }
        
        events = []
        if alert_file.exists():
            with open(alert_file, 'r') as f:
                events = json.load(f)
        
        events.append(alert_data)
        
        with open(alert_file, 'w') as f:
            json.dump(events, f, indent=2)


class FrameAnnotator:
    """Advanced visualization utilities"""
    
    @staticmethod
    def draw_risk_banner(frame, risk_level, combined_score):
        """Draw prominent risk banner on frame"""
        h, w = frame.shape[:2]
        banner_height = 50
        
        risk_colors = {
            "Low": (0, 255, 0),
            "Medium": (0, 200, 255),
            "High": (0, 0, 255)
        }
        color = risk_colors.get(risk_level, (128, 128, 128))
        
        # Banner background
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (w, banner_height), color, -1)
        frame = cv2.addWeighted(overlay, 0.7, frame, 0.3, 0)
        
        # Banner text
        text = f"RISK LEVEL: {risk_level.upper()} | SCORE: {combined_score:.1f}"
        cv2.putText(frame, text, (20, 35), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)
        
        return frame
    
    @staticmethod
    def draw_density_zones(frame, density_map, grid_size=(4, 4)):
        """Draw grid lines and density numbers on zones"""
        h, w = frame.shape[:2]
        cell_h, cell_w = h // grid_size[0], w // grid_size[1]
        
        for i in range(grid_size[0]):
            for j in range(grid_size[1]):
                x1, y1 = j * cell_w, i * cell_h
                x2, y2 = (j + 1) * cell_w, (i + 1) * cell_h
                
                # Grid lines
                cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 255, 255), 1)
                
                # Density count
                count = density_map[i, j]
                text = str(count)
                text_pos = (x1 + cell_w//2 - 15, y1 + cell_h//2 + 10)
                cv2.putText(frame, text, text_pos,
                           cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        
        return frame
    
    @staticmethod
    def draw_motion_vectors(frame, tracks, previous_centroids):
        """Draw motion arrows showing movement direction"""
        for track in tracks:
            x1, y1, x2, y2, track_id = track
            centroid = np.array([(x1+x2)/2, (y1+y2)/2], dtype=np.int32)
            
            if track_id in previous_centroids:
                prev = previous_centroids[track_id].astype(np.int32)
                cv2.arrowedLine(frame, tuple(prev), tuple(centroid),
                              (0, 255, 255), 2, tipLength=0.3)
        
        return frame
    
    @staticmethod
    def create_dashboard_frame(frame, metrics, density_map, grid_size=(4, 4)):
        """Create complete dashboard view with all overlays"""
        frame = frame.copy()
        
        # Risk banner
        frame = FrameAnnotator.draw_risk_banner(
            frame, metrics.get("risk", "Low"), metrics.get("combined_score", 0)
        )
        
        # Density grid
        frame = FrameAnnotator.draw_density_zones(frame, density_map, grid_size)
        
        # Info panel (right side)
        h, w = frame.shape[:2]
        panel_x = w - 220
        cv2.rectangle(frame, (panel_x, 0), (w, h), (0, 0, 0, 128), -1)
        
        y = 80
        info_items = [
            ("Persons", metrics.get("person_count", 0)),
            ("Max Density", metrics.get("density", 0)),
            ("Anomaly", f"{metrics.get('anomaly', 0):.2f}"),
            ("Risk Score", f"{metrics.get('combined_score', 0):.1f}"),
        ]
        
        for label, value in info_items:
            cv2.putText(frame, f"{label}:", (panel_x + 10, y),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)
            cv2.putText(frame, str(value), (panel_x + 120, y),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            y += 35
        
        return frame


class ConfigLoader:
    """Load and validate configuration"""
    
    @staticmethod
    def load_from_file(config_path):
        """Load config from JSON file"""
        with open(config_path, 'r') as f:
            return json.load(f)
    
    @staticmethod
    def create_default_config():
        """Generate default configuration"""
        default_config = {
            "detection": {
                "model": "yolov8n.pt",
                "confidence": 0.5,
                "device": "cpu"
            },
            "tracking": {
                "max_age": 30
            },
            "density": {
                "grid_size": [4, 4],
                "thresholds": {
                    "low": 5,
                    "medium": 15,
                    "high": 30
                }
            },
            "risk": {
                "anomaly_threshold": 10,
                "density_weight": 0.7,
                "anomaly_weight": 0.3
            },
            "alerts": {
                "enabled": False,
                "cooldown_seconds": 60,
                "email": {"enabled": False},
                "sms": {"enabled": False}
            },
            "output": {
                "save_video": False,
                "log_metrics": True,
                "show_dashboard": True
            }
        }
        return default_config


def preprocess_frame(frame, target_size=(1280, 720)):
    """Resize and normalize frame"""
    frame = cv2.resize(frame, target_size)
    return frame


def calculate_optical_flow(prev_frame, current_frame):
    """Calculate sparse optical flow for movement analysis"""
    # Convert to grayscale
    prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
    curr_gray = cv2.cvtColor(current_frame, cv2.COLOR_BGR2GRAY)
    
    # Detect good features
    feature_params = dict(maxCorners=100, qualityLevel=0.3, minDistance=7, blockSize=7)
    p0 = cv2.goodFeaturesToTrack(prev_gray, mask=None, **feature_params)
    
    if p0 is None:
        return None, None
    
    # Calculate optical flow
    lk_params = dict(winSize=(15, 15), maxLevel=2,
                    criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 10, 0.03))
    p1, status, _ = cv2.calcOpticalFlowPyrLK(prev_gray, curr_gray, p0, None, **lk_params)
    
    if p1 is None:
        return None, None
    
    return p0[status == 1], p1[status == 1]


def format_timestamp():
    """Get formatted timestamp"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def create_directory_structure():
    """Create project directory structure"""
    dirs = [
        "logs",
        "output",
        "config",
        "models",
        "data/videos",
        "data/images"
    ]
    for d in dirs:
        os.makedirs(d, exist_ok=True)
    print("[✓] Directory structure created")