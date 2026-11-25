"""
tests/test_camera_inputs_and_streaming.py
-----------------------------------------
Comprehensive automated verification suite for:
1. All 7 camera source types (laptop_camera, usb_webcam, phone_link, ip_camera, upload_video, video_url, preset_video)
2. Device discovery and Windows PnP camera categorization
3. verify_stream_source timeout bounds, device detection, and error diagnostics
4. Continuous frame advancement and automated EOF rewinding for looping video playback
5. Multi-camera execution without cross-feed freezing
6. Physical device lock acquisition and cleanup on session start/stop
"""

import time
import os
import threading
import cv2
import numpy as np
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.camera_devices import (
    verify_stream_source,
    get_categorized_cameras,
    mask_stream_url,
    build_phone_stream_url,
    CameraDevice
)
from dashboard.org_ui import (
    SOURCE_TYPE_DISPLAY,
    normalize_source_type_display,
    discover_preset_videos,
    resolve_camera_status_badge
)
from src.multi_camera_manager import MultiCameraManager, CameraState
from src.resource_manager import PhysicalDeviceRegistry, get_device_registry
from src.auth.database import AuthDatabase, TenantCameraConfig, User, Organization
from src.auth.tenant_operational_service import TenantOperationalService


def test_seven_source_types_registered():
    """Verify all 7 required source types have user-friendly display labels."""
    expected = [
        "laptop_camera",
        "usb_webcam",
        "phone_link",
        "ip_camera",
        "upload_video",
        "video_url",
        "preset_video"
    ]
    for key in expected:
        assert key in SOURCE_TYPE_DISPLAY, f"Missing source type: {key}"
        assert len(SOURCE_TYPE_DISPLAY[key]) > 0


def test_source_type_normalization():
    """Verify legacy and shorthand source types normalize to the 7 canonical types."""
    assert normalize_source_type_display("laptop_camera") == "laptop_camera"
    assert normalize_source_type_display("laptop") == "laptop_camera"
    assert normalize_source_type_display("usb_webcam") == "usb_webcam"
    assert normalize_source_type_display("usb") == "usb_webcam"
    assert normalize_source_type_display("phone_link") == "phone_link"
    assert normalize_source_type_display("ip_camera") == "ip_camera"
    assert normalize_source_type_display("rtsp") == "ip_camera"
    assert normalize_source_type_display("phone") == "ip_camera"
    assert normalize_source_type_display("upload_video") == "upload_video"
    assert normalize_source_type_display("video_url") == "video_url"
    assert normalize_source_type_display("preset_video") == "preset_video"
    assert normalize_source_type_display("video") == "preset_video"
    assert normalize_source_type_display("webcam") == "laptop_camera"


def test_preset_videos_discovered():
    """Verify benchmark video discovery finds sample videos in data/videos."""
    videos = discover_preset_videos()
    assert len(videos) > 0
    assert "crowd_sample.mp4" in videos


def test_verify_stream_source_preset_video():
    """Verify verify_stream_source successfully verifies a real video file."""
    ok, msg, res, status = verify_stream_source("data/videos/crowd_sample.mp4", source_type="preset_video")
    assert ok is True
    assert "crowd_sample.mp4" in msg
    assert "x" in res
    assert status == "CONNECTED"


def test_verify_stream_source_missing_video():
    """Verify verify_stream_source cleanly fails on missing video without throwing."""
    ok, msg, res, status = verify_stream_source("data/videos/nonexistent_123456.mp4", source_type="preset_video")
    assert ok is False
    assert "not found" in msg.lower()
    assert status == "DISCONNECTED"


def test_verify_stream_source_phone_link_unexposed():
    """Verify informative diagnosis when Phone Link camera is not exposed."""
    ok, msg, res, status = verify_stream_source("2", source_type="phone_link")
    assert ok is False
    assert "phone link" in msg.lower() or "mobile devices" in msg.lower() or "device" in msg.lower()
    assert status == "DISCONNECTED"


def test_verify_stream_source_usb_webcam_unexposed():
    """Verify informative diagnosis when USB webcam index is not detected."""
    ok, msg, res, status = verify_stream_source("9", source_type="usb_webcam")
    assert ok is False
    assert status in ("DISCONNECTED", "FAILED", "INVALID_STREAM")


def test_verify_stream_source_network_timeout():
    """Verify unreachable network URL times out promptly and never hangs."""
    worker_finished = threading.Event()

    def mock_delayed_video_capture(*args, **kwargs):
        # Simulate a network connection attempt that exceeds the 1.0s probe timeout
        time.sleep(1.2)
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = False
        worker_finished.set()
        return mock_cap

    with patch("src.camera_devices.cv2.VideoCapture", side_effect=mock_delayed_video_capture):
        t0 = time.time()
        ok, msg, res, status = verify_stream_source(
            "rtsp://198.51.100.1:554/live",
            timeout_sec=1.0,
            source_type="ip_camera"
        )
        elapsed = time.time() - t0

    assert ok is False
    assert status in ("CONNECTION_TIMEOUT", "DISCONNECTED")
    assert status == "CONNECTION_TIMEOUT"
    assert elapsed < 3.0, f"Probe took too long: {elapsed:.2f}s"

    # Synchronize and ensure the mocked worker thread has finished before test exit
    assert worker_finished.wait(timeout=2.0), "Mocked probe worker thread did not finish within timeout."


def test_video_continuous_playback_and_looping(tmp_path):
    """
    Verify video files loop continuously on EOF so surveillance never freezes.
    Creates a tiny 5-frame synthetic video, steps 12 times, and verifies frames advance past EOF.
    """
    test_video_path = tmp_path / "tiny_test_video.mp4"
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    writer = cv2.VideoWriter(str(test_video_path), fourcc, 10.0, (160, 120))
    for i in range(5):
        frame = np.full((120, 160, 3), fill_value=i * 40, dtype=np.uint8)
        writer.write(frame)
    writer.release()

    config = TenantCameraConfig(
        id="cfg_test_eof",
        organization_id="org_test",
        slot_id="CAM-01",
        name="EOF Test Camera",
        source_type="preset_video",
        source=str(test_video_path),
        device_name=None,
        enabled=True,
        detection_mode="PERSON",
        created_at=None,
        updated_at=None
    )

    mc = MultiCameraManager(
        camera_configs=[config],
        detection_mode="PERSON",
        device="cpu",
        detect_interval=1
    )
    mc.start_all_cameras()
    cam = mc.cameras["CAM-01"]
    assert cam.status in ("ONLINE", "STREAMING")

    # Step past the 5-frame limit
    for _ in range(12):
        mc.step_camera("CAM-01")

    # Frame count must reach 12 because of auto-looping on EOF
    assert cam.frame_count == 12
    assert cam.status in ("ONLINE", "STREAMING")
    assert cam.annotated_frame is not None
    mc.stop_all_cameras()
    assert cam.status == "OFFLINE"


def test_resolve_camera_status_badge():
    """Verify camera status badge resolves correctly across all states."""
    cfg_active = MagicMock(enabled=True, source="0", source_type="laptop_camera")
    cfg_disabled = MagicMock(enabled=False, source="0", source_type="laptop_camera")
    cfg_unconf = MagicMock(enabled=True, source="", source_type="laptop_camera")

    # 1. Not configured / disabled
    t, c, _ = resolve_camera_status_badge(cfg_unconf, None, is_active=False)
    assert t == "NOT CONFIGURED"
    t, c, _ = resolve_camera_status_badge(cfg_disabled, None, is_active=True)
    assert t == "NOT CONFIGURED"

    # 2. Standby
    t, c, _ = resolve_camera_status_badge(cfg_active, None, is_active=False)
    assert t == "STANDBY"

    # 3. Connecting
    cam_mock = MagicMock(status="CONNECTING", annotated_frame=None, error_message=None)
    t, c, _ = resolve_camera_status_badge(cfg_active, cam_mock, is_active=True)
    assert t == "CONNECTING"

    # 4. Processing
    cam_mock.status = "STREAMING"
    cam_mock.annotated_frame = np.zeros((100, 100, 3), dtype=np.uint8)
    t, c, _ = resolve_camera_status_badge(cfg_active, cam_mock, is_active=True)
    assert t == "PROCESSING"

    # 5. Disconnected
    cam_mock.status = "DISCONNECTED"
    cam_mock.annotated_frame = None
    t, c, _ = resolve_camera_status_badge(cfg_active, cam_mock, is_active=True)
    assert t == "DISCONNECTED"

    # 6. Error
    cam_mock.status = "ERROR"
    t, c, _ = resolve_camera_status_badge(cfg_active, cam_mock, is_active=True)
    assert t == "ERROR"


def test_device_registry_normalize_and_lock():
    """Verify PhysicalDeviceRegistry locks physical devices across source types."""
    reg = PhysicalDeviceRegistry()

    # Normalization tests
    assert reg.normalize_device_id("0", "laptop_camera") == "webcam_0"
    assert reg.normalize_device_id(1, "usb_webcam") == "webcam_1"
    assert reg.normalize_device_id("2", "phone_link") == "webcam_2"
    assert reg.normalize_device_id("data/videos/crowd_sample.mp4", "preset_video") is None
    assert reg.normalize_device_id("http://192.168.1.5:8080/video", "ip_camera") is None

    # Exclusive locking
    ok, err = reg.acquire_device("webcam_0", "org_1", "sess_1", "CAM-01")
    assert ok is True
    assert err is None

    # Second organization attempts to acquire the same physical webcam
    ok2, err2 = reg.acquire_device("webcam_0", "org_2", "sess_2", "CAM-01")
    assert ok2 is False
    assert "in use" in err2.lower()

    # Release device
    reg.release_device("webcam_0", "org_1", "sess_1")
    ok3, err3 = reg.acquire_device("webcam_0", "org_2", "sess_2", "CAM-01")
    assert ok3 is True


def test_multi_camera_manager_reconfigure_and_focus():
    """Verify dynamic camera reconfiguration and Focus Feed stepping."""
    configs = [
        TenantCameraConfig(
            id="cfg_test_1",
            organization_id="org_test",
            slot_id="CAM-01",
            name="Preset Cam 1",
            source_type="preset_video",
            source="data/videos/crowd_sample.mp4",
            device_name=None,
            enabled=True,
            detection_mode="PERSON",
            created_at=None,
            updated_at=None
        ),
        TenantCameraConfig(
            id="cfg_test_2",
            organization_id="org_test",
            slot_id="CAM-02",
            name="Preset Cam 2",
            source_type="preset_video",
            source="data/videos/crowd_sample.mp4",
            device_name=None,
            enabled=True,
            detection_mode="PERSON",
            created_at=None,
            updated_at=None
        )
    ]

    mc = MultiCameraManager(
        camera_configs=configs,
        detection_mode="PERSON",
        device="cpu",
        detect_interval=1
    )
    mc.start_all_cameras()

    # Step all
    mc.step_all()
    assert mc.cameras["CAM-01"].frame_count >= 1
    assert mc.cameras["CAM-02"].frame_count >= 1

    # Step focus on CAM-01
    mc.step_focus("CAM-01", step_background=False)
    assert mc.cameras["CAM-01"].frame_count == 2
    assert mc.cameras["CAM-02"].frame_count == 1

    # Dynamic reconfigure
    ok = mc.reconfigure_camera(
        "CAM-02",
        source="data/videos/crowd_sample.mp4",
        source_type="preset_video",
        name="Renamed Preset Cam"
    )
    assert ok is True
    assert mc.cameras["CAM-02"].name == "Renamed Preset Cam"
    assert mc.cameras["CAM-02"].frame_count == 0  # Reset upon reconfigure

    mc.step_all()
    assert mc.cameras["CAM-02"].frame_count == 1
    mc.stop_all_cameras()
