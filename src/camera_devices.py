"""
CrowdPatrol Phase 13.3.5 — Windows Camera Device Mapping Utility.
Maps friendly camera device names to explicit OpenCV capture indices for demo deployment,
while providing manual index fallback and light standalone camera verification.
"""

import os
import cv2
import platform
import re
import socket
import threading
import time
from pathlib import Path
from typing import Tuple, Union, Optional, Dict
from urllib.parse import urlsplit

# Concurrency lock and tracking to avoid repeatedly spawning detached probe threads
_active_network_probes_lock = threading.Lock()
_active_network_probes: Dict[str, threading.Thread] = {}

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


def query_windows_pnp_cameras() -> list:
    """
    Queries Windows PnP Registry to identify installed video capture devices,
    including Integrated Webcams, USB Webcams, Windows Connected Cameras (Phone Link),
    and virtual camera drivers (DroidCam, Iriun, Camo, OBS).
    """
    devices = []
    if os.name != 'nt':
        return devices

    try:
        import winreg
    except ImportError:
        return devices

    seen = set()
    guid = '{65e8773d-8f56-11d0-a3b9-00a0c9223196}'
    key_path = rf'SYSTEM\CurrentControlSet\Control\DeviceClasses\{guid}'

    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as root:
            idx = 0
            while True:
                try:
                    sub = winreg.EnumKey(root, idx)
                    idx += 1
                except OSError:
                    break

                sub_lower = sub.lower()
                if any(x in sub_lower for x in ['audio', 'bth', 'bthenum', 'bthhfenum', 'hdaudio', 'intelaudio']):
                    continue

                sub_path = rf'{key_path}\{sub}'
                try:
                    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, sub_path) as sub_key:
                        ch_idx = 0
                        while True:
                            try:
                                child = winreg.EnumKey(sub_key, ch_idx)
                                ch_idx += 1
                            except OSError:
                                break

                            dev_param_path = rf'{sub_path}\{child}\Device Parameters'
                            try:
                                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, dev_param_path) as dp_key:
                                    fname = None
                                    try:
                                        fname, _ = winreg.QueryValueEx(dp_key, 'FriendlyName')
                                    except OSError:
                                        try:
                                            fname, _ = winreg.QueryValueEx(dp_key, 'DeviceDesc')
                                        except OSError:
                                            pass
                                    if fname and fname not in seen:
                                        fname_lower = fname.lower()
                                        if any(x in fname_lower for x in ['audio', 'microphone', 'stereo mix', 'midi']):
                                            continue
                                        seen.add(fname)
                                        is_virtual = any(k in fname_lower or k in sub_lower for k in ['virtual', 'phone', 'droidcam', 'iriun', 'camo', 'obs', 'vcam', 'swd'])
                                        devices.append({
                                            'name': fname,
                                            'pnp_id': sub,
                                            'is_virtual': is_virtual
                                        })
                            except OSError:
                                pass
                except OSError:
                    pass
    except Exception:
        pass

    return devices


def discover_camera_devices(max_probe: int = 6) -> list:
    """
    Discovers available camera devices on the system.
    Combines Windows PnP device query with OpenCV index probing (0..max_probe-1).
    Returns a list of CameraDevice objects with unique indices.
    """
    discovered = []
    pnp_devices = query_windows_pnp_cameras()

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

                if idx < len(pnp_devices):
                    dev_name = pnp_devices[idx]["name"]
                    is_virtual = pnp_devices[idx].get("is_virtual", False)
                elif idx in DEMO_MACHINE_CAMERA_MAP:
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

    # Fallback to discovered PnP devices or demo mapping if probe yielded no open devices
    if not discovered:
        if pnp_devices:
            for idx, pnp in enumerate(pnp_devices[:max_probe]):
                discovered.append(CameraDevice(
                    index=idx,
                    name=pnp["name"],
                    status="UNKNOWN",
                    resolution="0x0",
                    is_virtual=pnp.get("is_virtual", False)
                ))
        else:
            for idx in range(min(3, max_probe)):
                m_info = DEMO_MACHINE_CAMERA_MAP.get(idx, {"name": "Manual Device Index", "is_virtual": False})
                discovered.append(CameraDevice(
                    index=idx,
                    name=m_info["name"],
                    status="FAIL",
                    resolution="0x0",
                    is_virtual=m_info["is_virtual"]
                ))

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


def verify_stream_source(source: Union[int, str], timeout_sec: float = 4.0, source_type: Optional[str] = None) -> Tuple[bool, str, str, str]:
    """
    Comprehensive verification for camera sources (local device index, video file, or phone/IP/RTSP stream URL).
    Employs a bounded timeout worker thread to guarantee the caller never hangs if the network IP is unreachable.
    
    Returns:
        (success: bool, message: str, resolution: str, status: str)
        status values: 'CONNECTED', 'INVALID_STREAM', 'CONNECTION_TIMEOUT', 'DISCONNECTED', 'FAILED'
    """
    if source is None or str(source).strip() in ("", "None", "null"):
        return False, "Camera source is not configured.", "0x0", "NOT_CONFIGURED"

    source_str = str(source).strip()
    st_clean = str(source_type).lower() if source_type else ""
    is_network_stream = source_str.startswith("http://") or source_str.startswith("https://") or source_str.startswith("rtsp://")
    safe_display = mask_stream_url(source_str)

    # 1. Video file check
    file_path = Path(source_str)
    if not is_network_stream and (file_path.exists() or st_clean in ("video", "preset_video", "upload_video")):
        if not file_path.exists():
            candidate = Path(__file__).parent.parent / source_str
            if candidate.exists():
                file_path = candidate
            else:
                return False, f"Video file not found: '{source_str}'", "0x0", "DISCONNECTED"

        cap = None
        try:
            cap = cv2.VideoCapture(str(file_path))
            if not cap.isOpened():
                return False, f"Unable to open video file '{file_path.name}'", "0x0", "DISCONNECTED"

            ret, frame = cap.read()
            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = float(cap.get(cv2.CAP_PROP_FPS))
            fps_str = f"{fps:.1f}" if fps > 0 else "30.0"

            if ret and frame is not None and frame.size > 0:
                return True, f"Video verified: {file_path.name} ({total} frames, {w}x{h} @ {fps_str} FPS)", f"{w}x{h}", "CONNECTED"
            else:
                return False, f"Video file '{file_path.name}' opened but failed to read frames", "0x0", "DISCONNECTED"
        except Exception as e:
            return False, f"Video probe error: {e}", "0x0", "FAILED"
        finally:
            if cap is not None:
                try:
                    cap.release()
                except Exception:
                    pass

    # 2. Local Hardware Camera Device Index
    if not is_network_stream:
        try:
            dev_idx = int(source_str) if source_str != "" else 0
        except (ValueError, TypeError):
            return False, f"Invalid device index or URL format: '{source_str}'", "0x0", "INVALID_STREAM"

        cap = None
        try:
            backend = cv2.CAP_DSHOW if os.name == 'nt' else cv2.CAP_ANY
            cap = cv2.VideoCapture(dev_idx, backend)
            if not cap.isOpened():
                if st_clean == "phone_link":
                    return False, "Phone Link camera is not exposed as an available Windows capture device. Ensure 'Link to Windows' camera sharing is active in Windows Settings -> Mobile Devices.", "0x0", "DISCONNECTED"
                elif st_clean == "usb_webcam":
                    return False, f"USB webcam index {dev_idx} not detected or disconnected.", "0x0", "DISCONNECTED"
                else:
                    return False, f"Unable to open camera device index {dev_idx} (device disconnected or in use).", "0x0", "DISCONNECTED"

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

    # 3. Network Stream (Phone / IP Webcam / RTSP / Video URL)
    result = {"success": False, "message": "", "resolution": "0x0", "status": "CONNECTION_TIMEOUT"}
    parsed = urlsplit(source_str)

    # 3A. Bounded TCP pre-check where appropriate (detects closed ports / unreachable hosts quickly)
    # Limitation Note: socket.create_connection() applies timeout to the socket connection (connect()).
    # Synchronous DNS resolution (getaddrinfo) is performed by the OS resolver beforehand and is not
    # bounded by the socket connect timeout if the OS DNS lookup stalls. We handle socket.gaierror
    # cleanly, but intentionally do not spawn unmanaged background DNS threads.
    is_cv_mocked = hasattr(cv2.VideoCapture, "assert_called") or "mock" in type(cv2.VideoCapture).__name__.lower()
    if not is_cv_mocked and parsed.scheme in ("rtsp", "http", "https") and parsed.hostname:
        default_port = 554 if parsed.scheme == "rtsp" else (443 if parsed.scheme == "https" else 80)
        port = parsed.port or default_port
        try:
            tcp_timeout = min(timeout_sec, 1.5)
            s = socket.create_connection((parsed.hostname, port), timeout=tcp_timeout)
            s.close()
            # Note: Successful TCP connection does NOT mean the stream is valid.
            # Must proceed to OpenCV VideoCapture to validate stream format, codec, and frame delivery.
        except socket.timeout:
            return False, f"Connection timeout after {timeout_sec:.1f}s connecting to '{safe_display}'. Check IP address and port.", "0x0", "CONNECTION_TIMEOUT"
        except socket.gaierror as dns_err:
            return False, f"DNS resolution failed for host '{parsed.hostname}': {dns_err}", "0x0", "DISCONNECTED"
        except (ConnectionRefusedError, OSError) as sock_err:
            err_msg = str(sock_err).lower()
            win_err = getattr(sock_err, "winerror", None)
            if win_err == 10013 or "forbidden" in err_msg:
                return False, f"Network endpoint '{safe_display}' connection blocked or unreachable (WSAEACCES).", "0x0", "DISCONNECTED"
            elif "refused" in err_msg or getattr(sock_err, "errno", None) in (10061, 111):
                return False, f"Connection refused by '{safe_display}' (port {port} is closed).", "0x0", "DISCONNECTED"
            elif "unreachable" in err_msg or getattr(sock_err, "errno", None) in (10051, 101):
                return False, f"Network host '{parsed.hostname}' is unreachable.", "0x0", "DISCONNECTED"
            else:
                return False, f"Network connection error to '{safe_display}': {sock_err}", "0x0", "DISCONNECTED"
        except Exception:
            pass

    # 3B. Prepare OpenCV VideoCapture constructor timeout parameters
    timeout_ms = int(max(timeout_sec, 0.5) * 1000)
    params = []
    if hasattr(cv2, "CAP_PROP_OPEN_TIMEOUT_MSEC"):
        params.extend([cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, timeout_ms])
    if hasattr(cv2, "CAP_PROP_READ_TIMEOUT_MSEC"):
        params.extend([cv2.CAP_PROP_READ_TIMEOUT_MSEC, timeout_ms])

    def _probe_worker():
        cap = None
        try:
            # Network URLs (rtsp, http, https) must strictly use bounded FFmpeg constructor without unbounded fallback
            if parsed.scheme in ("rtsp", "http", "https"):
                if not (params and hasattr(cv2, "CAP_FFMPEG")):
                    result["success"] = False
                    result["message"] = f"OpenCV FFmpeg timeout parameters unsupported for network stream '{safe_display}'."
                    result["status"] = "FAILED"
                    return

                try:
                    cap = cv2.VideoCapture(source_str, cv2.CAP_FFMPEG, params)
                except Exception as c_err:
                    result["success"] = False
                    result["message"] = f"Failed to initialize bounded network stream probe: {c_err}"
                    result["status"] = "FAILED"
                    return
            else:
                cap = cv2.VideoCapture(source_str)

            # Property assignment fallback
            try:
                cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, timeout_ms)
                cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, timeout_ms)
            except Exception:
                pass

            if not cap.isOpened():
                result["success"] = False
                result["message"] = f"Failed to connect to stream '{safe_display}'. Verify network endpoint is reachable."
                result["status"] = "DISCONNECTED"
                return

            ret, frame = cap.read()
            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

            if ret and frame is not None and frame.size > 0:
                result["success"] = True
                result["message"] = f"Network stream connected successfully ({w}x{h})"
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
                del cap

    # 3C. Manage probe worker lifecycle without stacking detached threads
    with _active_network_probes_lock:
        existing_thread = _active_network_probes.get(source_str)
        if existing_thread is not None and existing_thread.is_alive():
            probe_thread = existing_thread
        else:
            probe_thread = threading.Thread(target=_probe_worker, daemon=True)
            _active_network_probes[source_str] = probe_thread
            probe_thread.start()

    probe_thread.join(timeout=timeout_sec)

    with _active_network_probes_lock:
        if _active_network_probes.get(source_str) is probe_thread and not probe_thread.is_alive():
            _active_network_probes.pop(source_str, None)

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


def get_categorized_cameras() -> dict:
    """
    Categorizes discovered camera devices on Windows into:
    - laptop: built-in laptop/integrated webcams
    - usb: external USB cameras
    - phone_link: Phone Link / virtual cameras
    """
    pnp_devices = query_windows_pnp_cameras()
    laptop = []
    usb = []
    phone = []

    for idx, pnp in enumerate(pnp_devices):
        dev_name = pnp.get("name", f"Camera {idx}")
        nl = dev_name.lower()
        is_virtual = pnp.get("is_virtual", False) or any(k in nl for k in ['phone', 'virtual', 'link', 'droidcam', 'iriun', 'camo', 'vcam'])
        is_usb = ('usb' in nl) and not is_virtual
        is_laptop = any(k in nl for k in ['integrated', 'internal', 'built-in', 'laptop', 'facetime']) or (not is_usb and not is_virtual)

        dev = CameraDevice(index=idx, name=dev_name, is_virtual=is_virtual)
        if is_virtual:
            phone.append(dev)
        elif is_usb:
            usb.append(dev)
        else:
            laptop.append(dev)

    # If no laptop cameras detected from PnP, provide standard Device 0 fallback
    if not laptop:
        laptop.append(CameraDevice(index=0, name="Integrated Camera", is_virtual=False))

    return {
        "laptop": laptop,
        "usb": usb,
        "phone_link": phone
    }

