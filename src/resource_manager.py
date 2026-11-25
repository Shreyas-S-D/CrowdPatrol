"""
src/resource_manager.py
-----------------------
CrowdPatrol 2.0 — Centralized Physical Device & Compute Resource Manager.

Orchestrates multi-tenant resource allocation:
1. Physical device ownership: Exclusive locking for local webcams / hardware capture devices.
2. Contention handling: Reports clear status (DEVICE_IN_USE) instead of crashes or frozen streams.
3. Compute capacity scheduling: Bounded concurrent active monitoring sessions across all tenants.
4. Safe lifecycle cleanup and stale session recovery.
"""

import time
import threading
from typing import Dict, Any, Optional, Tuple, List
from dataclasses import dataclass


@dataclass
class DeviceLock:
    device_id: str
    organization_id: str
    session_id: str
    slot_id: str
    acquired_at: float


class PhysicalDeviceRegistry:
    """
    Central thread-safe registry for exclusive hardware capture devices (e.g. webcams).
    Prevents simultaneous OpenCV VideoCapture attempts that lock or crash hardware.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._device_locks: Dict[str, DeviceLock] = {}

    @staticmethod
    def normalize_device_id(source: Any, source_type: str) -> Optional[str]:
        """Normalizes source into a hardware resource ID if it requires exclusive hardware access."""
        st = str(source_type).lower().strip()
        if st in ("webcam", "camera", "laptop_camera", "usb_webcam", "phone_link"):
            try:
                idx = int(source)
                return f"webcam_{idx}"
            except (ValueError, TypeError):
                s_str = str(source).strip()
                if s_str and not (s_str.startswith("http://") or s_str.startswith("https://") or s_str.startswith("rtsp://")):
                    return f"webcam_{s_str}"
        return None

    def acquire_device(
        self,
        device_id: str,
        organization_id: str,
        session_id: str,
        slot_id: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Attempts to acquire an exclusive lock on a physical camera device.
        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        with self._lock:
            existing = self._device_locks.get(device_id)
            if existing is not None:
                # Same session & same slot is re-entrant
                if existing.organization_id == organization_id and existing.session_id == session_id:
                    if existing.slot_id == slot_id:
                        return True, None
                    msg = (
                        f"Physical camera device '{device_id}' is already assigned to slot '{existing.slot_id}' "
                        f"in this monitoring session. A physical camera cannot be shared across multiple slots."
                    )
                    return False, msg
                # Another organization or session holds the device
                msg = (
                    f"Physical camera device '{device_id}' is currently in use by "
                    f"organization '{existing.organization_id}' (Session: {existing.session_id})."
                )
                return False, msg

            # Device is available
            self._device_locks[device_id] = DeviceLock(
                device_id=device_id,
                organization_id=organization_id,
                session_id=session_id,
                slot_id=slot_id,
                acquired_at=time.time()
            )
            return True, None

    def release_device(self, device_id: str, organization_id: str, session_id: str) -> bool:
        """Releases a specific device lock if held by the given session."""
        with self._lock:
            existing = self._device_locks.get(device_id)
            if existing and existing.organization_id == organization_id and existing.session_id == session_id:
                del self._device_locks[device_id]
                return True
            return False

    def release_session_devices(self, organization_id: str, session_id: str) -> int:
        """Releases all physical devices locked by a given monitoring session."""
        released_count = 0
        with self._lock:
            to_remove = [
                d_id for d_id, lock in self._device_locks.items()
                if lock.organization_id == organization_id and lock.session_id == session_id
            ]
            for d_id in to_remove:
                del self._device_locks[d_id]
                released_count += 1
        return released_count

    def get_device_status(self, device_id: str) -> Dict[str, Any]:
        """Returns diagnostic lock status for a physical device."""
        with self._lock:
            existing = self._device_locks.get(device_id)
            if existing:
                return {
                    "device_id": device_id,
                    "locked": True,
                    "organization_id": existing.organization_id,
                    "session_id": existing.session_id,
                    "slot_id": existing.slot_id,
                    "held_duration_sec": round(time.time() - existing.acquired_at, 1)
                }
            return {"device_id": device_id, "locked": False}

    def list_active_locks(self) -> List[Dict[str, Any]]:
        """Returns all currently active hardware device locks."""
        with self._lock:
            now = time.time()
            return [
                {
                    "device_id": lock.device_id,
                    "organization_id": lock.organization_id,
                    "session_id": lock.session_id,
                    "slot_id": lock.slot_id,
                    "held_duration_sec": round(now - lock.acquired_at, 1)
                }
                for lock in self._device_locks.values()
            ]


class ComputeScheduler:
    """
    Manages host computing resource allocation across tenant monitoring sessions.
    Prevents CPU/GPU starvation and throttles concurrent multi-camera inference pipelines.
    """

    def __init__(self, max_concurrent_sessions: int = 2):
        self._lock = threading.Lock()
        self.max_concurrent_sessions = max_concurrent_sessions
        self._active_sessions: Dict[str, Dict[str, Any]] = {}

    def register_session_start(
        self,
        organization_id: str,
        session_id: str,
        camera_count: int = 4
    ) -> Tuple[bool, Optional[str]]:
        """
        Evaluates system capacity before allowing a new tenant monitoring session to start.
        """
        with self._lock:
            # If already registered, update heartbeat
            if session_id in self._active_sessions:
                self._active_sessions[session_id]["last_heartbeat"] = time.time()
                return True, None

            # Check capacity
            current_count = len(self._active_sessions)
            if current_count >= self.max_concurrent_sessions:
                return False, (
                    f"Host compute capacity limit reached ({current_count}/{self.max_concurrent_sessions} active). "
                    "Please wait for an active monitoring session to finish or stop another session."
                )

            self._active_sessions[session_id] = {
                "organization_id": organization_id,
                "session_id": session_id,
                "camera_count": camera_count,
                "started_at": time.time(),
                "last_heartbeat": time.time()
            }
            return True, None

    def register_heartbeat(self, session_id: str) -> None:
        """Pings heartbeat for an active session."""
        with self._lock:
            if session_id in self._active_sessions:
                self._active_sessions[session_id]["last_heartbeat"] = time.time()

    def register_session_stop(self, session_id: str) -> None:
        """De-registers a completed or stopped session."""
        with self._lock:
            self._active_sessions.pop(session_id, None)

    def cleanup_stale_sessions(
        self,
        device_registry: PhysicalDeviceRegistry,
        stale_threshold_seconds: float = 90.0
    ) -> List[str]:
        """Automatically recovers resources from abandoned or crashed sessions."""
        now = time.time()
        stale_ids = []
        with self._lock:
            for s_id, s_info in list(self._active_sessions.items()):
                if now - s_info["last_heartbeat"] > stale_threshold_seconds:
                    stale_ids.append((s_id, s_info["organization_id"]))

        for s_id, org_id in stale_ids:
            with self._lock:
                self._active_sessions.pop(s_id, None)
            device_registry.release_session_devices(org_id, s_id)

        return [s[0] for s in stale_ids]

    def get_scheduler_status(self) -> Dict[str, Any]:
        """Returns diagnostic compute scheduler status."""
        with self._lock:
            return {
                "max_concurrent_sessions": self.max_concurrent_sessions,
                "active_sessions_count": len(self._active_sessions),
                "sessions": list(self._active_sessions.values())
            }

    def get_active_session_count(self) -> int:
        """Returns the number of currently active compute sessions."""
        with self._lock:
            return len(self._active_sessions)


# Global shared instances
_GLOBAL_DEVICE_REGISTRY = PhysicalDeviceRegistry()
_GLOBAL_COMPUTE_SCHEDULER = ComputeScheduler(max_concurrent_sessions=2)


def get_device_registry() -> PhysicalDeviceRegistry:
    return _GLOBAL_DEVICE_REGISTRY


def get_compute_scheduler() -> ComputeScheduler:
    return _GLOBAL_COMPUTE_SCHEDULER
