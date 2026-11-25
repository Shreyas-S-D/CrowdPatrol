"""
CrowdPatrol — Starlette Web Application Server
Entrypoint for the CrowdPatrol modern web architecture backend.
Provides REST APIs and WebSocket endpoints for camera capture, YOLOv8/DeepSORT inference,
density estimation, motion analysis, alert management, and live MJPEG streaming.
Pure Python / Starlette ASGI application without FastAPI or Pydantic dependencies.
"""

import sys
from pathlib import Path
from contextlib import asynccontextmanager

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
from starlette.requests import Request
from starlette.routing import Route

# Ensure root directory is on Python path
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

from backend.routers.api import routes as api_routes
from backend.routers.stream import routes as stream_routes
from backend.services.pipeline_service import get_pipeline_service


@asynccontextmanager
async def lifespan(app: Starlette):
    """Lifespan context manager for startup and graceful shutdown."""
    print("[CrowdPatrol Server] Initializing AI backend services...")
    pipeline = get_pipeline_service()
    yield
    print("[CrowdPatrol Server] Shutting down AI backend services...")
    pipeline.stop()


async def root_endpoint(request: Request) -> JSONResponse:
    """Root health and platform identity endpoint."""
    return JSONResponse({
        "platform": "CrowdPatrol",
        "description": "AI-Powered Crowd Monitoring & Risk Assessment Web Application",
        "version": "2.5.0",
        "status": "ONLINE",
        "docs_url": "/docs"
    })


async def healthcheck(request: Request) -> JSONResponse:
    """Service healthcheck."""
    pipeline = get_pipeline_service()
    return JSONResponse({
        "status": "healthy",
        "pipeline_running": pipeline.is_running,
        "detection_mode": pipeline.detection_mode,
        "firebase_connected": pipeline.alert_service.fb_initialized
    })


# Route Assembly
routes = [
    Route("/", root_endpoint, methods=["GET"]),
    Route("/health", healthcheck, methods=["GET"]),
    *api_routes,
    *stream_routes,
]

# CORS Middleware Configuration
middleware = [
    Middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Allows React dev server on any port
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
]

# Starlette Application Instance
app = Starlette(
    debug=False,
    routes=routes,
    middleware=middleware,
    lifespan=lifespan
)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=False)
