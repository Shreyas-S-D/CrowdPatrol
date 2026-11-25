"""
CrowdPatrol Backend — Alert & Notification Service
Manages active and historical alerts, operator acknowledgement/resolution,
Gmail SMTP alert dispatches, and Firebase Realtime Database telemetry synchronization.
"""

import os
import json
import time
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

import firebase_admin
from firebase_admin import credentials, db

from src.alert_manager import AlertManager, AlertEvent
from src.notification_dispatcher import get_notification_dispatcher
from dashboard.dashboard_utils import normalize_telemetry_payload, load_offline_csv_fallback


class AlertService:
    def __init__(self):
        self.notification_dispatcher = get_notification_dispatcher()
        self.alert_manager = AlertManager(
            cooldown_seconds=10,
            enable_local_logging=True,
            notification_dispatcher=self.notification_dispatcher
        )
        self.fb_initialized = self._init_firebase()
        self.alert_history: List[Dict[str, Any]] = []

    def _init_firebase(self) -> bool:
        """Initialize Firebase once with fail-safe error handling."""
        try:
            firebase_admin.get_app()
            return True
        except ValueError:
            try:
                cred_path = Path(__file__).parent.parent.parent / 'firebase-credentials.json'
                if not cred_path.exists():
                    return False
                cred = credentials.Certificate(str(cred_path))
                firebase_admin.initialize_app(cred, {
                    'databaseURL': 'https://crowdpatrol-default-rtdb.asia-southeast1.firebasedatabase.app'
                })
                return True
            except Exception:
                return False

    def get_active_alerts(self) -> List[Dict[str, Any]]:
        """Return list of all currently active (unresolved) alerts across all cameras."""
        active = []
        for cam_id, alert in self.alert_manager.active_alerts.items():
            if alert is not None:
                active.append(alert.to_dict())
        return active

    def get_alert_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Fetch recent alert history from memory ledger, Firebase, or offline fallback.
        """
        if self.fb_initialized:
            try:
                alerts_ref = db.reference('alerts')
                fb_alerts = alerts_ref.order_by_key().limit_to_last(limit).get()
                if fb_alerts:
                    return [v for v in fb_alerts.values()][::-1]
            except Exception:
                pass

        # Return memory ledger plus locally logged alerts
        recent_mem = [a.to_dict() for a in self.alert_manager.alert_history[-limit:]]
        return recent_mem[::-1] if recent_mem else []

    def acknowledge_alert(self, camera_id: str, operator_id: str = "WebOperator") -> Dict[str, Any]:
        """Acknowledge an active alert for a specific camera feed."""
        ok = self.alert_manager.acknowledge_alert(camera_id, operator_id=operator_id)
        return {
            "success": ok,
            "camera_id": camera_id,
            "acknowledged_by": operator_id if ok else None,
            "message": f"Alert for {camera_id} acknowledged by {operator_id}" if ok else f"No active unacknowledged alert for {camera_id}"
        }

    def resolve_alert(self, camera_id: str, operator_id: str = "WebOperator", note: str = "Resolved via Web Client") -> Dict[str, Any]:
        """Resolve and archive an active alert for a camera."""
        ok = self.alert_manager.resolve_alert(camera_id, operator_id=operator_id, note=note)
        return {
            "success": ok,
            "camera_id": camera_id,
            "resolved_by": operator_id if ok else None,
            "message": f"Alert for {camera_id} resolved" if ok else f"No active alert to resolve for {camera_id}"
        }

    def send_test_email(self, to_email: Optional[str] = None) -> Dict[str, Any]:
        """Trigger an explicit test email via NotificationDispatcher."""
        ok, msg = self.notification_dispatcher.send_test_email(to_email=to_email)
        return {
            "success": ok,
            "message": msg
        }

    def get_notification_log(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Return notification delivery ledger."""
        records = self.notification_dispatcher.get_history(limit=limit)
        return [r.to_dict() for r in records]

    def sync_telemetry_to_firebase(self, payload: Dict[str, Any]):
        """Push latest telemetry frame payload to Firebase RTDB."""
        if not self.fb_initialized:
            return
        try:
            db.reference('dashboard').set(payload)
        except Exception:
            pass


_alert_service_instance: Optional[AlertService] = None

def get_alert_service() -> AlertService:
    global _alert_service_instance
    if _alert_service_instance is None:
        _alert_service_instance = AlertService()
    return _alert_service_instance
