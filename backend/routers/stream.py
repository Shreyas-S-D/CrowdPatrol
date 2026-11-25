"""
CrowdPatrol Backend — Live Streaming & WebSocket Router
Provides multipart/x-mixed-replace MJPEG video streams for high-performance,
low-latency browser playback, and WebSockets for real-time telemetry broadcast.
Pure Python / Starlette ASGI implementation without FastAPI dependencies.
"""

import asyncio
import time
from typing import Optional
from starlette.requests import Request
from starlette.responses import StreamingResponse
from starlette.websockets import WebSocket, WebSocketDisconnect
from starlette.routing import Route, WebSocketRoute

from backend.services.pipeline_service import get_pipeline_service


async def _mjpeg_generator(camera_id: Optional[str] = None, layout: Optional[str] = None, max_frames: Optional[int] = None):
    """Yield multipart JPEG frames at ~25-30 FPS for browser video stream."""
    pipeline = get_pipeline_service()
    frames_sent = 0
    try:
        while True:
            frame_bytes = pipeline.get_latest_jpeg(camera_id=camera_id, layout=layout)
            if frame_bytes:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                frames_sent += 1
                if max_frames and frames_sent >= max_frames:
                    break
            await asyncio.sleep(0.033)  # ~30 FPS throttle
    except (asyncio.CancelledError, GeneratorExit):
        pass


async def _heatmap_generator(max_frames: Optional[int] = None):
    """Yield multipart JPEG frames of the live density heatmap."""
    pipeline = get_pipeline_service()
    frames_sent = 0
    try:
        while True:
            frame_bytes = pipeline.get_latest_heatmap_jpeg()
            if frame_bytes:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                frames_sent += 1
                if max_frames and frames_sent >= max_frames:
                    break
            await asyncio.sleep(0.05)  # ~20 FPS throttle
    except (asyncio.CancelledError, GeneratorExit):
        pass


async def stream_live_video(request: Request) -> StreamingResponse:
    """
    Primary live video feed: CCTV 2x2 grid (or active focus feed) annotated with
    YOLOv8 bounding boxes, track IDs, spatial density, and risk color indicators.
    Pass layout='grid' or layout='focus' to force specific display layout.
    """
    layout = request.query_params.get("layout")
    raw_max = request.query_params.get("max_frames")
    max_frames = int(raw_max) if raw_max and raw_max.isdigit() else None

    return StreamingResponse(
        _mjpeg_generator(layout=layout, max_frames=max_frames),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


async def stream_single_camera(request: Request) -> StreamingResponse:
    """
    Live stream for a specific individual camera in the CCTV network (e.g. CAM-01).
    """
    camera_id = request.path_params.get("camera_id")
    raw_max = request.query_params.get("max_frames")
    max_frames = int(raw_max) if raw_max and raw_max.isdigit() else None

    return StreamingResponse(
        _mjpeg_generator(camera_id=camera_id, max_frames=max_frames),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


async def stream_heatmap(request: Request) -> StreamingResponse:
    """
    Real-time thermal density heatmap overlay visualizer.
    """
    raw_max = request.query_params.get("max_frames")
    max_frames = int(raw_max) if raw_max and raw_max.isdigit() else None

    return StreamingResponse(
        _heatmap_generator(max_frames=max_frames),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


async def websocket_telemetry_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint broadcasting real-time crowd metrics, velocity vectors,
    active alerts, and FPS metrics at ~10 Hz directly to the React frontend.
    """
    await websocket.accept()
    pipeline = get_pipeline_service()
    try:
        while True:
            # Send latest telemetry snapshot
            telemetry_snapshot = dict(pipeline.latest_telemetry)
            telemetry_snapshot["active_alerts"] = pipeline.alert_service.get_active_alerts()
            await websocket.send_json(telemetry_snapshot)
            await asyncio.sleep(0.1)  # 10 Hz broadcast
    except WebSocketDisconnect:
        pass
    except Exception:
        pass


routes = [
    Route("/api/stream/live", stream_live_video, methods=["GET"]),
    Route("/api/stream/camera/{camera_id}", stream_single_camera, methods=["GET"]),
    Route("/api/stream/heatmap", stream_heatmap, methods=["GET"]),
    WebSocketRoute("/ws/telemetry", websocket_telemetry_endpoint),
]
