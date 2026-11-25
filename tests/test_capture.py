import pytest
import numpy as np
import time
from pathlib import Path
from src.capture import FPSTracker, LowLatencyLiveCapture, OptimizedFileCapture, create_capture_source
from src.camera_devices import (
    build_phone_stream_url,
    mask_stream_url,
    verify_stream_source,
    verify_camera_source
)
from unittest.mock import MagicMock, patch

VIDEO_PATH = "data/videos/youtube_crowd_test.mp4"

def test_fps_tracker():
    tracker = FPSTracker(window_size=10, source_fps=30.0)
    for _ in range(5):
        tracker.start_frame()
        time.sleep(0.01) # 10 ms -> ~100 FPS
        rolling_fps = tracker.end_frame()
        assert rolling_fps > 0
    stats = tracker.get_fps_stats()
    assert stats["source_fps"] == 30.0
    assert stats["rolling_fps"] > 0
    assert stats["total_frames"] == 5

def test_optimized_file_capture():
    if Path(VIDEO_PATH).exists():
        cap = create_capture_source(VIDEO_PATH, source_type="video")
        assert cap.isOpened()
        ret, frame = cap.read()
        assert ret is True
        assert frame is not None
        assert frame.shape[0] > 0
        stats = cap.get_stats()
        assert stats["source_type"] == "video_file"
        assert stats["current_frame"] == 1
        cap.release()
        assert not cap.isOpened()

def test_low_latency_live_capture_simulated():
    if Path(VIDEO_PATH).exists():
        cap = LowLatencyLiveCapture(VIDEO_PATH)
        assert cap.isOpened()
        time.sleep(0.1)
        ret, frame = cap.read()
        assert ret is True
        assert frame is not None
        stats = cap.get_stats()
        assert stats["source_type"] == "live"
        cap.release()
        assert not cap.isOpened()


# ==============================================================================
# Phone Camera & Stream Validation Tests
# ==============================================================================

def test_build_phone_stream_url():
    """Verifies standard URL formatting across phone camera apps."""
    # IP Webcam default
    url1 = build_phone_stream_url("192.168.1.50", port=8080, endpoint="video")
    assert url1 == "http://192.168.1.50:8080/video"

    # DroidCam default
    url2 = build_phone_stream_url("192.168.1.60", port=4747, endpoint="video")
    assert url2 == "http://192.168.1.60:4747/video"

    # RTSP format
    url3 = build_phone_stream_url("192.168.1.70", port=8554, endpoint="live", protocol="rtsp")
    assert url3 == "rtsp://192.168.1.70:8554/live"

    # Direct pass-through if already a full URL
    url4 = build_phone_stream_url("http://10.0.0.5:8080/video")
    assert url4 == "http://10.0.0.5:8080/video"


def test_mask_stream_url():
    """Verifies credentials in stream URLs are masked for privacy."""
    raw = "rtsp://admin:secretPass123@192.168.1.100:554/stream1"
    masked = mask_stream_url(raw)
    assert "secretPass123" not in masked
    assert "admin:***@" in masked

    raw_http = "http://user:mypassword@192.168.1.45:8080/video"
    masked_http = mask_stream_url(raw_http)
    assert "mypassword" not in masked_http
    assert "user:***@" in masked_http


def test_verify_stream_source_success_mock():
    """Verifies successful phone/IP camera probe using mocked cv2.VideoCapture."""
    with patch("cv2.VideoCapture") as mock_cap_cls:
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.read.return_value = (True, np.zeros((720, 1280, 3), dtype=np.uint8))
        mock_cap.get.side_effect = lambda prop: 1280.0 if prop == 3 else 720.0
        mock_cap_cls.return_value = mock_cap

        ok, msg, res, status = verify_stream_source("http://192.168.1.50:8080/video", timeout_sec=2.0)
        assert ok is True
        assert status == "CONNECTED"
        assert "1280x720" in res
        assert mock_cap.release.called


def test_verify_stream_source_invalid():
    """Verifies handling of invalid or empty stream source."""
    ok, msg, res, status = verify_stream_source(None)
    assert ok is False
    assert status == "INVALID_STREAM"


def test_verify_stream_source_timeout_handling():
    """Verifies that unreachable stream URLs time out cleanly without blocking."""
    def _slow_open(*args, **kwargs):
        time.sleep(0.5)
        mock = MagicMock()
        mock.isOpened.return_value = False
        return mock

    with patch("cv2.VideoCapture", side_effect=_slow_open):
        t0 = time.perf_counter()
        ok, msg, res, status = verify_stream_source("http://192.168.254.254:8080/video", timeout_sec=0.1)
        elapsed = time.perf_counter() - t0

        assert ok is False
        assert status == "CONNECTION_TIMEOUT"
        assert elapsed < 0.35  # Must not hang indefinitely


def test_phone_stream_creates_low_latency_live_capture():
    """Verifies that phone stream URLs instantiate LowLatencyLiveCapture rather than file capture."""
    with patch("cv2.VideoCapture") as mock_cap_cls:
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.read.return_value = (True, np.zeros((480, 640, 3), dtype=np.uint8))
        mock_cap.get.side_effect = lambda prop: 30.0 if prop == 5 else (640.0 if prop == 3 else 480.0)
        mock_cap_cls.return_value = mock_cap

        # URL source with source_type="phone"
        cap = create_capture_source("http://192.168.1.50:8080/video", source_type="phone")
        assert isinstance(cap, LowLatencyLiveCapture)
        assert cap.isOpened()
        cap.release()
        assert not cap.isOpened()

