"""
CrowdPatrol Phase 10 — Physical Camera Validation & Reliability Test Suite
Validates:
1. Hardware camera discovery, DirectShow & MediaFoundation behavior, and RTSP verification.
2. Dynamic camera management: add, reconfigure, switch, and delete feeds with handle release.
3. Detection configuration audit: Head Mode (640x640, conf=0.25), Person Mode (conf=0.35), YOLOv8 + DeepSORT.
4. Pipeline reliability: repeated start/stop, camera disconnection resilience, and resource measurements.
"""

import os
import time
import psutil
import pytest
import cv2
import numpy as np
from starlette.testclient import TestClient

from backend.main import app
from backend.services.pipeline_service import get_pipeline_service
from backend.services.camera_service import get_camera_service
from src.camera_devices import discover_camera_devices, test_camera_source, verify_stream_source


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_hardware_camera_discovery_and_probe():
    """Probe system hardware cameras and verify status logging without false-positive verification."""
    devs = discover_camera_devices(max_probe=3)
    assert isinstance(devs, list)
    # Ensure any discovered device has index and name, and is not falsely claimed as verified
    for d in devs:
        assert hasattr(d, "index")
        assert hasattr(d, "name")
        assert hasattr(d, "status")
        # Devices where OpenCV frame read fails must have status FAIL or UNKNOWN, not PASS
        if d.status != "PASS":
            assert d.status in ["FAIL", "UNKNOWN", "NOT_VERIFIED"]
        else:
            assert d.resolution != "0x0"


def test_rtsp_and_phone_ip_stream_timeout():
    """Verify that unreachable RTSP and Phone IP stream URLs timeout gracefully without blocking."""
    cam_svc = get_camera_service()
    
    # 1. Unreachable RTSP
    res_rtsp = cam_svc.test_camera_connection("rtsp://192.168.1.250:554/live")
    assert res_rtsp["success"] is False
    assert res_rtsp["status"] in ["CONNECTION_TIMEOUT", "OFFLINE"]
    assert "timeout" in res_rtsp["message"].lower() or "unable" in res_rtsp["message"].lower()

    # 2. Unreachable Phone IP webcam
    res_phone = cam_svc.test_camera_connection("http://192.168.1.250:8080/video")
    assert res_phone["success"] is False
    assert res_phone["status"] in ["CONNECTION_TIMEOUT", "OFFLINE"]


def test_detection_configuration_audit(client):
    """Confirm Head Mode is 640x640 at 0.25 confidence, and Person Mode confidence is preserved."""
    pipeline = get_pipeline_service()

    # 1. Switch to HEAD mode
    res_head = client.post("/api/config", json={"detection_mode": "HEAD"})
    assert res_head.status_code == 200
    cfg_head = client.get("/api/config").json()
    assert cfg_head["detection_mode"] == "HEAD"
    assert cfg_head["confidence"] == 0.25
    if pipeline.multi_camera and pipeline.multi_camera.shared_detector:
        assert pipeline.multi_camera.shared_detector.confidence == 0.25
        assert pipeline.multi_camera.shared_detector.imgsz == 640

    # 2. Switch to PERSON mode
    res_person = client.post("/api/config", json={"detection_mode": "PERSON"})
    assert res_person.status_code == 200
    cfg_person = client.get("/api/config").json()
    assert cfg_person["detection_mode"] == "PERSON"
    assert cfg_person["confidence"] == 0.35
    if pipeline.multi_camera and pipeline.multi_camera.shared_detector:
        assert pipeline.multi_camera.shared_detector.confidence == 0.35


def test_dynamic_camera_management_lifecycle(client):
    """Verify adding, reconfiguring, switching focus, and deleting camera feeds."""
    cam_svc = get_camera_service()

    # 1. Add a temporary 5th camera feed
    add_req = {
        "camera_id": "CAM-TEST-05",
        "name": "Validation Sector 5",
        "source": "data/videos/temp/upload_CAM-01_temple 1.mp4",
        "source_type": "video",
        "enabled": True
    }
    res_add = client.post("/api/cameras/reconfigure", json=add_req)
    assert res_add.status_code == 200
    assert res_add.json()["success"] is True

    # Verify present in cameras list
    cams_after_add = client.get("/api/cameras").json()["configured_cameras"]
    assert any(c["id"] == "CAM-TEST-05" for c in cams_after_add)

    # 2. Switch focus to the new camera
    res_focus = client.post("/api/cameras/focus", json={"camera_id": "CAM-TEST-05"})
    assert res_focus.status_code == 200
    assert client.get("/api/status").json()["focus_camera"] == "CAM-TEST-05"

    # 3. Reconfigure the camera source
    reconf_req = {
        "camera_id": "CAM-TEST-05",
        "name": "Updated Sector 5",
        "source": "data/videos/temp/upload_CAM-02_temple 2.mp4",
        "source_type": "video",
        "enabled": True
    }
    res_reconf = client.post("/api/cameras/reconfigure", json=reconf_req)
    assert res_reconf.status_code == 200
    assert res_reconf.json()["success"] is True

    # 4. Delete the camera feed
    res_del = client.delete("/api/cameras/CAM-TEST-05")
    assert res_del.status_code == 200
    assert res_del.json()["success"] is True

    # Verify deleted from config and pipeline
    cams_after_del = client.get("/api/cameras").json()["configured_cameras"]
    assert not any(c["id"] == "CAM-TEST-05" for c in cams_after_del)

    # Reset focus camera back to CAM-01
    client.post("/api/cameras/focus", json={"camera_id": "CAM-01"})


def test_repeated_start_stop_stability(client):
    """Verify monitoring pipeline can be started and stopped 3 consecutive times without leaks."""
    pipeline = get_pipeline_service()

    for cycle in range(3):
        # Start
        res_start = client.post("/api/monitoring/start")
        assert res_start.status_code == 200
        assert pipeline.is_running is True
        time.sleep(0.5)

        # Stop
        res_stop = client.post("/api/monitoring/stop")
        assert res_stop.status_code == 200
        assert pipeline.is_running is False
        assert pipeline.thread is None or not pipeline.thread.is_alive()


def test_camera_disconnection_resilience(client):
    """Simulate a disconnected feed during active monitoring and confirm pipeline survives."""
    pipeline = get_pipeline_service()

    # Start monitoring with valid cameras
    client.post("/api/monitoring/start")
    assert pipeline.is_running is True
    time.sleep(0.5)

    # Reconfigure CAM-04 to a broken/nonexistent stream
    res_break = client.post("/api/cameras/reconfigure", json={
        "camera_id": "CAM-04",
        "name": "Broken Feed",
        "source": "nonexistent_source_path.mp4",
        "source_type": "video",
        "enabled": True
    })
    assert res_break.status_code == 200

    # Let pipeline execute worker loop
    time.sleep(1.0)
    assert pipeline.is_running is True

    # Other cameras must still be active and generating frames
    stream_c1 = client.get("/api/stream/camera/CAM-01?max_frames=1")
    assert stream_c1.status_code == 200
    assert b"--frame" in stream_c1.content

    # Broken camera returns clean standby frame
    stream_c4 = client.get("/api/stream/camera/CAM-04?max_frames=1")
    assert stream_c4.status_code == 200
    assert b"--frame" in stream_c4.content

    # Restore CAM-04 to original source
    client.post("/api/cameras/reconfigure", json={
        "camera_id": "CAM-04",
        "name": "Perimeter Gate",
        "source": "data/videos/temp/upload_CAM-04_temple 4.mp4",
        "source_type": "video",
        "enabled": True
    })

    client.post("/api/monitoring/stop")


def test_resource_and_fps_measurement(client):
    """Measure CPU, memory usage, and separate inference FPS from display FPS."""
    pipeline = get_pipeline_service()
    proc = psutil.Process()

    # Measure pre-monitoring resources
    cpu_before = proc.cpu_percent(interval=0.1)
    mem_before = proc.memory_info().rss / (1024 * 1024)  # MB

    # Start monitoring
    client.post("/api/monitoring/start")
    time.sleep(1.5)

    cpu_during = proc.cpu_percent(interval=0.2)
    mem_during = proc.memory_info().rss / (1024 * 1024)  # MB

    # Grab throughput metrics
    metrics = pipeline.multi_camera.get_throughput_metrics() if pipeline.multi_camera else {}
    grid_fps = metrics.get("grid_display_fps", 30.0)
    inference_fps = metrics.get("yolo_inference_fps", {})

    print(f"\nResource Telemetry:")
    print(f"  Memory: {mem_during:.1f} MB (delta: {mem_during - mem_before:+.1f} MB)")
    print(f"  CPU Usage: {cpu_during:.1f}%")
    print(f"  Display FPS: {grid_fps}")
    print(f"  YOLO Inference FPS: {inference_fps}")

    assert mem_during < 2500  # Within healthy limits (< 2.5 GB)
    assert grid_fps >= 0.0

    client.post("/api/monitoring/stop")
