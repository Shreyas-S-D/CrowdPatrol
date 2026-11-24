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
from src.alert_manager import AlertManager, extract_spatial_risk_info

DEFAULT_CONFIG_PATH = BASE_DIR / "config" / "cameras.json"

class CameraState:
    """Independent tracking, density, motion, and telemetry state for a single camera stream."""
    def __init__(self, camera_id, name, source, source_type="video", device_name=None, enabled=True, detection_mode="PERSON", flow_interval=2, session_id=None, organization_id=None):
        self.id = camera_id
        self.name = name
        self.source = source
        self.source_type = str(source_type).lower() if source_type else "video"  # "video", "webcam", "rtsp"
        self.device_name = device_name
        self.enabled = enabled
        self.detection_mode = detection_mode  # "PERSON" or "HEAD"
        self.flow_interval = flow_interval
        self.session_id = session_id
        self.organization_id = organization_id
        
        self.cap = None
        self.status = "OFFLINE"  # ONLINE, STALE, CONNECTION FAILED, DISABLED, COMPLETED
        self.error_message = ""
        
        # Independent per-camera analytics components
        self.tracker = PersonTracker(max_age=30, n_init=1)
        self.motion_analyzer = CrowdMotionAnalyzer(grid_size=(4, 4), flow_interval=self.flow_interval)
        
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

        # Required Truthful Diagnostic Instrumentation
        self.source_frame_seq = 0
        self.processed_frame_seq = 0
        self.current_video_pos = 0
        self.last_capture_time = None
        self.last_processing_time = None
        self.frame_diff = 0.0
        self.is_frame_changed = True
        self.prev_raw_frame = None
        self.consecutive_drops = 0
        
        self.fps_deque = deque(maxlen=30)
        self.fps = 0.0
        self.last_update_time = None
        self.last_frame_finish_time = None
        
        # Transparent YOLO inference telemetry tracking
        self.yolo_inferences_count = 0
        self.yolo_fps_deque = deque(maxlen=20)
        self.yolo_inference_fps = 0.0
        self.last_yolo_time = None
        
    def open_source(self):
        """Initialize VideoCapture source with strict source validation."""
        if not self.enabled:
            self.status = "DISABLED"
            self.error_message = "Camera disabled"
            print(f"[{self.id}] Camera disabled", flush=True)
            return False
            
        print(f"[{self.id}] Opening {self.source_type.upper()} source: {self.source} (enabled={self.enabled})", flush=True)
        try:
            st_clean = self.source_type.lower()
            if st_clean in ("video", "preset_video", "upload_video"):
                src_str = str(self.source).strip() if self.source is not None else ""
                if not src_str or src_str.lower() in ("none", "null", ""):
                    self.status = "NOT_CONFIGURED"
                    self.error_message = "Video source file not configured. Please select or upload a video in Camera Slots."
                    print(f"[{self.id}] NOT_CONFIGURED: Video source file not configured.", flush=True)
                    return False
                file_path = Path(src_str)
                if not file_path.exists():
                    candidate_rel = BASE_DIR / src_str
                    candidate_vids = BASE_DIR / "data" / "videos" / file_path.name
                    if candidate_rel.exists():
                        file_path = candidate_rel
                    elif file_path.name and candidate_vids.exists():
                        file_path = candidate_vids
                    else:
                        self.status = "CONNECTION FAILED"
                        self.error_message = f"Video file not found: '{self.source}'"
                        print(f"[{self.id}] CONNECTION FAILED: Video file not found: '{self.source}'", flush=True)
                        return False
                src = str(file_path)
            elif st_clean in ("webcam", "laptop_camera", "usb_webcam"):
                src_val = str(self.source).strip() if self.source is not None else ""
                if not src_val or src_val.lower() in ("none", "null", ""):
                    self.status = "NOT_CONFIGURED"
                    dev_type_str = "USB webcam" if st_clean == "usb_webcam" else "Laptop camera"
                    self.error_message = f"{dev_type_str} device index not configured. Please select or enter device index in Camera Slots tab."
                    print(f"[{self.id}] NOT_CONFIGURED: {self.error_message}", flush=True)
                    return False
                try:
                    src = int(src_val)
                except (ValueError, TypeError):
                    self.status = "CONNECTION FAILED"
                    self.error_message = f"Invalid webcam device index: '{self.source}'"
                    print(f"[{self.id}] CONNECTION FAILED: Invalid webcam device index: '{self.source}'", flush=True)
                    return False

                # Check physical hardware device lock
                try:
                    if self.organization_id and self.session_id:
                        from src.resource_manager import get_device_registry
                        reg = get_device_registry()
                        dev_id = reg.normalize_device_id(src, "webcam")
                        if dev_id:
                            acquired, err_msg = reg.acquire_device(
                                device_id=dev_id,
                                organization_id=self.organization_id,
                                session_id=self.session_id,
                                slot_id=self.id
                            )
                            if not acquired:
                                self.status = "DEVICE_IN_USE"
                                self.error_message = err_msg or f"Webcam index {src} is currently in use."
                                print(f"[{self.id}] DEVICE_IN_USE: {self.error_message}", flush=True)
                                return False
                except Exception as e_reg:
                    pass
            elif st_clean in ("phone_link", "phone", "windows_phone"):
                src_val = str(self.source).strip() if self.source is not None else ""
                if not src_val or src_val.lower() in ("none", "null", ""):
                    self.status = "NOT_CONFIGURED"
                    self.error_message = "Phone Link camera not configured. In Camera Slots tab, select a Phone Link device (Windows Mobile Devices) or enter an IP stream URL."
                    print(f"[{self.id}] NOT_CONFIGURED: {self.error_message}", flush=True)
                    return False
                if src_val.startswith("http://") or src_val.startswith("https://") or src_val.startswith("rtsp://"):
                    src = src_val
                else:
                    try:
                        src = int(src_val)
                    except (ValueError, TypeError):
                        self.status = "CONNECTION FAILED"
                        self.error_message = f"Invalid Phone Link source: '{self.source}' (must be a device index or stream URL)"
                        return False
                    # Check physical hardware device lock for direct phone capture
                    try:
                        if self.organization_id and self.session_id:
                            from src.resource_manager import get_device_registry
                            reg = get_device_registry()
                            dev_id = reg.normalize_device_id(src, "webcam")
                            if dev_id:
                                acquired, err_msg = reg.acquire_device(
                                    device_id=dev_id,
                                    organization_id=self.organization_id,
                                    session_id=self.session_id,
                                    slot_id=self.id
                                )
                                if not acquired:
                                    self.status = "DEVICE_IN_USE"
                                    self.error_message = err_msg or f"Phone device index {src} is currently in use."
                                    print(f"[{self.id}] DEVICE_IN_USE: {self.error_message}", flush=True)
                                    return False
                    except Exception:
                        pass
            elif st_clean in ("rtsp", "phone_ip", "ip_camera", "video_url"):
                src = str(self.source).strip() if self.source is not None else ""
                if not src or src.lower() in ("none", "null", ""):
                    self.status = "NOT_CONFIGURED"
                    self.error_message = "Phone/IP stream URL not configured. Enter a valid stream URL (e.g. http://<IP>:8080/video) in Camera Slots tab."
                    print(f"[{self.id}] NOT_CONFIGURED: {self.error_message}", flush=True)
                    return False
                if not (src.startswith("rtsp://") or src.startswith("http://") or src.startswith("https://")):
                    self.status = "CONNECTION FAILED"
                    self.error_message = f"Invalid stream URL format: '{self.source}' (must start with http://, https://, or rtsp://)"
                    print(f"[{self.id}] CONNECTION FAILED: Invalid stream URL format: '{self.source}'", flush=True)
                    return False
            else:
                src = int(self.source) if str(self.source).isdigit() else str(self.source)

            try:
                self.cap = VideoProcessor.get_video_source(src, source_type=self.source_type)
            except TypeError:
                self.cap = VideoProcessor.get_video_source(src)

            if self.cap is not None and self.cap.isOpened():
                self.status = "ONLINE"
                self.error_message = ""
                print(f"[{self.id}] ONLINE: {self.source_type.upper()} source {self.source} opened successfully", flush=True)
                return True
            else:
                self.status = "CONNECTION FAILED"
                # Release hardware lock if open failed
                try:
                    from src.resource_manager import get_device_registry
                    reg = get_device_registry()
                    dev_id = reg.normalize_device_id(src, self.source_type)
                    if dev_id and self.organization_id and self.session_id:
                        reg.release_device(dev_id, self.organization_id, self.session_id)
                except Exception:
                    pass

                if st_clean in ("phone_link", "phone", "windows_phone"):
                    self.error_message = f"Phone Link camera device '{src}' could not be opened. Ensure camera sharing is active in Windows Settings -> Mobile Devices."
                elif st_clean == "usb_webcam":
                    self.error_message = f"Unable to open USB webcam index {src} (device disconnected or in use)."
                elif st_clean in ("laptop_camera", "webcam"):
                    actual_idx = 0 if (self.source is None or str(self.source).strip() == "") else self.source
                    self.error_message = f"Unable to open camera index {actual_idx} (device not found or disconnected)."
                elif st_clean in ("rtsp", "phone_ip", "ip_camera"):
                    self.error_message = f"Unable to connect to stream '{self.source}' (host unreachable or stream closed)."
                elif st_clean == "video_url":
                    self.error_message = f"Unable to open direct video URL '{self.source}'. Stream unreachable or invalid format."
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
        if self.organization_id and self.session_id:
            try:
                from src.resource_manager import get_device_registry
                reg = get_device_registry()
                dev_id = reg.normalize_device_id(self.source, self.source_type)
                if dev_id:
                    reg.release_device(dev_id, self.organization_id, self.session_id)
            except Exception:
                pass

    def reset_pipeline(self, detection_mode="PERSON"):
        """Reinitialize components when toggling detection mode or switching sources."""
        self.detection_mode = detection_mode
        self.tracker = PersonTracker(max_age=30, n_init=1)
        self.motion_analyzer = CrowdMotionAnalyzer(grid_size=(4, 4), flow_interval=self.flow_interval)
        
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

    def reconfigure(self, source, source_type=None, name=None, device_name=None, enabled=None, detection_mode=None):
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
        if detection_mode is not None:
            self.detection_mode = str(detection_mode).upper()
            
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
    def __init__(
        self,
        config_path=None,
        camera_configs=None,
        detection_mode="PERSON",
        device="cpu",
        detect_interval=3,
        tiled_mode=False,
        alert_manager=None,
        yolo_imgsz=640,
        flow_interval=2,
        stagger_detections=True,
        organization_id=None,
        session_id=None,
        tenant_op_service=None
    ):
        if config_path is None:
            config_path = DEFAULT_CONFIG_PATH
        self.config_path = Path(config_path)
        self.camera_configs = camera_configs
        self.organization_id = organization_id
        self.session_id = session_id
        self.tenant_op_service = tenant_op_service
        self.detection_mode = detection_mode  # "PERSON" or "HEAD"
        self.device = device
        self.detect_interval = detect_interval
        self.tiled_mode = tiled_mode
        if alert_manager is None:
            self.alert_manager = AlertManager(
                organization_id=self.organization_id,
                session_id=self.session_id,
                tenant_op_service=self.tenant_op_service
            )
        else:
            self.alert_manager = alert_manager
            if self.organization_id and not getattr(self.alert_manager, "organization_id", None):
                self.alert_manager.organization_id = self.organization_id
            if self.session_id and not getattr(self.alert_manager, "session_id", None):
                self.alert_manager.session_id = self.session_id
            if self.tenant_op_service and not getattr(self.alert_manager, "tenant_op_service", None):
                self.alert_manager.tenant_op_service = self.tenant_op_service
        self.yolo_imgsz = yolo_imgsz
        self.flow_interval = flow_interval
        self.stagger_detections = stagger_detections
        
        self.cameras = {}
        self._bg_round_robin_idx = 0
        from src.capture import FPSTracker
        self.grid_fps_tracker = FPSTracker(window_size=20, source_fps=30.0)
        self._shared_detector = None
        self._head_detector = None
        self._person_detector = None
        self._init_shared_detector()
        self.load_camera_config(camera_configs=self.camera_configs)

    def get_detector(self, mode="PERSON"):
        """Get or lazily instantiate detector for the specified mode without replacing the other."""
        mode = str(mode).upper()
        if mode == "HEAD":
            if self._head_detector is None:
                head_model_path = "models/crowdpatrol_yolov8n_head_v4.pt" if os.path.exists("models/crowdpatrol_yolov8n_head_v4.pt") else DEFAULT_HEAD_MODEL_PATH
                self._head_detector = ExperimentalHeadDetector(model_path=head_model_path, confidence=0.25, device=self.device, imgsz=640)
            return self._head_detector
        else:
            if self._person_detector is None:
                v2_model_path = "models/crowdpatrol_yolov8n_finetuned_v2.pt" if os.path.exists("models/crowdpatrol_yolov8n_finetuned_v2.pt") else "yolov8n.pt"
                self._person_detector = PersonDetector(model_path=v2_model_path, confidence=0.35, device=self.device, imgsz=self.yolo_imgsz)
            return self._person_detector

    @property
    def shared_detector(self):
        if self._shared_detector is not None:
            return self._shared_detector
        return self.get_detector(self.detection_mode)

    @shared_detector.setter
    def shared_detector(self, val):
        self._shared_detector = val
        
    def _init_shared_detector(self):
        """Instantiate single shared detector model to optimize CPU/RAM utilization."""
        self.get_detector(self.detection_mode)

    def load_camera_config(self, camera_configs=None):
        """Load camera definitions from a tenant config list or config JSON file."""
        if camera_configs is not None:
            self.camera_configs = camera_configs
            raw_list = camera_configs
        elif self.camera_configs is not None:
            raw_list = self.camera_configs
        else:
            if not self.config_path.exists():
                raise FileNotFoundError(f"Camera config file not found: {self.config_path}")
            with open(self.config_path, "r") as f:
                cfg = json.load(f)
            raw_list = cfg.get("cameras", [])

        self.cameras.clear()
        for cam_cfg in raw_list:
            if hasattr(cam_cfg, "slot_id"):
                cam_id = cam_cfg.slot_id
                cam_name = cam_cfg.name
                cam_src = cam_cfg.source
                source_type = cam_cfg.source_type
                device_name = cam_cfg.device_name
                enabled = cam_cfg.enabled
                detection_mode = getattr(cam_cfg, "detection_mode", None) or self.detection_mode
            else:
                cam_id = cam_cfg.get("slot_id", cam_cfg.get("id"))
                cam_name = cam_cfg.get("name", f"Camera {cam_id}")
                cam_src = cam_cfg.get("source", "")
                source_type = cam_cfg.get("source_type", "video")
                device_name = cam_cfg.get("device_name", None)
                enabled = cam_cfg.get("enabled", True)
                detection_mode = cam_cfg.get("detection_mode", self.detection_mode)

            detection_mode = str(detection_mode).upper() if detection_mode else self.detection_mode

            cam_state = CameraState(
                cam_id, cam_name, cam_src,
                source_type=source_type,
                device_name=device_name,
                enabled=enabled,
                detection_mode=detection_mode,
                flow_interval=self.flow_interval,
                session_id=self.session_id,
                organization_id=self.organization_id
            )
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

    def reconfigure_camera(self, camera_id, source, source_type=None, name=None, device_name=None, enabled=None, detection_mode=None):
        """
        Dynamically reconfigures capture source for a specific camera ID.
        Replaces active VideoCapture cleanly and resets camera temporal tracking state.
        """
        cam = self.cameras.get(camera_id)
        if cam is None:
            return False
        return cam.reconfigure(source, source_type=source_type, name=name, device_name=device_name, enabled=enabled, detection_mode=detection_mode)

    def start_all_cameras(self):
        """Open video stream sources for all enabled cameras."""
        success_count = 0
        for cam in self.cameras.values():
            if cam.enabled:
                if cam.open_source():
                    success_count += 1
        return success_count

    def stop_all_cameras(self):
        """Release all video stream resources cleanly and release locks."""
        for cam in self.cameras.values():
            cam.close_source()
        if self.organization_id and self.session_id:
            try:
                from src.resource_manager import get_device_registry, get_compute_scheduler
                get_device_registry().release_session_devices(self.organization_id, self.session_id)
                get_compute_scheduler().register_session_stop(self.session_id)
            except Exception:
                pass

    def step_camera(self, camera_id, annotate=True, is_focused=False):
        """
        Process a single frame for a specific camera ID.
        Uses shared YOLO detector for inference while executing independent per-camera tracking and risk calculations.
        If annotate=False, skips HUD and heatmap rendering for background surveillance efficiency.
        """
        cam = self.cameras.get(camera_id)
        if cam is None or not cam.enabled or cam.cap is None or not cam.cap.isOpened():
            return None

        t_start = time.perf_counter()
        ret, frame = cam.cap.read()
        
        # EOF Handling: Recorded videos rewind automatically; live streams (webcam/rtsp) DO NOT rewind.
        if not ret or frame is None:
            is_file_video = (
                cam.source_type.lower() in ("video", "preset_video", "upload_video", "uploaded_video", "file") 
                or hasattr(cam.cap, "file_path")
            )
            if is_file_video:
                cam.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame = cam.cap.read()
                if not ret or frame is None:
                    cam.close_source()
                    cam.open_source()
                    if cam.cap and cam.cap.isOpened():
                        ret, frame = cam.cap.read()
                if not ret or frame is None:
                    cam.status = "COMPLETED"
                    return None
                else:
                    cam.status = "ONLINE"
            else:
                cam.consecutive_drops += 1
                if cam.consecutive_drops >= 15 or cam.annotated_frame is None:
                    cam.status = "OFFLINE"
                    cam.error_message = "Live camera stream disconnected or ended."
                    return None
                if cam.annotated_frame is not None:
                    return cam.annotated_frame
                return None
        else:
            cam.consecutive_drops = 0
            if cam.status != "ONLINE":
                cam.status = "ONLINE"
                cam.error_message = ""

        now = time.time()
        cam.last_capture_time = now
        cam.source_frame_seq += 1

        # Current video position tracking
        if hasattr(cam.cap, "get"):
            cam.current_video_pos = int(cam.cap.get(cv2.CAP_PROP_POS_FRAMES))
        else:
            cam.current_video_pos = cam.source_frame_seq

        # Frame difference calculation for truthful diagnostics
        if cam.prev_raw_frame is not None and cam.prev_raw_frame.shape == frame.shape:
            diff = float(np.mean(np.abs(frame.astype(np.float32) - cam.prev_raw_frame.astype(np.float32))))
            cam.frame_diff = round(diff, 2)
            cam.is_frame_changed = bool(diff > 0.3)
        else:
            cam.frame_diff = 0.0
            cam.is_frame_changed = True
        cam.prev_raw_frame = frame.copy()

        # Standardize surveillance display resolution to 1280x720 for optimal rendering & stream efficiency
        if frame.shape[0] > 720 or frame.shape[1] > 1280:
            frame = cv2.resize(frame, (1280, 720), interpolation=cv2.INTER_LINEAR)

        cam.frame_count += 1
        cam.processed_frame_seq = cam.frame_count
        cam.current_frame = frame
        
        # 1. Detection & Tracking Scheduling
        if is_focused or not self.stagger_detections or len(self.cameras) <= 1:
            is_detection_frame = (cam.frame_count == 1 or cam.frame_count % self.detect_interval == 0)
        else:
            cam_keys = list(self.cameras.keys())
            try:
                cam_idx = cam_keys.index(camera_id)
            except ValueError:
                cam_idx = 0
            stride = max(len(cam_keys), self.detect_interval)
            is_detection_frame = (cam.frame_count == 1 or (cam.frame_count + cam_idx) % stride == 0)
        
        # Query active alert state for responsive HUD display
        alt_status = "NORMAL"
        if self.alert_manager is not None:
            if hasattr(self.alert_manager, "active_alerts") and cam.id in self.alert_manager.active_alerts:
                alt = self.alert_manager.active_alerts[cam.id]
                if getattr(alt, "acknowledged", False):
                    alt_status = "ACKNOWLEDGED"
                else:
                    alt_status = f"ACTIVE ({getattr(alt, 'severity', 'HIGH')})"
            elif getattr(cam, "risk_level", "LOW") in ("HIGH", "CRITICAL"):
                alt_status = f"ACTIVE ({cam.risk_level})"

        # Ensure camera pipeline matches its configured detection mode
        cam_mode = getattr(cam, "detection_mode", "PERSON").upper()
        if cam_mode not in ("PERSON", "HEAD"):
            cam_mode = "PERSON"

        active_detector = self._shared_detector if self._shared_detector is not None else self.get_detector(cam_mode)

        if cam_mode == "HEAD":
            if is_detection_frame:
                t_yolo_now = time.perf_counter()
                if cam.last_yolo_time is not None:
                    yolo_interval = t_yolo_now - cam.last_yolo_time
                    if yolo_interval > 0:
                        cam.yolo_fps_deque.append(1.0 / yolo_interval)
                cam.last_yolo_time = t_yolo_now
                cam.yolo_inferences_count += 1
                if cam.yolo_fps_deque:
                    cam.yolo_inference_fps = float(np.mean(cam.yolo_fps_deque))
                cam.raw_detections = active_detector.detect(frame, tiled=self.tiled_mode)
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
            dens_res = cam.density_estimator.calculate_density(cam.visible_tracks, frame.shape)
            if isinstance(dens_res, tuple):
                cam.density_map = dens_res[0]
                cam.max_density = int(dens_res[1])
            else:
                cam.density_map = dens_res
                cam.max_density = int(np.max(dens_res)) if dens_res is not None else 0
            
            if cam.risk_adapter is None:
                cam.risk_adapter = ExperimentalHeadRiskAdapter()

            risk_info = cam.risk_adapter.calculate_experimental_head_risk(
                total_heads=cam.active_count,
                max_head_cell=cam.max_density,
                frame_idx=cam.frame_count,
                anomaly_score=cam.anomaly_score,
                visible_heads=cam.visible_count
            )
            cam.risk_level = risk_info["risk_level"].upper()
            cam.risk_score = risk_info["smoothed_score"]
            
            if annotate:
                # Render Head Mode Annotations (visible tracks only)
                heatmap_base, _ = generate_heatmap(frame, cam.visible_tracks, draw_grid=False)
                cam.annotated_frame = FrameAnnotator.create_head_dashboard_frame(
                    heatmap_base,
                    {
                        "camera_id": cam.id,
                        "camera_name": cam.name,
                        "mode": "Head Mode",
                        "visible_heads": cam.visible_count,
                        "active_tracks": cam.active_count,
                        "person_count": cam.active_count,
                        "density": cam.max_density,
                        "anomaly": cam.anomaly_score,
                        "avg_speed": cam.avg_speed,
                        "dominant_direction": cam.dominant_direction,
                        "risk": cam.risk_level,
                        "combined_score": cam.risk_score,
                        "alert_state": alt_status,
                        "fps": cam.fps
                    },
                    cam.density_map,
                    grid_size=(4, 4),
                    grid_matrix=grid_matrix,
                    tracks=cam.visible_tracks
                )
            else:
                cam.annotated_frame = frame
        else:
            if is_detection_frame:
                t_yolo_now = time.perf_counter()
                if cam.last_yolo_time is not None:
                    yolo_interval = t_yolo_now - cam.last_yolo_time
                    if yolo_interval > 0:
                        cam.yolo_fps_deque.append(1.0 / yolo_interval)
                cam.last_yolo_time = t_yolo_now
                cam.yolo_inferences_count += 1
                if cam.yolo_fps_deque:
                    cam.yolo_inference_fps = float(np.mean(cam.yolo_fps_deque))
                cam.raw_detections = active_detector.detect(frame)
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
            dens_res = cam.density_estimator.calculate_density(cam.active_tracks, frame.shape)
            if isinstance(dens_res, tuple):
                cam.density_map = dens_res[0]
                cam.max_density = int(dens_res[1])
            else:
                cam.density_map = dens_res
                cam.max_density = int(np.max(dens_res)) if dens_res is not None else 0

            if cam.risk_assessor is None:
                cam.risk_assessor = RiskAssessor()

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
            
            if annotate:
                # Render Person Mode Annotations
                heatmap_base, _ = generate_heatmap(frame, cam.active_tracks, draw_grid=False)
                cam.annotated_frame = FrameAnnotator.create_dashboard_frame(
                    heatmap_base,
                    {
                        "camera_id": cam.id,
                        "camera_name": cam.name,
                        "mode": "Person Mode",
                        "person_count": cam.active_count,
                        "active_tracks": cam.active_count,
                        "visible_heads": 0,
                        "density": cam.max_density,
                        "anomaly": cam.anomaly_score,
                        "avg_speed": cam.avg_speed,
                        "dominant_direction": cam.dominant_direction,
                        "risk": cam.risk_level,
                        "combined_score": cam.risk_score,
                        "alert_state": alt_status,
                        "fps": cam.fps
                    },
                    cam.density_map,
                    grid_size=(4, 4),
                    grid_matrix=grid_matrix,
                    tracks=cam.active_tracks
                )
            else:
                cam.annotated_frame = frame
            
        t_end = time.perf_counter()
        dur_ms = (t_end - t_start) * 1000.0
        frame_fps = 1000.0 / dur_ms if dur_ms > 0 else 0.0
        
        if cam.last_frame_finish_time is not None:
            interval = t_end - cam.last_frame_finish_time
            if interval > 0:
                cam.fps_deque.append(1.0 / interval)
            else:
                cam.fps_deque.append(frame_fps)
        else:
            cam.fps_deque.append(frame_fps)
            
        cam.last_frame_finish_time = t_end
        cam.fps = float(np.mean(cam.fps_deque))
        cam.last_update_time = datetime.now().isoformat()
        cam.last_processing_time = time.time()
        
        # Process camera telemetry through AlertManager for discrete alert events
        if self.alert_manager is not None:
            telemetry = self.get_camera_telemetry_payload(camera_id)
            if telemetry:
                self.alert_manager.process_camera_telemetry(cam.id, cam.name, telemetry)
        
        return cam.annotated_frame

    def step_all(self):
        """Step forward 1 frame sequentially across all enabled online cameras."""
        self.grid_fps_tracker.start_frame()
        processed = {}
        for cam_id, cam in self.cameras.items():
            if cam.enabled and cam.status == "ONLINE":
                frame_out = self.step_camera(cam_id)
                if frame_out is not None:
                    processed[cam_id] = frame_out
        self.grid_fps_tracker.end_frame()
        return processed

    def step_focus(self, focus_cam_id: str, step_background: bool = True):
        """
        Processes a dedicated frame for the focused camera while maintaining background
        alert surveillance via round-robin stepping of background cameras.
        This delivers high display FPS on the focused feed while guaranteeing that
        abnormal crowd density and safety emergencies in background feeds are still caught.
        """
        self.grid_fps_tracker.start_frame()
        processed = {}
        
        # 1. Step the focused camera with highest priority (full annotation, is_focused=True)
        if focus_cam_id in self.cameras:
            cam = self.cameras[focus_cam_id]
            if cam.enabled and cam.status == "ONLINE":
                frame_out = self.step_camera(focus_cam_id, annotate=True, is_focused=True)
                if frame_out is not None:
                    processed[focus_cam_id] = frame_out

        # 2. Step one background camera round-robin per cycle for background surveillance (lightweight, annotate=False)
        if step_background:
            bg_candidates = [
                c_id for c_id, c in self.cameras.items()
                if c_id != focus_cam_id and c.enabled and c.status == "ONLINE"
            ]
            if bg_candidates:
                bg_id = bg_candidates[self._bg_round_robin_idx % len(bg_candidates)]
                self._bg_round_robin_idx = (self._bg_round_robin_idx + 1) % len(bg_candidates)
                bg_frame = self.step_camera(bg_id, annotate=False, is_focused=False)
                if bg_frame is not None:
                    processed[bg_id] = bg_frame

        self.grid_fps_tracker.end_frame()
        return processed

    def get_aggregate_throughput(self) -> float:
        """
        Calculates aggregate processed frames per second across all active cameras.
        Aggregate throughput = sum(camera.fps for camera in active_cameras).
        """
        active_fps = [
            cam.fps for cam in self.cameras.values()
            if cam.enabled and cam.status == "ONLINE" and cam.fps > 0
        ]
        return float(sum(active_fps)) if active_fps else 0.0

    def get_throughput_metrics(self) -> dict:
        """
        Returns transparent telemetry separating:
          1. Display FPS (rolling refresh rate of the current view)
          2. Actual YOLO inference FPS per camera
          3. Aggregate system throughput (frames/sec across all cameras)
        """
        yolo_fps_dict = {
            cam_id: round(cam.yolo_inference_fps, 2)
            for cam_id, cam in self.cameras.items()
            if cam.enabled and cam.status == "ONLINE"
        }
        display_fps_dict = {
            cam_id: round(cam.fps, 2)
            for cam_id, cam in self.cameras.items()
            if cam.enabled and cam.status == "ONLINE"
        }
        return {
            "display_fps": display_fps_dict,
            "grid_display_fps": round(self.get_grid_fps(), 2),
            "yolo_inference_fps": yolo_fps_dict,
            "aggregate_throughput_fps": round(self.get_aggregate_throughput(), 2)
        }

    def get_grid_fps(self) -> float:
        """Returns the rolling aggregate iterations/second of the CCTV command center grid."""
        return self.grid_fps_tracker.rolling_fps

    def get_active_alerts(self):
        """Returns currently active alert events across all cameras."""
        if self.alert_manager is not None:
            return self.alert_manager.get_active_alerts()
        return []

    def get_unacknowledged_high_alerts(self):
        """Returns active HIGH risk alerts that have not been acknowledged."""
        if self.alert_manager is not None:
            return self.alert_manager.get_unacknowledged_high_alerts()
        return []

    def get_pending_alarm_alerts(self):
        """Returns active HIGH risk alerts needing sound alarm trigger."""
        if self.alert_manager is not None:
            return self.alert_manager.get_pending_alarm_alerts()
        return []

    def attach_notification_dispatcher(self, dispatcher):
        """Attaches notification dispatcher to the underlying AlertManager."""
        if self.alert_manager and hasattr(self.alert_manager, "attach_notification_dispatcher"):
            self.alert_manager.attach_notification_dispatcher(dispatcher)

    def acknowledge_alert(self, camera_id, operator_id="Operator"):
        """Marks active alert for camera_id as acknowledged."""
        if self.alert_manager is not None:
            return self.alert_manager.acknowledge_alert(camera_id, operator_id=operator_id)
        return False

    def resolve_alert(self, camera_id, operator_id="Operator", note=None):
        """Resolves active alert for camera_id."""
        if self.alert_manager is not None:
            return self.alert_manager.resolve_alert(camera_id, operator_id=operator_id, note=note)
        return False

    def get_alert_by_id(self, alert_id):
        """Retrieves alert by alert_id."""
        if self.alert_manager is not None:
            return self.alert_manager.get_alert_by_id(alert_id)
        return None

    def get_alert_summary(self):
        """Returns high-level alert summary dictionary."""
        if self.alert_manager is not None:
            return self.alert_manager.get_alert_summary()
        return {"active": 0, "critical": 0, "high": 0, "medium": 0, "resolved": 0, "total_history": 0}

    def get_alert_history(self, limit=50, status=None, camera_id=None):
        """Returns recent alert event history across all cameras."""
        if self.alert_manager is not None:
            return self.alert_manager.get_alert_history(limit=limit, status=status, camera_id=camera_id)
        return []

    def get_overall_system_risk(self):
        """
        Aggregates risk level across all online cameras.
        Returns overall status = highest current camera risk level.
        """
        risk_weights = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1, "UNKNOWN": 0}
        
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
            
        spatial_info = extract_spatial_risk_info(cam.density_map)

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
            "primary_risk_zone": spatial_info["primary_risk_zone"],
            "primary_zone_density": spatial_info["primary_zone_density"],
            "zone_description": spatial_info["zone_description"],
            "secondary_zones": spatial_info["secondary_zones"],
            "density_map": cam.density_map.tolist() if hasattr(cam.density_map, "tolist") else cam.density_map,
            "risk_level": cam.risk_level,
            "risk_score": cam.risk_score,
            "combined_score": cam.risk_score,
            "anomaly_score": cam.anomaly_score,
            "avg_speed": cam.avg_speed,
            "dominant_direction": cam.dominant_direction,
            "camera_motion_detected": cam.camera_motion_detected,
            "fps": cam.fps,
            "last_frame_time": cam.last_update_time or datetime.now().isoformat(),
            "source_frame_seq": getattr(cam, "source_frame_seq", 0),
            "processed_frame_seq": getattr(cam, "processed_frame_seq", 0),
            "current_video_pos": getattr(cam, "current_video_pos", 0),
            "last_capture_time": getattr(cam, "last_capture_time", None),
            "last_processing_time": getattr(cam, "last_processing_time", None),
            "frame_diff": getattr(cam, "frame_diff", 0.0),
            "is_frame_changed": getattr(cam, "is_frame_changed", True)
        }
