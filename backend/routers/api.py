"""
CrowdPatrol Backend — Starlette REST API Router
Exposes endpoints for configuration, system status, camera management,
telemetry analytics, alert acknowledgment/resolution, and notifications.
Pure Python / Starlette ASGI implementation without FastAPI or Pydantic dependencies.
"""

import json
from typing import Dict, Any, Optional, List
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from backend.services.pipeline_service import get_pipeline_service
from backend.services.camera_service import get_camera_service
from backend.services.alert_service import get_alert_service


async def _parse_json(request: Request) -> Dict[str, Any]:
    """Safely parse JSON request body with robust error handling."""
    try:
        data = await request.json()
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


# Route Handlers

async def get_system_status(request: Request) -> JSONResponse:
    """Return overall operational status of CrowdPatrol AI platform."""
    pipeline = get_pipeline_service()
    return JSONResponse({
        "is_running": pipeline.is_running,
        "operating_mode": pipeline.operating_mode,
        "detection_mode": pipeline.detection_mode,
        "tiled_mode": pipeline.tiled_mode,
        "focus_camera": pipeline.focus_camera_id,
        "fps": pipeline.latest_telemetry.get("fps", 0.0),
        "person_count": pipeline.latest_telemetry.get("person_count", 0),
        "risk_level": pipeline.latest_telemetry.get("risk_level", "Low"),
        "active_alerts_count": len(pipeline.alert_service.get_active_alerts()),
        "firebase_connected": pipeline.alert_service.fb_initialized
    })


async def get_configuration(request: Request) -> JSONResponse:
    """Retrieve current vision and pipeline configurations."""
    pipeline = get_pipeline_service()
    return JSONResponse({
        "detection_mode": pipeline.detection_mode,
        "tiled_mode": pipeline.tiled_mode,
        "confidence": pipeline.confidence,
        "detect_interval": pipeline.detect_interval,
        "operating_mode": pipeline.operating_mode,
        "focus_camera": pipeline.focus_camera_id
    })


async def update_configuration(request: Request) -> JSONResponse:
    """Update vision and inference settings dynamically."""
    body = await _parse_json(request)
    pipeline = get_pipeline_service()

    detection_mode = body.get("detection_mode")
    tiled_mode = body.get("tiled_mode")
    confidence = body.get("confidence")
    detect_interval = body.get("detect_interval")
    operating_mode = body.get("operating_mode")

    if detection_mode is not None:
        pipeline.set_detection_mode(str(detection_mode), tiled=bool(tiled_mode) if tiled_mode is not None else False)
    if confidence is not None:
        try:
            pipeline.confidence = max(0.1, min(1.0, float(confidence)))
        except (ValueError, TypeError):
            pass
    if detect_interval is not None:
        try:
            pipeline.detect_interval = max(1, min(10, int(detect_interval)))
        except (ValueError, TypeError):
            pass
    if operating_mode is not None:
        pipeline.set_operating_mode(str(operating_mode))

    return JSONResponse({
        "success": True,
        "detection_mode": pipeline.detection_mode,
        "tiled_mode": pipeline.tiled_mode,
        "confidence": pipeline.confidence,
        "detect_interval": pipeline.detect_interval,
        "operating_mode": pipeline.operating_mode
    })


async def start_monitoring(request: Request) -> JSONResponse:
    """Start the real-time AI capture and inference pipeline."""
    pipeline = get_pipeline_service()
    return JSONResponse(pipeline.start())


async def stop_monitoring(request: Request) -> JSONResponse:
    """Stop the live video pipeline."""
    pipeline = get_pipeline_service()
    return JSONResponse(pipeline.stop())


async def get_cameras(request: Request) -> JSONResponse:
    """Get list of active configured cameras, discovered hardware, and sample videos."""
    cam_svc = get_camera_service()
    pipeline = get_pipeline_service()
    configured = cam_svc.load_cameras_config()
    discovered = cam_svc.get_discovered_devices()
    samples = cam_svc.get_sample_videos()

    live_status = {}
    if pipeline.multi_camera:
        for cid, cobj in pipeline.multi_camera.cameras.items():
            live_status[cid] = cobj.get_debug_info()

    return JSONResponse({
        "configured_cameras": configured,
        "discovered_devices": discovered,
        "sample_videos": samples,
        "live_status": live_status
    })


async def test_camera(request: Request) -> JSONResponse:
    """Test a camera device index, RTSP URL, or video path."""
    body = await _parse_json(request)
    source = body.get("source")
    if source is None:
        return JSONResponse({"success": False, "message": "Field 'source' is required", "status": "ERROR"}, status_code=400)
    cam_svc = get_camera_service()
    return JSONResponse(cam_svc.test_camera_connection(source))


async def set_focus_camera(request: Request) -> JSONResponse:
    """Switch Focus Feed camera."""
    body = await _parse_json(request)
    camera_id = body.get("camera_id")
    if not camera_id:
        return JSONResponse({"success": False, "detail": "Field 'camera_id' is required"}, status_code=400)
    pipeline = get_pipeline_service()
    return JSONResponse(pipeline.set_focus_camera(str(camera_id)))


async def set_camera_layout(request: Request) -> JSONResponse:
    """Switch CCTV layout between 2x2 grid and focus feed."""
    body = await _parse_json(request)
    layout = body.get("layout", "GRID")
    focus_camera = body.get("focus_camera")
    pipeline = get_pipeline_service()
    if focus_camera:
        pipeline.set_focus_camera(str(focus_camera))
    res = pipeline.set_operating_mode(str(layout))
    return JSONResponse({
        "success": res.get("success", True),
        "operating_mode": pipeline.operating_mode,
        "focus_camera": pipeline.focus_camera_id
    })


async def reconfigure_camera(request: Request) -> JSONResponse:
    """Reconfigure a single camera stream source dynamically."""
    body = await _parse_json(request)
    camera_id = body.get("camera_id")
    source = body.get("source")
    if not camera_id or source is None:
        return JSONResponse({"success": False, "detail": "Fields 'camera_id' and 'source' are required"}, status_code=400)

    source_type = body.get("source_type", "video")
    name = body.get("name")
    enabled = body.get("enabled", True)

    pipeline = get_pipeline_service()
    cam_svc = get_camera_service()

    # 1. Update in-memory pipeline
    result = pipeline.reconfigure_camera_source(
        camera_id=str(camera_id),
        source=source,
        source_type=str(source_type) if source_type else "video",
        name=str(name) if name else None,
        enabled=bool(enabled) if enabled is not None else True
    )

    # 2. Persist to cameras.json
    configured = cam_svc.load_cameras_config()
    found = False
    for c in configured:
        if c.get("id") == camera_id:
            c["source"] = str(source)
            if source_type:
                c["source_type"] = source_type
            if name:
                c["name"] = name
            if enabled is not None:
                c["enabled"] = enabled
            found = True
            break
    if not found:
        configured.append({
            "id": camera_id,
            "name": name or f"Camera {camera_id}",
            "source": str(source),
            "source_type": source_type or "video",
            "device_name": None,
            "enabled": enabled if enabled is not None else True
        })
    cam_svc.save_cameras_config(configured)

    return JSONResponse(result)


async def delete_camera(request: Request) -> JSONResponse:
    """Remove a camera feed dynamically and release capture resources."""
    camera_id = request.path_params.get("camera_id")
    if not camera_id:
        return JSONResponse({"success": False, "detail": "camera_id path parameter required"}, status_code=400)

    pipeline = get_pipeline_service()
    cam_svc = get_camera_service()

    result = pipeline.remove_camera(camera_id)

    configured = cam_svc.load_cameras_config()
    configured = [c for c in configured if c.get("id") != camera_id]
    cam_svc.save_cameras_config(configured)

    return JSONResponse(result)


async def generate_phone_camera_url(request: Request) -> JSONResponse:
    """Generate standardized phone camera streaming URL."""
    body = await _parse_json(request)
    ip = body.get("ip")
    if not ip:
        return JSONResponse({"detail": "Field 'ip' is required"}, status_code=400)

    port = body.get("port", 8080)
    try:
        port = int(port) if port else 8080
    except (ValueError, TypeError):
        port = 8080

    app_type = body.get("app_type", "ipwebcam")
    cam_svc = get_camera_service()
    url = cam_svc.generate_phone_url(ip=str(ip), port=port, app_type=str(app_type) if app_type else "ipwebcam")
    return JSONResponse({"url": url})


async def get_analytics_summary(request: Request) -> JSONResponse:
    """Return real-time metrics, spatial grid density, and time-series trend history."""
    pipeline = get_pipeline_service()
    return JSONResponse(pipeline.get_analytics_summary())


async def get_alerts(request: Request) -> JSONResponse:
    """Retrieve active unresolved alerts and historical ledger."""
    raw_limit = request.query_params.get("limit", "50")
    try:
        limit = max(1, min(200, int(raw_limit)))
    except (ValueError, TypeError):
        limit = 50

    alert_svc = get_alert_service()
    return JSONResponse({
        "active_alerts": alert_svc.get_active_alerts(),
        "history": alert_svc.get_alert_history(limit=limit)
    })


async def acknowledge_alert(request: Request) -> JSONResponse:
    """Acknowledge an active emergency alert."""
    camera_id = request.path_params.get("camera_id", "")
    body = await _parse_json(request)
    operator_id = body.get("operator_id", "WebOperator")
    alert_svc = get_alert_service()
    return JSONResponse(alert_svc.acknowledge_alert(camera_id=camera_id, operator_id=operator_id or "WebOperator"))


async def resolve_alert(request: Request) -> JSONResponse:
    """Resolve an emergency alert."""
    camera_id = request.path_params.get("camera_id", "")
    body = await _parse_json(request)
    operator_id = body.get("operator_id", "WebOperator")
    note = body.get("note", "Resolved via CrowdPatrol Web Application")
    alert_svc = get_alert_service()
    return JSONResponse(alert_svc.resolve_alert(
        camera_id=camera_id,
        operator_id=operator_id or "WebOperator",
        note=note or ""
    ))


async def send_test_email(request: Request) -> JSONResponse:
    """Trigger an explicit test email through Gmail SMTP."""
    body = await _parse_json(request)
    to_email = body.get("to_email")
    alert_svc = get_alert_service()
    return JSONResponse(alert_svc.send_test_email(to_email=to_email))


async def get_notification_log(request: Request) -> JSONResponse:
    """Retrieve delivery history of email and SMS notifications."""
    raw_limit = request.query_params.get("limit", "50")
    try:
        limit = max(1, min(200, int(raw_limit)))
    except (ValueError, TypeError):
        limit = 50

    alert_svc = get_alert_service()
    return JSONResponse(alert_svc.get_notification_log(limit=limit))


# Route Definitions Table
routes = [
    Route("/api/status", get_system_status, methods=["GET"]),
    Route("/api/config", get_configuration, methods=["GET"]),
    Route("/api/config", update_configuration, methods=["POST"]),
    Route("/api/monitoring/start", start_monitoring, methods=["POST"]),
    Route("/api/monitoring/stop", stop_monitoring, methods=["POST"]),
    Route("/api/cameras", get_cameras, methods=["GET"]),
    Route("/api/cameras/test", test_camera, methods=["POST"]),
    Route("/api/cameras/focus", set_focus_camera, methods=["POST"]),
    Route("/api/cameras/layout", set_camera_layout, methods=["POST"]),
    Route("/api/cameras/reconfigure", reconfigure_camera, methods=["POST"]),
    Route("/api/cameras/{camera_id}", delete_camera, methods=["DELETE"]),
    Route("/api/cameras/phone-url", generate_phone_camera_url, methods=["POST"]),
    Route("/api/analytics/summary", get_analytics_summary, methods=["GET"]),
    Route("/api/alerts", get_alerts, methods=["GET"]),
    Route("/api/alerts/{camera_id}/acknowledge", acknowledge_alert, methods=["POST"]),
    Route("/api/alerts/{camera_id}/resolve", resolve_alert, methods=["POST"]),
    Route("/api/notifications/test-email", send_test_email, methods=["POST"]),
    Route("/api/notifications/log", get_notification_log, methods=["GET"]),
]
