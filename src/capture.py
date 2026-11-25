"""
CrowdPatrol Phase 16 — Low-Latency Video Capture & FPS Tracking Architecture
Provides multi-threaded bounded capture for live cameras (webcam, RTSP)
to eliminate buffer queue staleness, optimized sequential capture for video files,
and unified real-time FPS tracking.
"""

import time
import threading
from collections import deque
from pathlib import Path
from typing import Tuple, Optional, Union, Dict, Any
import cv2
import numpy as np


class FPSTracker:
    """
    Robust, jitter-free real-time FPS tracker using time.perf_counter().
    Calculates:
    - Native source FPS.
    - Instantaneous frame processing FPS.
    - Rolling average pipeline FPS (including rendering and Streamlit overhead).
    """
    def __init__(self, window_size: int = 30, source_fps: float = 30.0):
        self.window_size = window_size
        self.source_fps = float(source_fps)
        self.durations = deque(maxlen=window_size)
        self.intervals = deque(maxlen=window_size)
        self.last_frame_finish_time: Optional[float] = None
        self.t_start: Optional[float] = None
        self.current_fps: float = 0.0
        self.rolling_fps: float = float(source_fps) if source_fps > 0 else 30.0
        self.total_frames: int = 0

    def start_frame(self):
        """Mark the beginning of frame processing."""
        self.t_start = time.perf_counter()

    def end_frame(self) -> float:
        """Mark the completion of frame processing and return current rolling FPS."""
        now = time.perf_counter()
        if self.t_start is not None:
            dur = now - self.t_start
            if dur > 0:
                self.durations.append(dur)
                self.current_fps = 1.0 / dur

        if self.last_frame_finish_time is not None:
            interval = now - self.last_frame_finish_time
            if interval > 0:
                self.intervals.append(interval)

        self.last_frame_finish_time = now
        self.total_frames += 1

        if self.durations:
            avg_dur = float(np.mean(self.durations))
            self.rolling_fps = (1.0 / avg_dur) if avg_dur > 0 else 0.0

        return self.rolling_fps

    def get_fps_stats(self) -> Dict[str, float]:
        """Return structured FPS telemetry."""
        return {
            "source_fps": round(self.source_fps, 1),
            "instant_fps": round(self.current_fps, 1),
            "rolling_fps": round(self.rolling_fps, 1),
            "total_frames": self.total_frames
        }


class LowLatencyLiveCapture:
    """
    Dedicated background capture thread for live camera feeds (webcam, USB camera, RTSP).
    Drains the driver video buffer continuously into a bounded latest-frame buffer,
    completely preventing stale frame accumulation and multi-second display lag.
    """
    def __init__(self, source: Union[int, str], backend: Optional[int] = None):
        self.source = source
        self.backend = backend
        self.cap: Optional[cv2.VideoCapture] = None
        self.running: bool = False
        self.thread: Optional[threading.Thread] = None

        self.lock = threading.Lock()
        self.latest_frame: Optional[np.ndarray] = None
        self.last_valid_frame: Optional[np.ndarray] = None
        self.latest_timestamp: float = 0.0
        self.frame_number: int = 0
        self.dropped_frames: int = 0
        self.is_opened: bool = False
        self.source_fps: float = 30.0
        self.width: int = 0
        self.height: int = 0

        self._init_capture()

    def _init_capture(self):
        try:
            # Handle int index conversion
            actual_src = int(self.source) if isinstance(self.source, str) and self.source.isdigit() else self.source
            if self.backend is not None:
                self.cap = cv2.VideoCapture(actual_src, self.backend)
            else:
                self.cap = cv2.VideoCapture(actual_src)

            if isinstance(actual_src, str) and (actual_src.startswith("http://") or actual_src.startswith("https://") or actual_src.startswith("rtsp://")):
                try:
                    self.cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000)
                    self.cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 5000)
                except Exception:
                    pass

            if self.cap is not None and self.cap.isOpened():
                # Attempt to minimize native OS driver buffer to 1 frame
                try:
                    self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                except Exception:
                    pass

                self.is_opened = True
                fps = self.cap.get(cv2.CAP_PROP_FPS)
                self.source_fps = float(fps) if fps > 0 and not np.isnan(fps) else 30.0
                self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                self._start_thread()
            else:
                self.is_opened = False
        except Exception:
            self.is_opened = False
            self.cap = None

    def _start_thread(self):
        self.running = True
        self.thread = threading.Thread(target=self._capture_worker, daemon=True)
        self.thread.start()

    def _capture_worker(self):
        consecutive_failures = 0
        actual_src = int(self.source) if isinstance(self.source, str) and self.source.isdigit() else self.source
        is_net = isinstance(actual_src, str) and (actual_src.startswith("http://") or actual_src.startswith("https://") or actual_src.startswith("rtsp://"))

        while self.running:
            if not self.cap or not self.cap.isOpened():
                if is_net and self.running:
                    # Attempt safe reconnection for network/phone streams after disconnect
                    time.sleep(1.0)
                    try:
                        self.cap = cv2.VideoCapture(actual_src)
                        if self.cap.isOpened():
                            consecutive_failures = 0
                            self.is_opened = True
                    except Exception:
                        pass
                else:
                    break
                continue

            ret, frame = self.cap.read()
            if not ret or frame is None:
                consecutive_failures += 1
                if is_net and consecutive_failures > 30:
                    # Mark connection dropped, release and retry
                    self.is_opened = False
                    try:
                        self.cap.release()
                    except Exception:
                        pass
                    self.cap = None
                time.sleep(0.01)
                continue

            consecutive_failures = 0
            self.is_opened = True
            now = time.perf_counter()
            with self.lock:
                if self.latest_frame is not None:
                    self.dropped_frames += 1
                self.latest_frame = frame
                self.last_valid_frame = frame
                self.latest_timestamp = now
                self.frame_number += 1

    def read(self) -> Tuple[bool, Optional[np.ndarray]]:
        """
        Returns the freshest available frame with zero queue delay.
        Blocks for up to 150ms if no frame has arrived yet.
        """
        if not self.is_opened:
            return False, None

        t0 = time.perf_counter()
        while self.running:
            with self.lock:
                if self.latest_frame is not None:
                    frame = self.latest_frame
                    self.latest_frame = None  # Consume frame
                    return True, frame
            if (time.perf_counter() - t0) > 0.15:
                break
            time.sleep(0.002)

        return False, None

    def isOpened(self) -> bool:
        return self.is_opened and (self.cap is not None and self.cap.isOpened())

    def get(self, prop_id: int) -> float:
        if self.cap is not None:
            return self.cap.get(prop_id)
        return 0.0

    def set(self, prop_id: int, value: float) -> bool:
        if self.cap is not None:
            return self.cap.set(prop_id, value)
        return False

    def release(self):
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=0.5)
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        self.is_opened = False
        with self.lock:
            self.latest_frame = None
            self.last_valid_frame = None

    def get_stats(self) -> Dict[str, Any]:
        return {
            "source_type": "live",
            "source_fps": self.source_fps,
            "width": self.width,
            "height": self.height,
            "total_frames_grabbed": self.frame_number,
            "dropped_stale_frames": self.dropped_frames
        }


class OptimizedFileCapture:
    """
    Optimized capture wrapper for video files.
    Preserves sequential decoding and accurate EOF handling.
    """
    def __init__(self, file_path: str):
        self.file_path = str(file_path)
        self.cap: Optional[cv2.VideoCapture] = cv2.VideoCapture(self.file_path)
        self.is_opened: bool = self.cap.isOpened()
        self.source_fps: float = float(self.cap.get(cv2.CAP_PROP_FPS)) if self.is_opened else 30.0
        if self.source_fps <= 0 or np.isnan(self.source_fps):
            self.source_fps = 30.0
        self.width: int = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)) if self.is_opened else 0
        self.height: int = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) if self.is_opened else 0
        self.total_frames: int = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT)) if self.is_opened else 0
        self.current_frame_idx: int = 0

    def read(self) -> Tuple[bool, Optional[np.ndarray]]:
        if not self.is_opened or self.cap is None:
            return False, None
        ret, frame = self.cap.read()
        if ret:
            self.current_frame_idx += 1
        return ret, frame

    def isOpened(self) -> bool:
        return self.is_opened and (self.cap is not None and self.cap.isOpened())

    def get(self, prop_id: int) -> float:
        if prop_id == cv2.CAP_PROP_POS_FRAMES:
            return float(self.current_frame_idx)
        if self.cap is not None:
            return self.cap.get(prop_id)
        return 0.0

    def set(self, prop_id: int, value: float) -> bool:
        if prop_id == cv2.CAP_PROP_POS_FRAMES:
            self.current_frame_idx = int(value)
        if self.cap is not None:
            res = self.cap.set(prop_id, value)
            if prop_id == cv2.CAP_PROP_POS_FRAMES and value == 0 and not res:
                self.cap.release()
                self.cap = cv2.VideoCapture(self.file_path)
                self.is_opened = bool(self.cap.isOpened())
                return self.is_opened
            return bool(res)
        return False

    def release(self):
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        self.is_opened = False

    def get_stats(self) -> Dict[str, Any]:
        return {
            "source_type": "video_file",
            "source_fps": self.source_fps,
            "width": self.width,
            "height": self.height,
            "current_frame": self.current_frame_idx,
            "total_frames": self.total_frames
        }


def create_capture_source(source: Union[int, str], source_type: str = "video", backend: Optional[int] = None):
    """
    Factory function providing low-latency live capture for live streams (webcam/rtsp/phone)
    and optimized sequential capture for video files.
    """
    st = str(source_type).lower()
    is_network = isinstance(source, str) and (source.startswith("http://") or source.startswith("https://") or source.startswith("rtsp://"))
    is_live = (st in ["webcam", "live", "rtsp", "camera", "phone", "phone_ip", "ip_camera"]) or (isinstance(source, int)) or (isinstance(source, str) and source.isdigit()) or is_network
    if is_live:
        return LowLatencyLiveCapture(source, backend=backend)
    else:
        return OptimizedFileCapture(source)
