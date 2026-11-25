"""
CrowdPatrol Phase 13.3.5 — Windows Camera Device Mapping Utility.
Maps friendly camera device names to explicit OpenCV capture indices for demo deployment,
while providing manual index fallback and light standalone camera verification.
"""

import os
import cv2
import platform
import re
import threading
import time
from pathlib import Path
from typing import Tuple, Union, Optional

class CameraDevice:
    """Represents a discovered video input camera device."""
    def __init__(self, index: int, name: str, status: str = "UNKNOWN", resolution: str = "0x0", is_virtual: bool = False):
        self.index = int(index)
        self.name = str(name)
        self.status = str(status)  # "PASS" or "FAIL"
        self.resolution = str(resolution)
        self.is_virtual = bool(is_virtual)

    @property
    def display_name(self) -> str:
        """User-friendly display string e.g., 'Laptop Integrated Camera (Device 0)'"""
        return f"{self.name} (Device {self.index})"

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "name": self.name,
            "display_name": self.display_name,
            "status": self.status,
            "resolution": self.resolution,
            "is_virtual": self.is_virtual
        }


# Explicit Camera Device Mapping for Demo Machine:
# Device 0 -> Laptop Built-in / Integrated Camera (cv2.VideoCapture(0))
# Device 1 -> External USB Webcam               (cv2.VideoCapture(1))
# Device 2 -> Windows Phone Link Camera        (cv2.VideoCapture(2))
DEMO_MACHINE_CAMERA_MAP = {
    0: {"name": "Laptop Integrated Camera", "is_virtual": False},
    1: {"name": "External USB Webcam", "is_virtual": False},
    2: {"name": "Phone Link Camera", "is_virtual": True},
}


def discover_camera_devices(max_probe: int = 6) -> list:
    """
    Discovers available camera devices on the system.
    Probes OpenCV indices (0..max_probe-1) and assigns explicit demo machine device names.
    Returns a list of CameraDevice objects.
    """
    discovered = []

    for idx in range(max_probe):
        cap = None
        try:
            backend = cv2.CAP_DSHOW if os.name == 'nt' else cv2.CAP_ANY
            cap = cv2.VideoCapture(idx, backend)
            if cap.isOpened():
                ret, frame = cap.read()
                w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

                can_read = bool(ret and frame is not None and frame.size > 0)
                status = "PASS" if can_read else "FAIL"
                resolution = f"{w}x{h}" if can_read else "0x0"

                if idx in DEMO_MACHINE_CAMERA_MAP:
                    dev_name = DEMO_MACHINE_CAMERA_MAP[idx]["name"]
                    is_virtual = DEMO_MACHINE_CAMERA_MAP[idx]["is_virtual"]
                else:
                    dev_name = f"Manual Device Index"
                    is_virtual = False

                discovered.append(CameraDevice(
                    index=idx,
                    name=dev_name,
                    status=status,
                    resolution=resolution,
                    is_virtual=is_virtual
                ))
        except Exception:
            pass
        finally:
            if cap is not None:
                try:
                    cap.release()
                except Exception:
                    pass

    # Fallback if no camera indices were openable
    if not discovered:
        discovered.append(CameraDevice(index=0, name="Manual Device Index", status="FAIL", resolution="0x0"))

    return discovered


def mask_stream_url(url: str) -> str:
    """Masks embedded credentials in stream URLs (e.g., http://user:pass@ip:port -> http://user:***@ip:port)."""
    if not url:
        return ""
    return re.sub(r"://([^:@]+):([^@]+)@", r"://\1:***@", str(url))


def build_phone_stream_url(
    ip_address: str,
    port: int = 8080,
    endpoint: str = "video",
    protocol: str = "http"
) -> str:
    """
    Constructs a standardized stream URL for phone camera apps.
    Examples:
      - IP Webcam:   http://192.168.1.50:8080/video
      - DroidCam:    http://192.168.1.50:4747/video
      - RTSP Camera: rtsp://192.168.1.50:8080/h264_pcm.sdp
    """
    clean_ip = str(ip_address).strip()
    if clean_ip.startswith("http://") or clean_ip.startswith("https://") or clean_ip.startswith("rtsp://"):
        return clean_ip

    ep = f"/{endpoint.lstrip('/')}" if endpoint else ""
    return f"{protocol}://{clean_ip}:{int(port)}{ep}"


def verify_stream_source(source: Union[int, str], timeout_sec: float = 4.0) -> Tuple[bool, str, str, str]:
    """
    Comprehensive verification for camera sources (local device index or phone/IP/RTSP stream URL).
    Employs a bounded timeout worker thread to guarantee the caller never hangs if the network IP is unreachable.
    
    Returns:
        (success: bool, message: str, resolution: str, status: str)
        status values: 'CONNECTED', 'INVALID_STREAM', 'CONNECTION_TIMEOUT', 'DISCONNECTED', 'FAILED'
    """
    if source is None:
        return False, "No camera source provided", "0x0", "INVALID_STREAM"

    source_str = str(source).strip()
    is_network_stream = source_str.startswith("http://") or source_str.startswith("https://") or source_str.startswith("rtsp://")
    safe_display = mask_stream_url(source_str)

    if not is_network_stream:
        # Local hardware device index
        try:
            dev_idx = int(source_str)
        except (ValueError, TypeError):
            return False, f"Invalid device index or URL format: '{source_str}'", "0x0", "INVALID_STREAM"

        cap = None
        try:
            backend = cv2.CAP_DSHOW if os.name == 'nt' else cv2.CAP_ANY
            cap = cv2.VideoCapture(dev_idx, backend)
            if not cap.isOpened():
                return False, f"Unable to open camera device index {dev_idx}", "0x0", "DISCONNECTED"

            ret, frame = cap.read()
            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

            if ret and frame is not None and frame.size > 0:
                return True, f"Camera device {dev_idx} connected successfully ({w}x{h})", f"{w}x{h}", "CONNECTED"
            else:
                return False, f"Camera device {dev_idx} opened but failed to capture frame", "0x0", "DISCONNECTED"
        except Exception as e:
            return False, f"Camera device probe error: {e}", "0x0", "FAILED"
        finally:
            if cap is not None:
                try:
                    cap.release()
                except Exception:
                    pass

    # Network Stream (Phone / IP Webcam / RTSP)
    result = {"success": False, "message": "", "resolution": "0x0", "status": "CONNECTION_TIMEOUT"}

    def _probe_worker():
        cap = None
        try:
            # Direct OpenCV VideoCapture for URL
            cap = cv2.VideoCapture(source_str)
            try:
                cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, int(timeout_sec * 1000))
                cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, int(timeout_sec * 1000))
            except Exception:
                pass

            if not cap.isOpened():
                result["success"] = False
                result["message"] = f"Failed to connect to stream '{safe_display}'. Verify phone app is streaming and laptop is on same Wi-Fi."
                result["status"] = "DISCONNECTED"
                return

            ret, frame = cap.read()
            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

            if ret and frame is not None and frame.size > 0:
                result["success"] = True
                result["message"] = f"Phone/IP camera stream connected successfully ({w}x{h})"
                result["resolution"] = f"{w}x{h}"
                result["status"] = "CONNECTED"
            else:
                result["success"] = False
                result["message"] = f"Stream '{safe_display}' opened but delivered no video frames. Check stream endpoint."
                result["status"] = "DISCONNECTED"
        except Exception as err:
            result["success"] = False
            result["message"] = f"Stream probe error: {err}"
            result["status"] = "FAILED"
        finally:
            if cap is not None:
                try:
                    cap.release()
                except Exception:
                    pass

    probe_thread = threading.Thread(target=_probe_worker, daemon=True)
    probe_thread.start()
    probe_thread.join(timeout=timeout_sec)

    if probe_thread.is_alive():
        return False, f"Connection timeout after {timeout_sec:.1f}s connecting to '{safe_display}'. Check IP address and port.", "0x0", "CONNECTION_TIMEOUT"

    return result["success"], result["message"], result["resolution"], result["status"]


def verify_camera_source(source_idx=0, timeout_sec: float = 4.0) -> tuple:
    """
    Verification for a camera device (supports integer index or URL).
    Returns (success: bool, message: str, resolution: str) for backward compatibility.
    """
    ok, msg, res, _ = verify_stream_source(source_idx, timeout_sec=timeout_sec)
    return ok, msg, res


# Alias for backward compatibility
test_camera_source = verify_camera_source

# Prevent pytest from treating functions in this utility module as pytest test cases
verify_camera_source.__test__ = False
test_camera_source.__test__ = False


def get_camera_display_name(source, device_name=None) -> str:
    """Format camera name and index for UI display."""
    if str(source).isdigit():
        idx = int(source)
        if device_name:
            if f"(Device {idx})" in device_name:
                return device_name
            return f"{device_name} (Device {idx})"
        elif idx in DEMO_MACHINE_CAMERA_MAP:
            name = DEMO_MACHINE_CAMERA_MAP[idx]["name"]
            return f"{name} (Device {idx})"
        else:
            return f"Manual Device Index (Device {idx})"
    return str(source)
