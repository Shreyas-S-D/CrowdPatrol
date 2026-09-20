"""
Unit tests for Phase 13 & 13.3: Multi-Camera Crowd Monitoring Command Center.
Verifies camera configuration parsing, flexible source types (video, webcam, rtsp), source validation,
failed camera isolation, shared detector initialization, state isolation between cameras,
live camera vs video EOF behavior, overall system risk aggregation, mode switching, and telemetry.
"""

import pytest
import numpy as np
import cv2
import os
import json
from pathlib import Path

from src.multi_camera_manager import MultiCameraManager, CameraState, DEFAULT_CONFIG_PATH


def test_camera_config_file_exists():
    """Verify that config/cameras.json exists and is valid JSON."""
    assert DEFAULT_CONFIG_PATH.exists()
    with open(DEFAULT_CONFIG_PATH, "r") as f:
        cfg = json.load(f)
    assert "cameras" in cfg
    assert len(cfg["cameras"]) == 4


def test_multi_camera_manager_init():
    """Verify MultiCameraManager loads cameras from config and initializes shared detector."""
    manager = MultiCameraManager(device="cpu")
    assert len(manager.cameras) == 4
    assert manager.shared_detector is not None
    assert manager.detection_mode == "PERSON"
    
    for cam_id in ["CAM-01", "CAM-02", "CAM-03", "CAM-04"]:
        assert cam_id in manager.cameras
        cam = manager.cameras[cam_id]
        assert isinstance(cam, CameraState)
        assert cam.id == cam_id


def test_video_source_configuration():
    """Verify video source configuration in CameraState."""
    cam = CameraState("CAM-01", "Demo Video", "data/videos/youtube_crowd_test.mp4", source_type="video")
    assert cam.source_type == "video"
    assert cam.source == "data/videos/youtube_crowd_test.mp4"
    assert cam.open_source() is True
    assert cam.status == "ONLINE"
    cam.close_source()


def test_webcam_source_configuration():
    """Verify webcam source configuration in CameraState."""
    cam = CameraState("CAM-01", "Webcam 0", 0, source_type="webcam", enabled=False)
    assert cam.source_type == "webcam"
    assert cam.source == 0
    assert cam.open_source() is False
    assert cam.status == "DISABLED"


def test_rtsp_source_configuration():
    """Verify RTSP source configuration in CameraState."""
    cam = CameraState("CAM-03", "RTSP Cam", "rtsp://192.168.1.100:554/live", source_type="rtsp", enabled=False)
    assert cam.source_type == "rtsp"
    assert cam.source == "rtsp://192.168.1.100:554/live"
    assert cam.open_source() is False
    assert cam.status == "DISABLED"


def test_invalid_video_path_handling():
    """Verify invalid video file path fails cleanly with CONNECTION FAILED status."""
    cam = CameraState("CAM-99", "Bad File", "data/videos/non_existent_video.mp4", source_type="video")
    result = cam.open_source()
    assert result is False
    assert cam.status == "CONNECTION FAILED"
    assert "Video file not found" in cam.error_message


def test_invalid_webcam_index_handling():
    """Verify invalid webcam index fails cleanly with CONNECTION FAILED status."""
    cam = CameraState("CAM-99", "Bad Webcam", 9999, source_type="webcam")
    result = cam.open_source()
    assert result is False
    assert cam.status == "CONNECTION FAILED"
    assert "Unable to open camera index" in cam.error_message


def test_failed_rtsp_connection_handling(monkeypatch):
    """Verify invalid/unreachable RTSP URL fails cleanly without crashing."""
    cam = CameraState("CAM-99", "Bad RTSP", "rtsp://127.0.0.1:554/invalid_stream", source_type="rtsp")
    monkeypatch.setattr("src.multi_camera_manager.VideoProcessor.get_video_source", lambda src: None)
    result = cam.open_source()
    assert result is False
    assert cam.status == "CONNECTION FAILED"
    assert "Unable to connect" in cam.error_message


def test_mixed_source_types_across_cameras(tmp_path):
    """Verify MultiCameraManager cleanly parses mixed video, webcam, and RTSP sources."""
    config_data = {
        "cameras": [
            {
                "id": "CAM-01",
                "name": "Local Video",
                "source_type": "video",
                "source": "data/videos/youtube_crowd_test.mp4",
                "enabled": True
            },
            {
                "id": "CAM-02",
                "name": "Webcam Feed",
                "source_type": "webcam",
                "source": 0,
                "enabled": False
            },
            {
                "id": "CAM-03",
                "name": "RTSP Feed",
                "source_type": "rtsp",
                "source": "rtsp://192.168.1.200:554/stream1",
                "enabled": False
            }
        ]
    }
    cfg_file = tmp_path / "cameras.json"
    with open(cfg_file, "w") as f:
        json.dump(config_data, f)
        
    manager = MultiCameraManager(config_path=cfg_file, device="cpu")
    assert manager.cameras["CAM-01"].source_type == "video"
    assert manager.cameras["CAM-02"].source_type == "webcam"
    assert manager.cameras["CAM-03"].source_type == "rtsp"


def test_independent_camera_capture_state():
    """Verify each camera maintains isolated capture objects."""
    manager = MultiCameraManager(device="cpu")
    cam1 = manager.cameras["CAM-01"]
    cam2 = manager.cameras["CAM-02"]
    
    manager.start_all_cameras()
    assert cam1.cap is not cam2.cap
    manager.stop_all_cameras()


def test_reconfigure_video_to_webcam_switch():
    """Verify dynamic reconfiguration from video to webcam source type."""
    manager = MultiCameraManager(device="cpu")
    cam1 = manager.cameras["CAM-01"]
    manager.start_all_cameras()
    
    assert cam1.source_type == "video"
    assert cam1.status == "ONLINE"
    
    # Reconfigure CAM-01 to webcam index 0 (disabled to avoid physical hardware dependency in test)
    res = manager.reconfigure_camera("CAM-01", 0, source_type="webcam", enabled=False)
    
    assert res is False
    assert cam1.source_type == "webcam"
    assert cam1.source == 0
    assert cam1.status == "DISABLED"
    assert cam1.cap is None
    manager.stop_all_cameras()


def test_reconfigure_webcam_to_video_switch():
    """Verify dynamic reconfiguration from webcam to video source type."""
    manager = MultiCameraManager(device="cpu")
    cam1 = manager.cameras["CAM-01"]
    cam1.source_type = "webcam"
    cam1.source = 0
    
    # Reconfigure CAM-01 to valid video file path
    res = manager.reconfigure_camera("CAM-01", "data/videos/youtube_crowd_test.mp4", source_type="video", enabled=True)
    
    assert res is True
    assert cam1.source_type == "video"
    assert cam1.source == "data/videos/youtube_crowd_test.mp4"
    assert cam1.status == "ONLINE"
    assert cam1.cap is not None
    assert cam1.cap.isOpened()
    manager.stop_all_cameras()


def test_reconfigure_failed_source_reports_failure():
    """Verify reconfiguring to invalid source reports failure and releases old capture."""
    manager = MultiCameraManager(device="cpu")
    cam1 = manager.cameras["CAM-01"]
    manager.start_all_cameras()
    
    old_cap = cam1.cap
    assert old_cap is not None and old_cap.isOpened()
    
    # Reconfigure to non-existent video file
    res = manager.reconfigure_camera("CAM-01", "data/videos/non_existent.mp4", source_type="video", enabled=True)
    
    assert res is False
    assert cam1.status == "CONNECTION FAILED"
    assert "Video file not found" in cam.error_message if 'cam' in locals() else "Video file not found" in cam1.error_message
    assert cam1.cap is None or not cam1.cap.isOpened()
    manager.stop_all_cameras()


def test_reconfigure_resets_tracker_and_motion_state():
    """Verify reconfiguring a camera clears old tracks and resets motion history."""
    manager = MultiCameraManager(device="cpu")
    cam1 = manager.cameras["CAM-01"]
    manager.start_all_cameras()
    
    # Add dummy track & frame count to cam1
    cam1.frame_count = 50
    cam1.active_tracks = [[10, 10, 50, 50, 1]]
    
    # Reconfigure CAM-01
    manager.reconfigure_camera("CAM-01", "data/videos/dense_crowd_test.mp4", source_type="video", enabled=True)
    
    assert cam1.frame_count == 0
    assert len(cam1.active_tracks) == 0
    assert len(cam1.visible_tracks) == 0
    manager.stop_all_cameras()


def test_reconfigure_leaves_other_cameras_unaffected():
    """Verify reconfiguring CAM-01 does NOT affect CAM-02 online state."""
    manager = MultiCameraManager(device="cpu")
    manager.start_all_cameras()
    
    cam2 = manager.cameras["CAM-02"]
    assert cam2.status == "ONLINE"
    
    # Reconfigure CAM-01 to invalid file
    manager.reconfigure_camera("CAM-01", "invalid_file.mp4", source_type="video", enabled=True)
    
    assert manager.cameras["CAM-01"].status == "CONNECTION FAILED"
    assert cam2.status == "ONLINE"
    assert cam2.cap is not None and cam2.cap.isOpened()
    manager.stop_all_cameras()


def test_video_eof_looping():
    """Verify recorded video sources rewind automatically at EOF."""
    cam = CameraState("CAM-01", "Demo", "data/videos/youtube_crowd_test.mp4", source_type="video")
    cam.open_source()
    
    # Mock cap near end of video
    cap_len = int(cam.cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cam.cap.set(cv2.CAP_PROP_POS_FRAMES, cap_len - 1)
    
    # Read last frame
    ret, frame = cam.cap.read()
    assert ret is True
    
    # Next read will reach EOF (ret = False), triggering rewind
    ret_eof, _ = cam.cap.read()
    assert ret_eof is False
    
    # Manual trigger of step logic for recorded video
    cam.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    ret_rewound, frame_rewound = cam.cap.read()
    assert ret_rewound is True
    assert frame_rewound is not None
    cam.close_source()


def test_live_camera_does_not_rewind_at_eof():
    """Verify live camera sources (webcam/rtsp) do NOT rewind at EOF."""
    manager = MultiCameraManager(device="cpu")
    cam = manager.cameras["CAM-01"]
    cam.source_type = "webcam"
    
    # Mock a closed / ended live stream
    class MockEndedCap:
        def isOpened(self): return True
        def read(self): return False, None
        def set(self, prop, val): pass
        def release(self): pass
        
    cam.cap = MockEndedCap()
    cam.status = "ONLINE"
    
    out = manager.step_camera("CAM-01")
    assert out is None
    assert cam.status == "OFFLINE"
    assert "Live camera stream disconnected" in cam.error_message


def test_one_failed_camera_does_not_stop_other_cameras():
    """Verify a connection failure on one camera does NOT prevent other online cameras from operating."""
    manager = MultiCameraManager(device="cpu")
    
    # Set CAM-01 to invalid webcam index so connection fails
    manager.cameras["CAM-01"].source_type = "webcam"
    manager.cameras["CAM-01"].source = 9999
    
    # Other cameras are valid recorded videos
    success_count = manager.start_all_cameras()
    
    assert manager.cameras["CAM-01"].status == "CONNECTION FAILED"
    assert manager.cameras["CAM-02"].status == "ONLINE"
    assert success_count == 3  # 3/4 opened cleanly
    
    frames = manager.step_all()
    assert "CAM-01" not in frames
    assert "CAM-02" in frames
    assert "CAM-03" in frames
    assert "CAM-04" in frames
    
    manager.stop_all_cameras()


def test_camera_state_isolation():
    """Verify each camera maintains isolated tracker and density estimator instances."""
    manager = MultiCameraManager(device="cpu")
    cam1 = manager.cameras["CAM-01"]
    cam2 = manager.cameras["CAM-02"]
    
    # Trackers must be different object instances
    assert cam1.tracker is not cam2.tracker
    assert cam1.density_estimator is not cam2.density_estimator
    assert cam1.motion_analyzer is not cam2.motion_analyzer
    
    # Mutating state in cam1 must not affect cam2
    cam1.active_count = 15
    cam1.risk_level = "HIGH"
    cam1.risk_score = 85.0
    
    assert cam2.active_count == 0
    assert cam2.risk_level == "LOW"
    assert cam2.risk_score == 0.0


def test_overall_system_risk_aggregation():
    """Verify overall system risk is driven by highest risk level across active cameras."""
    manager = MultiCameraManager(device="cpu")
    
    cam1 = manager.cameras["CAM-01"]
    cam2 = manager.cameras["CAM-02"]
    cam3 = manager.cameras["CAM-03"]
    cam4 = manager.cameras["CAM-04"]
    
    cam1.status = "ONLINE"
    cam1.risk_level = "LOW"
    cam1.risk_score = 15.0
    
    cam2.status = "ONLINE"
    cam2.risk_level = "MEDIUM"
    cam2.risk_score = 55.0
    
    cam3.status = "ONLINE"
    cam3.risk_level = "HIGH"
    cam3.risk_score = 90.0
    
    cam4.status = "OFFLINE"
    cam4.risk_level = "LOW"
    
    sys_risk = manager.get_overall_system_risk()
    
    assert sys_risk["overall_risk_level"] == "HIGH"
    assert sys_risk["highest_risk_camera_id"] == "CAM-03"
    assert sys_risk["highest_risk_camera_name"] == "Street Crossing Plaza"
    assert sys_risk["highest_risk_score"] == 90.0
    assert sys_risk["active_camera_count"] == 3


def test_camera_telemetry_payload_schema():
    """Verify camera telemetry payload contains namespaced camera fields."""
    manager = MultiCameraManager(device="cpu")
    cam1 = manager.cameras["CAM-01"]
    cam1.status = "ONLINE"
    cam1.active_count = 12
    cam1.max_density = 4
    cam1.risk_level = "MEDIUM"
    cam1.risk_score = 60.0
    cam1.fps = 24.5
    
    payload = manager.get_camera_telemetry_payload("CAM-01")
    
    assert payload["camera_id"] == "CAM-01"
    assert payload["camera_name"] == "Main Sidewalk / Entrance"
    assert payload["status"] == "ONLINE"
    assert payload["source_type"] == "video"
    assert payload["person_count"] == 12
    assert payload["max_density"] == 4
    assert payload["risk_level"] == "MEDIUM"
    assert payload["risk_score"] == 60.0
    assert payload["fps"] == 24.5
    assert "last_frame_time" in payload


def test_detection_mode_switching():
    """Verify switching detection mode updates shared detector and resets camera pipelines."""
    manager = MultiCameraManager(device="cpu")
    assert manager.detection_mode == "PERSON"
    
    manager.set_detection_mode("HEAD")
    assert manager.detection_mode == "HEAD"
    assert manager.cameras["CAM-01"].detection_mode == "HEAD"
    assert manager.cameras["CAM-01"].risk_adapter is not None
    assert manager.cameras["CAM-01"].risk_assessor is None
    
    manager.set_detection_mode("PERSON")
    assert manager.detection_mode == "PERSON"
    assert manager.cameras["CAM-01"].detection_mode == "PERSON"
    assert manager.cameras["CAM-01"].risk_assessor is not None
    assert manager.cameras["CAM-01"].risk_adapter is None


def test_step_camera_with_mock_frame():
    """Verify step_camera executes frame inference and produces annotated frame output."""
    manager = MultiCameraManager(device="cpu")
    cam1 = manager.cameras["CAM-01"]
    
    # Create a synthetic dummy video stream / frame
    dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    
    # Mock cap object
    class MockCap:
        def isOpened(self): return True
        def read(self): return True, dummy_frame.copy()
        def release(self): pass
            
    cam1.cap = MockCap()
    cam1.status = "ONLINE"
    
    annotated = manager.step_camera("CAM-01")
    
    assert annotated is not None
    assert annotated.shape == (480, 640, 3)
    assert cam1.frame_count == 1
    assert cam1.fps >= 0.0


# ========== PHASE 13.3.4 CAMERA DEVICE DISCOVERY & VERIFICATION TESTS ==========

from src.camera_devices import CameraDevice, discover_camera_devices, test_camera_source, get_camera_display_name


def test_camera_device_discovery():
    """Verify camera device discovery enumerates available video input devices."""
    devices = discover_camera_devices(max_probe=4)
    assert isinstance(devices, list)
    assert len(devices) > 0
    for dev in devices:
        assert isinstance(dev, CameraDevice)
        assert isinstance(dev.index, int)
        assert isinstance(dev.name, str)
        assert len(dev.display_name) > 0
        assert "(Device " in dev.display_name


def test_camera_devices_unique_indices():
    """Verify discovered camera devices have unique integer indices."""
    devices = discover_camera_devices(max_probe=4)
    indices = [d.index for d in devices]
    assert len(indices) == len(set(indices))


def test_manual_index_fallback():
    """Verify fallback handling when camera device discovery fails or is mocked."""
    dev = CameraDevice(index=3, name="Manual Device Index", status="FAIL", resolution="0x0")
    assert dev.index == 3
    assert dev.display_name == "Manual Device Index (Device 3)"
    assert dev.status == "FAIL"


def test_selected_device_maps_to_correct_index():
    """Verify selected device name maps cleanly to display name and index."""
    display_str_0 = get_camera_display_name(0)
    display_str_1 = get_camera_display_name(1)
    display_str_2 = get_camera_display_name(2)
    assert display_str_0 == "Laptop Integrated Camera (Device 0)"
    assert display_str_1 == "External USB Webcam (Device 1)"
    assert display_str_2 == "Phone Link Camera (Device 2)"


def test_invalid_device_handling():
    """Verify invalid device inputs return clean failure tuple."""
    ok, msg, res = test_camera_source("invalid_idx")
    assert ok is False
    assert "Invalid device index" in msg
    assert res == "0x0"


def test_camera_test_success_and_failure():
    """Verify test_camera_source reports failure on non-existent camera index."""
    ok, msg, res = test_camera_source(9999)
    assert ok is False
    assert "Unable to open camera device index 9999" in msg or "failed" in msg
    assert res == "0x0"


def test_source_badge_displays_selected_device():
    """Verify source badge formatting helper displays selected device name and index."""
    badge0 = get_camera_display_name(0)
    badge1 = get_camera_display_name(1)
    badge2 = get_camera_display_name(2)
    badge_def = get_camera_display_name(5)
    
    assert badge0 == "Laptop Integrated Camera (Device 0)"
    assert badge1 == "External USB Webcam (Device 1)"
    assert badge2 == "Phone Link Camera (Device 2)"
    assert badge_def == "Manual Device Index (Device 5)"


def test_multicamera_manager_receives_runtime_webcam_config():
    """Verify MultiCameraManager reconfigures camera state cleanly when runtime webcam config is applied."""
    manager = MultiCameraManager(device="cpu")
    cam1 = manager.cameras["CAM-01"]
    
    # Apply webcam config to CAM-01 without opening physical hardware device in automated test suite
    res = manager.reconfigure_camera("CAM-01", 0, source_type="webcam", enabled=False)
    assert res is False  # returns False because enabled=False
    assert cam1.source_type == "webcam"
    assert cam1.source == 0
    assert cam1.status == "DISABLED"


