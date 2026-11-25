"""
Phase 7 / Starlette Migration Unit & Integration Test Suite — Starlette Backend
Tests all REST endpoints, config updates, camera discovery, alert lifecycle,
notifications, and video streaming headers.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from starlette.testclient import TestClient

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.main import app
from backend.services.pipeline_service import get_pipeline_service
from backend.services.alert_service import get_alert_service
from backend.services.camera_service import get_camera_service


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_root_and_health_endpoints(client):
    """Verify platform identity and healthcheck endpoints."""
    res_root = client.get("/")
    assert res_root.status_code == 200
    data_root = res_root.json()
    assert data_root["platform"] == "CrowdPatrol"
    assert data_root["status"] == "ONLINE"

    res_health = client.get("/health")
    assert res_health.status_code == 200
    data_health = res_health.json()
    assert data_health["status"] == "healthy"
    assert "pipeline_running" in data_health
    assert "detection_mode" in data_health


def test_status_endpoint(client):
    """Verify system status reports operational state."""
    res = client.get("/api/status")
    assert res.status_code == 200
    data = res.json()
    assert "is_running" in data
    assert "detection_mode" in data
    assert "fps" in data
    assert "person_count" in data
    assert "risk_level" in data


def test_config_get_and_update(client):
    """Verify config retrieval and dynamic modification."""
    # 1. Get initial config
    res_get = client.get("/api/config")
    assert res_get.status_code == 200
    cfg = res_get.json()
    assert "detection_mode" in cfg
    assert "confidence" in cfg

    # 2. Update to HEAD mode with 0.25 confidence
    res_post = client.post("/api/config", json={
        "detection_mode": "HEAD",
        "tiled_mode": True,
        "confidence": 0.25,
        "detect_interval": 2
    })
    assert res_post.status_code == 200
    updated = res_post.json()
    assert updated["detection_mode"] == "HEAD"
    assert updated["tiled_mode"] is True
    assert updated["confidence"] == 0.25

    # 3. Switch back to PERSON mode
    res_restore = client.post("/api/config", json={
        "detection_mode": "PERSON",
        "tiled_mode": False,
        "confidence": 0.35,
        "detect_interval": 3
    })
    assert res_restore.status_code == 200
    assert res_restore.json()["detection_mode"] == "PERSON"


def test_cameras_discovery_and_config(client):
    """Verify camera lists configured cameras, hardware discovery, and sample videos."""
    res = client.get("/api/cameras")
    assert res.status_code == 200
    data = res.json()
    assert "configured_cameras" in data
    assert "discovered_devices" in data
    assert "sample_videos" in data
    assert isinstance(data["configured_cameras"], list)
    assert len(data["configured_cameras"]) >= 1
    assert any("CAM-01" == c["id"] for c in data["configured_cameras"])


def test_phone_url_generator(client):
    """Verify phone stream URL builder endpoint."""
    res = client.post("/api/cameras/phone-url", json={
        "ip": "192.168.1.150",
        "port": 8080,
        "app_type": "ipwebcam"
    })
    assert res.status_code == 200
    assert "http://192.168.1.150:8080/video" in res.json()["url"]


def test_analytics_summary(client):
    """Verify analytics summary provides current metrics and time-series history."""
    res = client.get("/api/analytics/summary")
    assert res.status_code == 200
    data = res.json()
    assert "current" in data
    assert "history" in data
    assert "timestamps" in data["history"]
    assert "risk_scores" in data["history"]
    assert "person_counts" in data["history"]


def test_alert_lifecycle_api(client):
    """Verify alerts endpoint, manual acknowledgement, and resolution."""
    # 1. Fetch alerts
    res_get = client.get("/api/alerts")
    assert res_get.status_code == 200
    alerts_data = res_get.json()
    assert "active_alerts" in alerts_data
    assert "history" in alerts_data

    # 2. Test acknowledge on test camera
    res_ack = client.post("/api/alerts/CAM-01/acknowledge", json={"operator_id": "UnitTester"})
    assert res_ack.status_code == 200
    assert "camera_id" in res_ack.json()

    # 3. Test resolve on test camera
    res_res = client.post("/api/alerts/CAM-01/resolve", json={
        "operator_id": "UnitTester",
        "note": "Unit test resolution"
    })
    assert res_res.status_code == 200
    assert "camera_id" in res_res.json()


def test_notifications_log_api(client):
    """Verify notification delivery history endpoint."""
    res = client.get("/api/notifications/log")
    assert res.status_code == 200
    assert isinstance(res.json(), list)


def test_monitoring_start_stop(client):
    """Verify pipeline worker start and stop endpoints."""
    # Ensure stopped first
    client.post("/api/monitoring/stop")

    # Start
    res_start = client.post("/api/monitoring/start")
    assert res_start.status_code == 200
    assert res_start.json()["status"] in ["started", "already_running"]

    # Verify status reports running
    res_status = client.get("/api/status")
    assert res_status.json()["is_running"] is True

    # Stop
    res_stop = client.post("/api/monitoring/stop")
    assert res_stop.status_code == 200
    assert res_stop.json()["status"] in ["stopped", "not_running"]

    # Verify status reports stopped
    res_status_after = client.get("/api/status")
    assert res_status_after.json()["is_running"] is False


def test_live_stream_headers(client):
    """Verify live stream endpoint sets multipart/x-mixed-replace content type and sends initial chunk."""
    res = client.get("/api/stream/live?max_frames=1")
    assert res.status_code == 200
    assert "multipart/x-mixed-replace" in res.headers.get("content-type", "")
    assert b"--frame" in res.content
    assert b"Content-Type: image/jpeg" in res.content


def test_camera_and_heatmap_stream_endpoints(client):
    """Verify single-camera and heatmap MJPEG streaming endpoints."""
    # Single camera stream (CAM-01)
    res_cam = client.get("/api/stream/camera/CAM-01?max_frames=1")
    assert res_cam.status_code == 200
    assert "multipart/x-mixed-replace" in res_cam.headers.get("content-type", "")
    assert b"--frame" in res_cam.content

    # Heatmap stream
    res_hm = client.get("/api/stream/heatmap?max_frames=1")
    assert res_hm.status_code == 200
    assert "multipart/x-mixed-replace" in res_hm.headers.get("content-type", "")
    assert b"--frame" in res_hm.content


def test_camera_layout_switch(client):
    """Verify layout switching between GRID and FOCUS."""
    res = client.post("/api/cameras/layout", json={"layout": "FOCUS", "focus_camera": "CAM-02"})
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["operating_mode"] == "FOCUS"
    assert data["focus_camera"] == "CAM-02"

    # Switch back to GRID
    res_grid = client.post("/api/cameras/layout", json={"layout": "GRID"})
    assert res_grid.status_code == 200
    assert res_grid.json()["operating_mode"] == "GRID"


def test_backend_does_not_start_camera_during_ordinary_health_api_calls(client):
    """Confirm the backend does not start camera processing during ordinary health/API tests."""
    # Ensure pipeline is stopped
    client.post("/api/monitoring/stop")

    # Make ordinary health & API queries
    client.get("/")
    client.get("/health")
    client.get("/api/status")
    client.get("/api/config")
    client.get("/api/cameras")
    client.get("/api/alerts")
    client.get("/api/notifications/log")

    # Confirm pipeline remains stopped and camera capture is not active
    pipeline = get_pipeline_service()
    assert pipeline.is_running is False
    res_status = client.get("/api/status").json()
    assert res_status["is_running"] is False


def test_telemetry_websocket_endpoint(client):
    """Verify WebSocket telemetry broadcast endpoint connects and delivers live snapshots."""
    with client.websocket_connect("/ws/telemetry") as ws:
        msg = ws.receive_json()
        assert isinstance(msg, dict)
        assert "fps" in msg
        assert "person_count" in msg
        assert "risk_level" in msg
        assert "active_alerts" in msg


def test_backend_modules_have_no_fastapi_or_pydantic_imports():
    """Verify backend modules import cleanly without FastAPI or Pydantic runtime dependencies."""
    import inspect
    import backend.main
    import backend.routers.api
    import backend.routers.stream
    import backend.services.pipeline_service
    import backend.services.camera_service
    import backend.services.alert_service

    modules = [
        backend.main,
        backend.routers.api,
        backend.routers.stream,
        backend.services.pipeline_service,
        backend.services.camera_service,
        backend.services.alert_service,
    ]

    for mod in modules:
        source = inspect.getsource(mod)
        assert "import fastapi" not in source, f"fastapi imported in {mod.__name__}"
        assert "from fastapi" not in source, f"fastapi imported in {mod.__name__}"
        assert "import pydantic" not in source, f"pydantic imported in {mod.__name__}"
        assert "from pydantic" not in source, f"pydantic imported in {mod.__name__}"

