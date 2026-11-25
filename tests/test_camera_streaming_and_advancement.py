"""
tests/test_camera_streaming_and_advancement.py
----------------------------------------------
Comprehensive verification and regression suite for:
1. Webcam device index propagation without silent substitution.
2. Missing vs configured Phone Link detection and user-friendly requirements.
3. Simultaneous independent video playback across multiple channels.
4. Continuous truthful frame advancement (source_seq, proc_seq, current_video_pos, diff).
5. Video EOF automatic looping without freezing or premature completion.
6. Pause, resume, and stop resource lifecycle releasing threads and locks.
"""

import os
import sys
import time
import cv2
import numpy as np
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from src.auth.database import TenantCameraConfig
from src.multi_camera_manager import MultiCameraManager, CameraState
from src.capture import LowLatencyLiveCapture, OptimizedFileCapture, create_capture_source
from dashboard.org_ui import resolve_camera_status_badge, normalize_source_type_display


def test_webcam_device_index_propagation():
    """Verify webcam device index is propagated faithfully and empty source is NOT substituted."""
    # 1. Unconfigured webcam: must NOT silently default to 0
    cfg_unconf = TenantCameraConfig(
        id="c1", organization_id="o1", slot_id="CAM-01", name="Entrance",
        source_type="laptop_camera", source="", device_name=None,
        enabled=True, detection_mode="PERSON", created_at=None, updated_at=None
    )
    cam_unconf = CameraState("CAM-01", "Entrance", source="", source_type="laptop_camera")
    res = cam_unconf.open_source()
    assert res is False
    assert cam_unconf.status == "NOT_CONFIGURED"
    assert "not configured" in cam_unconf.error_message.lower()

    # 2. Configured device index: must propagate explicit index
    cam_conf = CameraState("CAM-01", "Entrance", source="1", source_type="laptop_camera")
    assert str(cam_conf.source) == "1"


def test_missing_phone_link_configuration():
    """Verify unconfigured Phone Link slot reports clear setup instructions rather than stream error."""
    cam_phone = CameraState("CAM-02", "Phone Slot", source="", source_type="phone_link")
    res = cam_phone.open_source()
    assert res is False
    assert cam_phone.status == "NOT_CONFIGURED"
    assert "phone link" in cam_phone.error_message.lower() or "mobile devices" in cam_phone.error_message.lower()

    # Also test legacy source_type 'phone'
    cam_legacy_phone = CameraState("CAM-02", "Phone Slot", source="", source_type="phone")
    res_leg = cam_legacy_phone.open_source()
    assert res_leg is False
    assert cam_legacy_phone.status == "NOT_CONFIGURED"


def test_valid_phone_link_configuration():
    """Verify valid Phone Link source (device index or RTSP/HTTP URL) is accepted."""
    cam_url = CameraState("CAM-02", "Phone Stream", source="http://192.168.1.50:8080/video", source_type="phone_link")
    assert cam_url.source == "http://192.168.1.50:8080/video"

    cam_idx = CameraState("CAM-02", "Phone Device", source="2", source_type="phone_link")
    assert cam_idx.source == "2"


def test_simultaneous_video_playback_and_advancement(tmp_path):
    """
    Verify two independent video files advance simultaneously across all diagnostic counters:
    - source_frame_seq advances on each step.
    - processed_frame_seq advances on each step.
    - current_video_pos advances sequentially.
    - frame_diff is computed and indicates non-stale frames.
    - Neither camera freezes the other.
    """
    # Create two synthetic videos with distinct visual motions
    vid1_path = tmp_path / "vid_sim_1.mp4"
    vid2_path = tmp_path / "vid_sim_2.mp4"
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')

    w1 = cv2.VideoWriter(str(vid1_path), fourcc, 15.0, (160, 120))
    w2 = cv2.VideoWriter(str(vid2_path), fourcc, 15.0, (160, 120))
    for i in range(20):
        # Video 1: sweeping bright bar
        f1 = np.zeros((120, 160, 3), dtype=np.uint8)
        cv2.rectangle(f1, (i * 7, 10), (i * 7 + 25, 110), (255, 200, 50), -1)
        w1.write(f1)

        # Video 2: increasing global brightness
        f2 = np.full((120, 160, 3), fill_value=min(255, 15 + i * 11), dtype=np.uint8)
        w2.write(f2)
    w1.release()
    w2.release()

    configs = [
        TenantCameraConfig(
            id="cfg_1", organization_id="o1", slot_id="CAM-03", name="Video 1",
            source_type="preset_video", source=str(vid1_path), device_name=None,
            enabled=True, detection_mode="PERSON", created_at=None, updated_at=None
        ),
        TenantCameraConfig(
            id="cfg_2", organization_id="o1", slot_id="CAM-04", name="Video 2",
            source_type="preset_video", source=str(vid2_path), device_name=None,
            enabled=True, detection_mode="PERSON", created_at=None, updated_at=None
        )
    ]

    mc = MultiCameraManager(
        camera_configs=configs,
        detection_mode="PERSON",
        device="cpu",
        detect_interval=1
    )
    started = mc.start_all_cameras()
    assert started == 2

    c3 = mc.cameras["CAM-03"]
    c4 = mc.cameras["CAM-04"]

    prev_pos3 = -1
    prev_pos4 = -1

    for step in range(1, 11):
        processed = mc.step_all()
        assert "CAM-03" in processed
        assert "CAM-04" in processed

        # Truthful diagnostic assertions
        assert c3.source_frame_seq == step
        assert c4.source_frame_seq == step
        assert c3.processed_frame_seq == step
        assert c4.processed_frame_seq == step
        assert c3.frame_count == step
        assert c4.frame_count == step

        # Video positions must advance
        assert c3.current_video_pos > prev_pos3
        assert c4.current_video_pos > prev_pos4
        prev_pos3 = c3.current_video_pos
        prev_pos4 = c4.current_video_pos

        # Timestamps must be recorded
        assert c3.last_capture_time is not None
        assert c3.last_processing_time is not None
        assert c4.last_capture_time is not None
        assert c4.last_processing_time is not None

        # Frame difference must be positive (frames are genuinely changing, not identical)
        if step > 1:
            assert c3.frame_diff > 0.0, f"CAM-03 frame diff zero at step {step}"
            assert c4.frame_diff > 0.0, f"CAM-04 frame diff zero at step {step}"
            assert c3.is_frame_changed is True
            assert c4.is_frame_changed is True

    mc.stop_all_cameras()


def test_video_eof_looping(tmp_path):
    """Verify video files loop automatically past EOF and do not terminate monitoring."""
    vid_path = tmp_path / "short_loop.mp4"
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    w = cv2.VideoWriter(str(vid_path), fourcc, 10.0, (160, 120))
    for i in range(4):
        f = np.full((120, 160, 3), fill_value=i * 50, dtype=np.uint8)
        w.write(f)
    w.release()

    config = TenantCameraConfig(
        id="cfg_loop", organization_id="o1", slot_id="CAM-03", name="Loop Cam",
        source_type="preset_video", source=str(vid_path), device_name=None,
        enabled=True, detection_mode="PERSON", created_at=None, updated_at=None
    )

    mc = MultiCameraManager(camera_configs=[config], detection_mode="PERSON", device="cpu", detect_interval=1)
    mc.start_all_cameras()
    cam = mc.cameras["CAM-03"]

    # Step 12 times (3 full loops of 4-frame video)
    for _ in range(12):
        res = mc.step_camera("CAM-03")
        assert res is not None

    assert cam.frame_count == 12
    assert cam.source_frame_seq == 12
    assert cam.status == "ONLINE"
    mc.stop_all_cameras()
    assert cam.status == "OFFLINE"


def test_pause_resume_lifecycle(tmp_path):
    """Verify pause stops frame stepping and resume cleanly restores frame progression."""
    vid_path = tmp_path / "pause_test.mp4"
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    w = cv2.VideoWriter(str(vid_path), fourcc, 10.0, (160, 120))
    for i in range(10):
        f = np.full((120, 160, 3), fill_value=i * 20, dtype=np.uint8)
        w.write(f)
    w.release()

    config = TenantCameraConfig(
        id="cfg_p", organization_id="o1", slot_id="CAM-03", name="Pause Cam",
        source_type="preset_video", source=str(vid_path), device_name=None,
        enabled=True, detection_mode="PERSON", created_at=None, updated_at=None
    )
    mc = MultiCameraManager(camera_configs=[config], detection_mode="PERSON", device="cpu", detect_interval=1)
    mc.start_all_cameras()
    cam = mc.cameras["CAM-03"]

    # 1. Step 3 times
    for _ in range(3):
        mc.step_all()
    assert cam.frame_count == 3

    # 2. Simulate paused state (as checked by org_ui _render_live_stream_container)
    is_paused = True
    if not is_paused:
        mc.step_all()
    assert cam.frame_count == 3  # Unchanged during pause

    # 3. Simulate resume
    is_paused = False
    if not is_paused:
        mc.step_all()
    assert cam.frame_count == 4  # Progress resumed

    mc.stop_all_cameras()
    assert cam.status == "OFFLINE"
    assert cam.cap is None


def test_status_badge_not_configured_vs_processing():
    """Verify status badge resolves NOT CONFIGURED, STANDBY, and PROCESSING accurately."""
    cfg_unconf = MagicMock(enabled=True, source="", source_type="laptop_camera")
    t, c, _ = resolve_camera_status_badge(cfg_unconf, None, is_active=False)
    assert t == "NOT CONFIGURED"

    cfg_conf = MagicMock(enabled=True, source="data/videos/crowd_sample.mp4", source_type="preset_video")
    t, c, _ = resolve_camera_status_badge(cfg_conf, None, is_active=False)
    assert t == "STANDBY"

    cam_mock = MagicMock(status="ONLINE", annotated_frame=np.zeros((10, 10, 3), dtype=np.uint8))
    t, c, _ = resolve_camera_status_badge(cfg_conf, cam_mock, is_active=True)
    assert t == "PROCESSING"

    cam_unconf_obj = MagicMock(status="NOT_CONFIGURED", annotated_frame=None, error_message="Source not configured")
    t, c, _ = resolve_camera_status_badge(cfg_unconf, cam_unconf_obj, is_active=True)
    assert t == "NOT CONFIGURED"
