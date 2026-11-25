"""
CrowdPatrol Phase 13.3.5 — Windows Camera Device Mapping Utility.
Maps friendly camera device names to explicit OpenCV capture indices for demo deployment,
while providing manual index fallback and light standalone camera verification.
"""

import cv2
import platform
from pathlib import Path

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
        cap = cv2.VideoCapture(idx)
        if cap.isOpened():
            ret, frame = cap.read()
            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            cap.release()

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

    # Fallback if no camera indices were openable
    if not discovered:
        discovered.append(CameraDevice(index=0, name="Manual Device Index", status="FAIL", resolution="0x0"))

    return discovered


def verify_camera_source(source_idx=0) -> tuple:
    """
    Standalone verification for a camera device index.
    Opens cv2.VideoCapture(source_idx), captures 1 frame, and releases immediately.
    Returns (success: bool, message: str, resolution: str).
    """
    try:
        idx = int(source_idx)
    except (ValueError, TypeError):
        return False, f"Invalid device index: '{source_idx}'", "0x0"

    cap = cv2.VideoCapture(idx)
    if not cap.isOpened():
        return False, f"Unable to open camera device index {idx}", "0x0"

    ret, frame = cap.read()
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()

    if ret and frame is not None and frame.size > 0:
        return True, f"Camera device {idx} connected successfully ({w}x{h})", f"{w}x{h}"
    else:
        return False, f"Camera device {idx} opened but failed to capture frame", "0x0"


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
