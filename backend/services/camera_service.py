"""
CrowdPatrol Backend — Camera Management Service
Handles hardware camera discovery, connection testing, phone stream URL generation,
and configuration of the multi-camera CCTV grid.
"""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional

from src.camera_devices import (
    discover_camera_devices,
    test_camera_source,
    get_camera_display_name,
    verify_stream_source,
    build_phone_stream_url
)

BASE_DIR = Path(__file__).parent.parent.parent
CONFIG_PATH = BASE_DIR / "config" / "cameras.json"
VIDEOS_DIR = BASE_DIR / "data" / "videos"


class CameraService:
    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or CONFIG_PATH

    def get_discovered_devices(self) -> List[Dict[str, Any]]:
        """Discover available physical and virtual cameras connected to the system."""
        try:
            devs = discover_camera_devices()
            return [
                {
                    "index": d.index,
                    "name": d.name,
                    "display_name": d.display_name,
                    "is_virtual": d.is_virtual,
                    "is_connected": d.is_connected
                }
                for d in devs
            ]
        except Exception:
            return []

    def get_sample_videos(self) -> List[str]:
        """List available benchmark and sample videos in data/videos/."""
        if not VIDEOS_DIR.exists():
            return []
        vids = []
        for ext in ["*.mp4", "*.avi", "*.mov", "*.mkv", "*.webm"]:
            for f in VIDEOS_DIR.glob(ext):
                vids.append(f"data/videos/{f.name}")
        return sorted(vids)

    def load_cameras_config(self) -> List[Dict[str, Any]]:
        """Load cameras from cameras.json."""
        if not self.config_path.exists():
            return []
        try:
            with open(self.config_path, "r") as f:
                data = json.load(f)
                return data.get("cameras", [])
        except Exception:
            return []

    def save_cameras_config(self, cameras: List[Dict[str, Any]]) -> bool:
        """Persist cameras configuration list to config/cameras.json."""
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, "w") as f:
                json.dump({"cameras": cameras}, f, indent=2)
            return True
        except Exception:
            return False

    def test_camera_connection(self, source: Any) -> Dict[str, Any]:
        """Test whether a camera source (index or URL) can be opened and captured."""
        source_str = str(source).strip()
        if source_str.isdigit():
            ok, msg, res = test_camera_source(int(source_str))
            return {
                "success": ok,
                "message": msg,
                "resolution": f"{res[0]}x{res[1]}" if res else None,
                "status": "ONLINE" if ok else "OFFLINE"
            }
        else:
            ok, msg, res, status = verify_stream_source(source_str, timeout_sec=4.0)
            return {
                "success": ok,
                "message": msg,
                "resolution": f"{res[0]}x{res[1]}" if res else None,
                "status": status
            }

    def generate_phone_url(self, ip: str, port: int = 8080, app_type: str = "ipwebcam") -> str:
        """Generate standardized phone camera stream URL."""
        app_lower = app_type.lower()
        if "droidcam" in app_lower:
            return build_phone_stream_url(ip, port=port or 4747, endpoint="video")
        elif "iriun" in app_lower:
            return build_phone_stream_url(ip, port=port or 8080, endpoint="")
        else:
            # Default IP Webcam
            return build_phone_stream_url(ip, port=port or 8080, endpoint="video")


_camera_service_instance: Optional[CameraService] = None

def get_camera_service() -> CameraService:
    global _camera_service_instance
    if _camera_service_instance is None:
        _camera_service_instance = CameraService()
    return _camera_service_instance
