"""
CrowdPatrol Phase 13 — Multi-Camera Crowd Monitoring Manager.
Orchestrates multiple independent CCTV video feeds while sharing a single YOLO detector
instance for computational efficiency. Each camera maintains strict independence for:
- DeepSORT tracker state
- Spatial density estimation state
- Optical flow motion analysis state
- Risk assessment state
- Telemetry & status metrics
"""

import os
import sys
import time
import json
import cv2
import numpy as np
from datetime import datetime
from pathlib import Path
from collections import deque

BASE_DIR = Path(__file__).parent.parent
sys.path.append(str(BASE_DIR))

from src.detection import PersonDetector
from src.tracking import PersonTracker
from src.density import DensityEstimator
from src.motion_analysis import CrowdMotionAnalyzer
from src.risk_assessment import RiskAssessor
from src.experimental_head_mode import ExperimentalHeadDetector, DEFAULT_HEAD_MODEL_PATH
from src.experimental_head_density import HeadDensityEstimator
from src.experimental_head_risk import ExperimentalHeadRiskAdapter
from src.heatmap import generate_heatmap
from src.utils import VideoProcessor, FrameAnnotator

DEFAULT_CONFIG_PATH = BASE_DIR / "config" / "cameras.json"

class CameraState:
    """Independent tracking, density, motion, and telemetry state for a single camera stream."""
    def __init__(self, camera_id, name, source, source_type="video", device_name=None, enabled=True, detection_mode="PERSON"):
        self.id = camera_id
        self.name = name
        self.source = source
        self.source_type = str(source_type).lower() if source_type else "video"  # "video", "webcam", "rtsp"
        self.device_name = device_name
        self.enabled = enabled
        self.detection_mode = detection_mode  # "PERSON" or "HEAD"
        
        self.cap = None
        self.status = "OFFLINE"  # ONLINE, STALE, CONNECTION FAILED, DISABLED, COMPLETED
        self.error_message = ""
        
        # Independent per-camera analytics components
        self.tracker = PersonTracker(max_age=30, n_init=1)
        self.motion_analyzer = CrowdMotionAnalyzer(grid_size=(4, 4))
        
        if self.detection_mode == "HEAD":
            self.density_estimator = HeadDensityEstimator(grid_size=(4, 4))
            self.risk_adapter = ExperimentalHeadRiskAdapter()
            self.risk_assessor = None
        else:
            self.density_estimator = DensityEstimator(grid_size=(4, 4))
            self.risk_assessor = RiskAssessor()
            self.risk_adapter = None
            
        # Per-camera runtime telemetry state
        self.frame_count = 0
        self.current_frame = None
        self.annotated_frame = None
        self.visible_tracks = []
        self.active_tracks = []
        self.raw_detections = []
        self.visible_count = 0
        self.active_count = 0
        self.max_density = 0
        self.density_map = np.zeros((4, 4), dtype=int)
        self.anomaly_score = 0.0
        self.avg_speed = 0.0
        self.dominant_direction = "STATIONARY"
        self.camera_motion_detected = False
        self.risk_level = "LOW"
        self.risk_score = 0.0
        
        self.fps_deque = deque(maxlen=30)
        self.fps = 0.0
        self.last_update_time = None
        
    def open_source(self):
        """Initialize VideoCapture source with strict source validation."""
        if not self.enabled:
            self.status = "DISABLED"
            self.error_message = "Camera disabled"
            print(f"[{self.id}] Camera disabled", flush=True)
            return False
            
        print(f"[{self.id}] Opening {self.source_type.upper()} source: {self.source} (enabled={self.enabled})", flush=True)
        try:
            if self.source_type == "video":
                file_path = Path(str(self.source))
                if not file_path.exists():
                    self.status = "CONNECTION FAILED"
                    self.error_message = f"Video file not found: '{self.source}'"
                    print(f"[{self.id}] CONNECTION FAILED: Video file not found: '{self.source}'", flush=True)
                    return False
                src = str(file_path)
            elif self.source_type == "webcam":
                try:
                    src = int(self.source)
                except (ValueError, TypeError):
                    self.status = "CONNECTION FAILED"
                    self.error_message = f"Invalid webcam device index: '{self.source}'"
                    print(f"[{self.id}] CONNECTION FAILED: Invalid webcam device index: '{self.source}'", flush=True)
                    return False
            elif self.source_type == "rtsp":
                src = str(self.source)
                if not (src.startswith("rtsp://") or src.startswith("http://") or src.startswith("https://")):
                    self.status = "CONNECTION FAILED"
                    self.error_message = f"Invalid RTSP URL format: '{self.source}'"
                    print(f"[{self.id}] CONNECTION FAILED: Invalid RTSP URL format: '{self.source}'", flush=True)
                    return False
            else:
                src = int(self.source) if str(self.source).isdigit() else str(self.source)

            self.cap = VideoProcessor.get_video_source(src)
            if self.cap is not None and self.cap.isOpened():
                self.status = "ONLINE"
                self.error_message = ""
                print(f"[{self.id}] ONLINE: {self.source_type.upper()} source {self.source} opened successfully", flush=True)
                return True
            else:
                self.status = "CONNECTION FAILED"
                if self.source_type == "webcam":
                    self.error_message = f"Unable to open camera index {self.source}."
                elif self.source_type == "rtsp":
                    self.error_message = f"Unable to connect to RTSP stream '{self.source}'."
                else:
                    self.error_message = f"Unable to open video source '{self.source}'."
                print(f"[{self.id}] CONNECTION FAILED: {self.error_message}", flush=True)
                return False
        except Exception as e:
            self.status = "CONNECTION FAILED"
            self.error_message = str(e)
            print(f"[{self.id}] CONNECTION FAILED Exception: {e}", flush=True)
            return False

    def close_source(self):
        """Release VideoCapture resources cleanly."""
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        if self.status != "DISABLED":
            self.status = "OFFLINE"

    def reset_pipeline(self, detection_mode="PERSON"):
        """Reinitialize components when toggling detection mode or switching sources."""
        self.detection_mode = detection_mode
        self.tracker = PersonTracker(max_age=30, n_init=1)
        self.motion_analyzer = CrowdMotionAnalyzer(grid_size=(4, 4))
        
        if self.detection_mode == "HEAD":
            self.density_estimator = HeadDensityEstimator(grid_size=(4, 4))
            self.risk_adapter = ExperimentalHeadRiskAdapter()
            self.risk_assessor = None
        else:
            self.density_estimator = DensityEstimator(grid_size=(4, 4))
            self.risk_assessor = RiskAssessor()
            self.risk_adapter = None
            
        self.frame_count = 0
        self.visible_tracks = []
        self.active_tracks = []
        self.raw_detections = []
        self.fps_deque.clear()

    def reconfigure(self, source, source_type=None, name=None, device_name=None, enabled=None):
        """
        Dynamically reconfigures capture source and type.
        Replaces existing capture cleanly, resets temporal state, and attempts opening new source.
        """
        print(f"[{self.id}] RECONFIGURING: {self.source_type} ({self.source}) -> {source_type} ({source})", flush=True)
        # 1. Close existing capture
        self.close_source()
        
        # 2. Update source metadata
        if name is not None:
            self.name = name
        if source_type is not None:
            self.source_type = str(source_type).lower()
        if device_name is not None:
            self.device_name = device_name
        self.source = source
        if enabled is not None:
            self.enabled = enabled
            
        # 3. Reset temporal tracking & optical flow state so old tracks don't leak onto new feed
        self.reset_pipeline(detection_mode=self.detection_mode)
        
        # 4. Open new source
        if self.enabled:
            return self.open_source()
        else:
            self.status = "DISABLED"
            self.error_message = "Camera disabled"
            return False

    def get_debug_info(self):
        """Return dict of active runtime camera capture diagnostic information."""
        return {
            "camera_id": self.id,
            "name": self.name,
            "configured_source_type": self.source_type,
            "configured_source": str(self.source),
            "device_name": self.device_name,
            "active_source_type": self.source_type if (self.cap is not None and self.cap.isOpened()) else "NONE",
            "active_source": str(self.source) if (self.cap is not None and self.cap.isOpened()) else "NONE",
            "status": self.status,
            "error_message": self.error_message,
            "capture_opened": bool(self.cap is not None and self.cap.isOpened())
        }


class MultiCameraManager:
    """
    Central orchestration manager for multi-camera CCTV crowd monitoring feeds.
    Shares a single YOLO detector across all cameras while isolating per-camera state.
    """
    def __init__(self, config_path=None, detection_mode="PERSON", device="cpu", detect_interval=3, tiled_mode=False):
        if config_path is None:
            config_path = DEFAULT_CONFIG_PATH
        self.config_path = Path(config_path)
        self.detection_mode = detection_mode  # "PERSON" or "HEAD"
        self.device = device
        self.detect_interval = detect_interval
        self.tiled_mode = tiled_mode
        
        self.cameras = {}
        self.shared_detector = None
        self._init_shared_detector()
        self.load_camera_config()
        
    def _init_shared_detector(self):
        """Instantiate single shared detector model to optimize CPU/RAM utilization."""
        if self.detection_mode == "HEAD":
            head_model_path = "models/crowdpatrol_yolov8n_head_v4.pt" if os.path.exists("models/crowdpatrol_yolov8n_head_v4.pt") else DEFAULT_HEAD_MODEL_PATH
            self.shared_detector = ExperimentalHeadDetector(model_path=head_model_path, confidence=0.25, device=self.device, imgsz=640)
        else:
            v2_model_path = "models/crowdpatrol_yolov8n_finetuned_v2.pt" if os.path.exists("models/crowdpatrol_yolov8n_finetuned_v2.pt") else "yolov8n.pt"
            self.shared_detector = PersonDetector(model_path=v2_model_path, confidence=0.35, device=self.device)

    def load_camera_config(self):
        """Load camera definitions from config JSON file."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Camera config file not found: {self.config_path}")
            
        with open(self.config_path, "r") as f:
            cfg = json.load(f)
            
        self.cameras.clear()
        for cam_cfg in cfg.get("cameras", []):
            cam_id = cam_cfg["id"]
            cam_name = cam_cfg["name"]
            cam_src = cam_cfg["source"]
            source_type = cam_cfg.get("source_type", "video")
            device_name = cam_cfg.get("device_name", None)
            enabled = cam_cfg.get("enabled", True)
            
            cam_state = CameraState(cam_id, cam_name, cam_src, source_type=source_type, device_name=device_name, enabled=enabled, detection_mode=self.detection_mode)
            self.cameras[cam_id] = cam_state

    def set_detection_mode(self, new_mode, tiled_mode=False):
        """Switch detection mode globally across all managed cameras."""
        if new_mode not in ["PERSON", "HEAD"]:
            raise ValueError(f"Invalid detection mode: {new_mode}")
            
        if self.detection_mode != new_mode or self.tiled_mode != tiled_mode:
            self.detection_mode = new_mode
            self.tiled_mode = tiled_mode
            self._init_shared_detector()
            for cam in self.cameras.values():
                cam.reset_pipeline(detection_mode=new_mode)

    def reconfigure_camera(self, camera_id, source, source_type=None, name=None, device_name=None, enabled=None):
        """
        Dynamically reconfigures capture source for a specific camera ID.
        Replaces active VideoCapture cleanly and resets camera temporal tracking state.
        """
        cam = self.cameras.get(camera_id)
        if cam is None:
            return False
        return cam.reconfigure(source, source_type=source_type, name=name, device_name=device_name, enabled=enabled)

    def start_all_cameras(self):
        """Open video stream sources for all enabled cameras."""
        success_count = 0
        for cam in self.cameras.values():
            if cam.enabled:
                if cam.open_source():
                    success_count += 1
        return success_count

    def stop_all_cameras(self):
        """Release all video stream resources cleanly."""
        for cam in self.cameras.values():
            cam.close_source()

    def step_camera(self, camera_id):
        """
        Process a single frame for a specific camera ID.
        Uses shared YOLO detector for inference while executing independent per-camera tracking and risk calculations.
        """
        cam = self.cameras.get(camera_id)
        if cam is None or not cam.enabled or cam.cap is None or not cam.cap.isOpened():
            return None

        t_start = time.perf_counter()
        ret, frame = cam.cap.read()
        
        # EOF Handling: Recorded videos rewind automatically; live streams (webcam/rtsp) DO NOT rewind.
        if not ret:
            if cam.source_type == "video":
                cam.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame = cam.cap.read()
                if not ret:
                    cam.status = "COMPLETED"
                    return None
            else:
                cam.status = "OFFLINE"
                cam.error_message = "Live camera stream disconnected or ended."
                return None

        cam.frame_count += 1
        cam.current_frame = frame.copy()
        
        # 1. Detection & Tracking Step
        is_detection_frame = (cam.frame_count == 1 or cam.frame_count % self.detect_interval == 0)
        
        if self.detection_mode == "HEAD":
            if is_detection_frame:
                cam.raw_detections = self.shared_detector.detect(frame, tiled=self.tiled_mode)
                cam.active_tracks = cam.tracker.update(cam.raw_detections, frame)
            else:
                cam.active_tracks = cam.tracker.predict()
                
            cam.visible_tracks = cam.tracker.get_visible_tracks()
            cam.visible_count = len(cam.visible_tracks) if len(cam.visible_tracks) > 0 else len(cam.raw_detections)
            cam.active_count = len(cam.active_tracks)
            
            # Optical Flow Crowd Motion Analysis
            grid_matrix, motion_summary = cam.motion_analyzer.analyze_frame(frame)
            cam.avg_speed = motion_summary.get("avg_speed", 0.0)
            cam.dominant_direction = motion_summary.get("dominant_direction", "STATIONARY")
            cam.camera_motion_detected = motion_summary.get("camera_motion_detected", False)
            cam.anomaly_score = motion_summary.get("anomaly_score", 0.0)
            
            # Spatial Head Density & Experimental Risk calculation
            cam.density_map, cam.max_density, _ = cam.density_estimator.calculate_density(cam.visible_tracks, frame.shape)
            
            risk_info = cam.risk_adapter.calculate_experimental_head_risk(
                total_heads=cam.active_count,
                max_head_cell=cam.max_density,
                frame_idx=cam.frame_count,
                anomaly_score=cam.anomaly_score,
                visible_heads=cam.visible_count
            )
            cam.risk_level = risk_info["risk_level"].upper()
            cam.risk_score = risk_info["smoothed_score"]
            
            # Render Head Mode Annotations (visible tracks only)
            heatmap_base, _ = generate_heatmap(frame, cam.visible_tracks, draw_grid=False)
            cam.annotated_frame = FrameAnnotator.create_head_dashboard_frame(
                heatmap_base,
                {
                    "visible_heads": cam.visible_count,
                    "person_count": cam.active_count,
                    "density": cam.max_density,
                    "anomaly": cam.anomaly_score,
                    "avg_speed": cam.avg_speed,
                    "dominant_direction": cam.dominant_direction,
                    "risk": cam.risk_level,
                    "combined_score": cam.risk_score
                },
                cam.density_map,
                grid_size=(4, 4),
                grid_matrix=grid_matrix,
                tracks=cam.visible_tracks
            )
        else:
            if is_detection_frame:
                cam.raw_detections = self.shared_detector.detect(frame)
                cam.active_tracks = cam.tracker.update(cam.raw_detections, frame)
            else:
                cam.active_tracks = cam.tracker.predict()
                
            cam.visible_tracks = cam.tracker.get_visible_tracks()
            cam.visible_count = len(cam.active_tracks)
            cam.active_count = len(cam.active_tracks)
            
            # Optical Flow Motion Analysis
            grid_matrix, motion_summary = cam.motion_analyzer.analyze_frame(frame)
            cam.avg_speed = motion_summary.get("avg_speed", 0.0)
            cam.dominant_direction = motion_summary.get("dominant_direction", "STATIONARY")
            cam.camera_motion_detected = motion_summary.get("camera_motion_detected", False)
            
            # Person Density & Production Risk Assessment
            cam.density_map, cam.max_density = cam.density_estimator.calculate_density(cam.active_tracks, frame.shape)
            cam.anomaly_score = cam.risk_assessor.calculate_movement_anomaly(cam.active_tracks, frame.shape)
            
            risk_res = cam.risk_assessor.assess_frame(
                max_density=cam.max_density,
                motion_summary=motion_summary,
                tracks=cam.active_tracks,
                timestamp=time.time(),
                anomaly_score=cam.anomaly_score
            )
            cam.risk_level = str(risk_res["risk"]).upper()
            cam.risk_score = float(risk_res["combined_score"])
            
            # Render Person Mode Annotations
            heatmap_base, _ = generate_heatmap(frame, cam.active_tracks, draw_grid=False)
            cam.annotated_frame = FrameAnnotator.create_dashboard_frame(
                heatmap_base,
                {
                    "person_count": cam.active_count,
                    "density": cam.max_density,
                    "anomaly": cam.anomaly_score,
                    "avg_speed": cam.avg_speed,
                    "dominant_direction": cam.dominant_direction,
                    "risk": cam.risk_level,
                    "combined_score": cam.risk_score
                },
                cam.density_map,
                grid_size=(4, 4),
                grid_matrix=grid_matrix,
                tracks=cam.active_tracks
            )
            
        t_end = time.perf_counter()
        dur_ms = (t_end - t_start) * 1000.0
        frame_fps = 1000.0 / dur_ms if dur_ms > 0 else 0.0
        cam.fps_deque.append(frame_fps)
        cam.fps = float(np.mean(cam.fps_deque))
        cam.last_update_time = datetime.now().isoformat()
        
        return cam.annotated_frame

    def step_all(self):
        """Step forward 1 frame sequentially across all enabled online cameras."""
        processed = {}
        for cam_id, cam in self.cameras.items():
            if cam.enabled and cam.status == "ONLINE":
                frame_out = self.step_camera(cam_id)
                if frame_out is not None:
                    processed[cam_id] = frame_out
        return processed

    def get_overall_system_risk(self):
        """
        Aggregates risk level across all online cameras.
        Returns overall status = highest current camera risk level.
        """
        risk_weights = {"HIGH": 3, "MEDIUM": 2, "LOW": 1, "UNKNOWN": 0}
        
        highest_weight = 0
        highest_level = "LOW"
        highest_cam_id = "N/A"
        highest_cam_name = "N/A"
        highest_score = 0.0
        
        active_camera_count = 0
        
        for cam in self.cameras.values():
            if cam.enabled and cam.status == "ONLINE":
                active_camera_count += 1
                level = cam.risk_level.upper()
                w = risk_weights.get(level, 0)
                if w > highest_weight or (w == highest_weight and cam.risk_score > highest_score):
                    highest_weight = w
                    highest_level = level
                    highest_cam_id = cam.id
                    highest_cam_name = cam.name
                    highest_score = cam.risk_score
                    
        return {
            "overall_risk_level": highest_level,
            "highest_risk_camera_id": highest_cam_id,
            "highest_risk_camera_name": highest_cam_name,
            "highest_risk_score": highest_score,
            "active_camera_count": active_camera_count
        }

    def get_camera_telemetry_payload(self, camera_id):
        """Generates namespaced telemetry dictionary payload for a camera."""
        cam = self.cameras.get(camera_id)
        if cam is None:
            return None
            
        return {
            "camera_id": cam.id,
            "camera_name": cam.name,
            "source": str(cam.source),
            "source_type": cam.source_type,
            "status": cam.status,
            "error_message": cam.error_message,
            "mode": self.detection_mode,
            "visible_heads": cam.visible_count if self.detection_mode == "HEAD" else 0,
            "person_count": cam.active_count,
            "max_density": cam.max_density,
            "risk_level": cam.risk_level,
            "risk_score": cam.risk_score,
            "combined_score": cam.risk_score,
            "anomaly_score": cam.anomaly_score,
            "avg_speed": cam.avg_speed,
            "dominant_direction": cam.dominant_direction,
            "camera_motion_detected": cam.camera_motion_detected,
            "fps": cam.fps,
            "last_frame_time": cam.last_update_time or datetime.now().isoformat()
        }
