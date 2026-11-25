"""
CrowdPatrol Backend — AI Pipeline & Video Streaming Service
Orchestrates multi-camera CCTV capture, YOLOv8 object detection, DeepSORT tracking,
density calculation, motion dynamics, risk assessment, and live MJPEG/WebSocket streaming.
"""

import os
import sys
import time
import json
import asyncio
import threading
from pathlib import Path
from typing import Dict, Any, Optional, Set
from collections import deque
import cv2
import numpy as np

BASE_DIR = Path(__file__).parent.parent.parent
sys.path.append(str(BASE_DIR))

from src.multi_camera_manager import MultiCameraManager, CameraState
from src.detection import PersonDetector
from src.experimental_head_mode import ExperimentalHeadDetector, DEFAULT_HEAD_MODEL_PATH
from src.heatmap import generate_heatmap
from backend.services.alert_service import get_alert_service
from dashboard.dashboard_utils import normalize_telemetry_payload


class PipelineService:
    def __init__(self):
        self.alert_service = get_alert_service()
        self.lock = threading.Lock()
        self.is_running = False
        self.thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # Operational configuration
        self.operating_mode = "GRID"  # "GRID" (Multi-camera) or "DIRECT" (Single camera)
        self.detection_mode = "PERSON"  # "PERSON" or "HEAD"
        self.tiled_mode = False
        self.confidence = 0.35
        self.detect_interval = 3
        self.device = "cpu"
        self.focus_camera_id: Optional[str] = "CAM-01"

        # Frame buffers (JPEG encoded)
        self.latest_grid_jpeg: Optional[bytes] = None
        self.latest_camera_jpegs: Dict[str, bytes] = {}
        self.latest_heatmap_jpeg: Optional[bytes] = None

        # Telemetry & History
        self.latest_telemetry: Dict[str, Any] = {
            "fps": 0.0,
            "person_count": 0,
            "max_density": 0.0,
            "risk_level": "Low",
            "combined_score": 0.0,
            "raw_score": 0.0,
            "growth_rate": 0.0,
            "data_quality_score": 1.0,
            "avg_speed": 0.0,
            "dominant_direction": "STATIC",
            "camera_motion_detected": False,
            "anomaly_score": 0.0,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "active_mode": "PERSON",
            "operating_mode": "GRID",
            "focus_camera": "CAM-01",
            "system_running": False
        }
        self.history_limit = 60
        self.time_history = deque(maxlen=self.history_limit)
        self.risk_history = deque(maxlen=self.history_limit)
        self.person_history = deque(maxlen=self.history_limit)
        self.density_history = deque(maxlen=self.history_limit)

        # Multi-camera engine
        self.multi_camera: Optional[MultiCameraManager] = None
        self._init_engine()

        # WebSocket subscribers
        self.active_websockets: Set[Any] = set()

    def _init_engine(self):
        """Initialize MultiCameraManager with alert integration."""
        try:
            self.multi_camera = MultiCameraManager(
                detection_mode=self.detection_mode,
                device=self.device,
                detect_interval=self.detect_interval,
                tiled_mode=self.tiled_mode,
                alert_manager=self.alert_service.alert_manager,
                yolo_imgsz=640
            )
        except Exception as e:
            print(f"[PipelineService] Error initializing MultiCameraManager: {e}")
            self.multi_camera = None

    def start(self) -> Dict[str, Any]:
        """Start the background pipeline capture and inference worker thread."""
        with self.lock:
            if self.is_running:
                return {"status": "already_running", "message": "Pipeline is already active"}

            self._stop_event.clear()
            self.is_running = True
            self.latest_telemetry["system_running"] = True

            # Open all cameras in multi_camera manager
            if self.multi_camera:
                self.multi_camera.start_all_cameras()

            self.thread = threading.Thread(target=self._worker_loop, daemon=True, name="CrowdPatrol-PipelineWorker")
            self.thread.start()
            return {"status": "started", "message": "Pipeline worker successfully started"}

    def stop(self) -> Dict[str, Any]:
        """Stop the background pipeline worker cleanly."""
        with self.lock:
            if not self.is_running:
                return {"status": "not_running", "message": "Pipeline is not running"}

            self.is_running = False
            self._stop_event.set()

        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=3.0)

        if self.multi_camera:
            self.multi_camera.stop_all_cameras()

        self.latest_telemetry["system_running"] = False
        return {"status": "stopped", "message": "Pipeline stopped cleanly"}

    def set_detection_mode(self, mode: str, tiled: bool = False) -> Dict[str, Any]:
        """Switch detection target between PERSON and HEAD (with optional 2x2 tiling)."""
        mode_upper = mode.upper()
        if mode_upper not in ["PERSON", "HEAD"]:
            return {"success": False, "error": "Invalid mode. Choose PERSON or HEAD"}

        self.detection_mode = mode_upper
        self.tiled_mode = tiled if mode_upper == "HEAD" else False
        if mode_upper == "HEAD":
            self.confidence = 0.25
        else:
            self.confidence = 0.35

        if self.multi_camera:
            self.multi_camera.set_detection_mode(self.detection_mode, tiled_mode=self.tiled_mode)

        self.latest_telemetry["active_mode"] = self.detection_mode
        return {
            "success": True,
            "detection_mode": self.detection_mode,
            "tiled_mode": self.tiled_mode,
            "confidence": self.confidence
        }

    def set_focus_camera(self, camera_id: str) -> Dict[str, Any]:
        """Change Focus Feed camera in Multi-Camera mode."""
        self.focus_camera_id = camera_id
        self.latest_telemetry["focus_camera"] = camera_id
        return {"success": True, "focus_camera": camera_id}

    def set_operating_mode(self, mode: str) -> Dict[str, Any]:
        """Set operating mode: 'GRID' or 'FOCUS'."""
        mode_upper = mode.upper()
        if mode_upper in ["GRID", "FOCUS"]:
            self.operating_mode = mode_upper
            self.latest_telemetry["operating_mode"] = mode_upper
            return {"success": True, "operating_mode": self.operating_mode}
        return {"success": False, "error": f"Invalid operating mode: {mode}"}

    def reconfigure_camera_source(self, camera_id: str, source: Any, source_type: str = "video", name: Optional[str] = None, enabled: bool = True) -> Dict[str, Any]:
        """Dynamically update source for a single camera feed or add new feed."""
        if not self.multi_camera:
            return {"success": False, "error": "MultiCameraManager not initialized"}

        if camera_id not in self.multi_camera.cameras:
            from src.multi_camera_manager import CameraState
            new_cam = CameraState(
                camera_id=camera_id,
                name=name or f"Camera {camera_id}",
                source=source,
                source_type=source_type,
                enabled=enabled,
                detection_mode=self.detection_mode
            )
            self.multi_camera.cameras[camera_id] = new_cam
            if self.is_running and enabled:
                new_cam.open_source()
            return {"success": True, "camera_id": camera_id, "status": new_cam.status, "action": "added"}

        ok = self.multi_camera.reconfigure_camera(
            camera_id=camera_id,
            source=source,
            source_type=source_type,
            name=name,
            enabled=enabled
        )
        return {"success": ok, "camera_id": camera_id, "status": self.multi_camera.cameras[camera_id].status, "action": "updated"}

    def remove_camera(self, camera_id: str) -> Dict[str, Any]:
        """Remove a camera feed dynamically and release capture handles."""
        if not self.multi_camera or camera_id not in self.multi_camera.cameras:
            return {"success": False, "error": f"Camera {camera_id} not found"}

        cam = self.multi_camera.cameras[camera_id]
        cam.close_source()
        del self.multi_camera.cameras[camera_id]
        if camera_id in self.latest_camera_jpegs:
            del self.latest_camera_jpegs[camera_id]

        # Reset focus camera if deleted
        if self.focus_camera_id == camera_id:
            remaining = list(self.multi_camera.cameras.keys())
            self.focus_camera_id = remaining[0] if remaining else None
            self.latest_telemetry["focus_camera"] = self.focus_camera_id

        return {"success": True, "camera_id": camera_id, "message": f"Camera {camera_id} removed"}

    def _update_composite_grid(self):
        """Generate a composite 1280x720 2x2 CCTV grid frame from the managed cameras."""
        target_cams = ["CAM-01", "CAM-02", "CAM-03", "CAM-04"]
        cells = []
        cell_w, cell_h = 640, 360

        for cid in target_cams:
            cam_obj = self.multi_camera.cameras.get(cid) if self.multi_camera else None
            if cam_obj and cam_obj.status == "ONLINE" and cam_obj.annotated_frame is not None and cam_obj.annotated_frame.size > 0:
                cell = cv2.resize(cam_obj.annotated_frame, (cell_w, cell_h))
            else:
                # Standby blank quadrant with camera metadata
                cell = np.zeros((cell_h, cell_w, 3), dtype=np.uint8)
                cell[:] = (23, 14, 10)  # BGR dark navy #0a0e17
                cname = cam_obj.name if cam_obj else cid
                cstatus = cam_obj.status if cam_obj else "OFFLINE"
                cv2.putText(cell, f"{cid} • {cname}", (20, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 210, 255), 2)
                cv2.putText(cell, f"Status: {cstatus}", (20, 190), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (160, 160, 160), 1)
                cv2.putText(cell, "Camera Feed Standby", (20, 230), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (100, 100, 100), 1)
            cells.append(cell)

        # Assemble 2x2 grid (1280x720)
        top_row = np.hstack([cells[0], cells[1]])
        bot_row = np.hstack([cells[2], cells[3]])
        grid = np.vstack([top_row, bot_row])

        # Grid line divider overlay (subtle 2px lines)
        grid[cell_h - 1:cell_h + 1, :] = (0, 180, 230)
        grid[:, cell_w - 1:cell_w + 1] = (0, 180, 230)

        _, grid_buf = cv2.imencode('.jpg', grid, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
        self.latest_grid_jpeg = grid_buf.tobytes()

    def _generate_standby_frame(self, text: str = "CrowdPatrol AI Video Standby") -> bytes:
        """Create a clean dark CCTV standby frame when streaming is paused or offline."""
        standby = np.zeros((480, 640, 3), dtype=np.uint8)
        standby[:] = (23, 14, 10)
        cv2.putText(standby, text, (60, 220), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 210, 255), 2)
        cv2.putText(standby, "Click 'Start Monitoring' to activate camera feed", (60, 260), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (180, 180, 180), 1)
        _, buf = cv2.imencode('.jpg', standby)
        return buf.tobytes()

    def _worker_loop(self):
        """Primary AI execution loop running in background daemon thread."""
        last_fb_sync = time.time()
        frame_iter = 0

        while not self._stop_event.is_set():
            loop_start = time.time()
            frame_iter += 1

            if self.multi_camera:
                try:
                    # 1. Step cameras according to operating mode
                    if self.operating_mode == "FOCUS" and self.focus_camera_id:
                        frames_dict = self.multi_camera.step_focus(self.focus_camera_id, step_background=True)
                    else:
                        frames_dict = self.multi_camera.step_all()

                    if frames_dict:
                        # 2. Encode individual camera JPEGs
                        for cam_id, frame in frames_dict.items():
                            if frame is not None and frame.size > 0:
                                _, buf = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
                                self.latest_camera_jpegs[cam_id] = buf.tobytes()

                        # 3. Generate CCTV 2x2 grid composite frame
                        self._update_composite_grid()

                        # 4. Generate & encode Heatmap from focus camera (every 2 frames for efficiency)
                        target_cam = self.focus_camera_id if self.focus_camera_id else "CAM-01"
                        if frame_iter % 2 == 0:
                            focus_cam_obj = self.multi_camera.cameras.get(target_cam)
                            if focus_cam_obj and focus_cam_obj.current_frame is not None:
                                try:
                                    tracks = getattr(focus_cam_obj, "visible_tracks", [])
                                    hm_frame, _ = generate_heatmap(
                                        focus_cam_obj.current_frame,
                                        tracks,
                                        grid_cols=8,
                                        grid_rows=6,
                                        draw_grid=True
                                    )
                                    if hm_frame is not None and hm_frame.size > 0:
                                        _, hm_buf = cv2.imencode('.jpg', hm_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
                                        self.latest_heatmap_jpeg = hm_buf.tobytes()
                                except Exception:
                                    pass

                        # 5. Extract telemetry payload
                        payload = self.multi_camera.get_camera_telemetry_payload(target_cam)
                        if payload:
                            fps_val = float(self.multi_camera.grid_fps_tracker.rolling_fps)
                            ts = time.strftime("%H:%M:%S")

                            self.latest_telemetry.update({
                                "fps": round(fps_val, 1),
                                "person_count": int(payload.get("person_count", 0)),
                                "max_density": round(float(payload.get("max_density", 0.0)), 2),
                                "risk_level": payload.get("risk_level", "Low"),
                                "combined_score": round(float(payload.get("combined_score", 0.0)), 1),
                                "raw_score": round(float(payload.get("raw_score", 0.0)), 1),
                                "growth_rate": round(float(payload.get("growth_rate", 0.0)), 2),
                                "data_quality_score": round(float(payload.get("data_quality_score", 1.0)), 2),
                                "avg_speed": round(float(payload.get("avg_speed", 0.0)), 2),
                                "dominant_direction": payload.get("dominant_direction", "STATIC"),
                                "camera_motion_detected": bool(payload.get("camera_motion_detected", False)),
                                "anomaly_score": round(float(payload.get("anomaly_score", 0.0)), 2),
                                "timestamp": ts,
                                "active_mode": self.detection_mode,
                                "operating_mode": self.operating_mode,
                                "focus_camera": self.focus_camera_id or "CAM-01",
                                "system_running": True
                            })

                            # Update historical queues for analytics
                            self.time_history.append(ts)
                            self.risk_history.append(self.latest_telemetry["combined_score"])
                            self.person_history.append(self.latest_telemetry["person_count"])
                            self.density_history.append(self.latest_telemetry["max_density"])

                        # 6. Periodic Firebase Sync
                        if time.time() - last_fb_sync > 1.0:
                            last_fb_sync = time.time()
                            self.alert_service.sync_telemetry_to_firebase(self.latest_telemetry)

                except Exception:
                    # Non-fatal worker loop protection
                    pass

            elapsed = time.time() - loop_start
            sleep_time = max(0.005, (1.0 / 30.0) - elapsed)
            time.sleep(sleep_time)

    def get_latest_jpeg(self, camera_id: Optional[str] = None, layout: Optional[str] = None) -> bytes:
        """Return latest JPEG bytes for streaming (composite grid or specific camera)."""
        # 1. If a specific camera was requested
        if camera_id:
            if camera_id in self.latest_camera_jpegs:
                return self.latest_camera_jpegs[camera_id]
            cam_obj = self.multi_camera.cameras.get(camera_id) if self.multi_camera else None
            cam_name = cam_obj.name if cam_obj else camera_id
            return self._generate_standby_frame(f"{camera_id} • {cam_name}")

        # 2. Check layout override or current operating mode
        effective_layout = layout.lower() if layout else self.operating_mode.lower()
        if effective_layout == "focus":
            target = self.focus_camera_id or "CAM-01"
            if target in self.latest_camera_jpegs:
                return self.latest_camera_jpegs[target]

        if self.latest_grid_jpeg:
            return self.latest_grid_jpeg

        return self._generate_standby_frame("CrowdPatrol CCTV Command Center Standby")

    def get_latest_heatmap_jpeg(self) -> bytes:
        """Return latest density heatmap JPEG bytes."""
        if self.latest_heatmap_jpeg:
            return self.latest_heatmap_jpeg
        return self._generate_standby_frame("Density Heatmap Standby")

    def get_analytics_summary(self) -> Dict[str, Any]:
        """Return comprehensive analytics data including history queues for dashboard charts."""
        return {
            "current": self.latest_telemetry,
            "history": {
                "timestamps": list(self.time_history),
                "risk_scores": list(self.risk_history),
                "person_counts": list(self.person_history),
                "densities": list(self.density_history)
            },
            "cameras_status": {
                cam_id: cam.get_debug_info()
                for cam_id, cam in (self.multi_camera.cameras.items() if self.multi_camera else {}.items())
            }
        }


_pipeline_service_instance: Optional[PipelineService] = None

def get_pipeline_service() -> PipelineService:
    global _pipeline_service_instance
    if _pipeline_service_instance is None:
        _pipeline_service_instance = PipelineService()
    return _pipeline_service_instance
