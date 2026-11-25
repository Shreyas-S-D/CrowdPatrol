"""
src/auth/tenant_operational_service.py
--------------------------------------
CrowdPatrol 2.0 — Phase 2B.3 Operational Tenant Isolation Service.

Enforces server-side tenant scoping and RBAC for all surveillance operations:
- Camera slot configurations (4 slots per organization).
- Monitoring session lifecycle and compute scheduling.
- Physical device locking and contention mitigation.
- Tenant-scoped alerts, lifecycle transitions, and analytics.
- Isolated video asset uploads with path traversal protection.
- Tenant notification settings.
- Operational audit event logging.
"""

import os
import re
import uuid
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timezone

from src.auth.database import (
    AuthDatabase,
    User,
    Organization,
    OrganizationMembership,
    TenantCameraConfig,
    TenantMonitoringSession,
    TenantAlertRecord,
    TenantNotificationSettings,
    TenantUploadedAsset
)
from src.auth.organization_service import resolve_tenant_context, is_platform_admin
from src.resource_manager import get_device_registry, get_compute_scheduler

ROLE_PLATFORM_ADMIN = "PLATFORM_ADMIN"
ROLE_ORG_ADMIN = "ORG_ADMIN"
ROLE_OPERATOR = "OPERATOR"
ROLE_VIEWER = "VIEWER"

BASE_TENANT_DATA_DIR = Path("data/tenants")


class TenantOperationalService:
    """
    Core service enforcing multi-tenant isolation across all surveillance operations.
    """

    def __init__(
        self,
        db: AuthDatabase,
        device_registry: Optional[PhysicalDeviceRegistry] = None,
        compute_scheduler: Optional[ComputeScheduler] = None
    ):
        self.db = db
        self.device_registry = device_registry or get_device_registry()
        self.compute_scheduler = compute_scheduler or get_compute_scheduler()

    def _resolve_context(
        self,
        actor: User,
        organization_id: str
    ) -> Tuple[Organization, Optional[OrganizationMembership]]:
        """
        Server-side validation of active membership. Never trusts client-supplied tenant context.
        Raises PermissionError if unauthorized.
        """
        try:
            org, mem = resolve_tenant_context(user=actor, requested_org_id=organization_id, db=self.db)
            if not org:
                raise PermissionError(f"Access denied: Organization '{organization_id}' not accessible.")
            return org, mem
        except (ValueError, PermissionError) as e:
            raise PermissionError(f"Access denied to organization '{organization_id}': {e}") from e

    def _require_non_viewer(
        self,
        actor: User,
        organization_id: str,
        action_name: str
    ) -> Tuple[Organization, Optional[OrganizationMembership]]:
        """Enforces that VIEWER roles are strictly prohibited from performing write or operational actions."""
        org, mem = self._resolve_context(actor, organization_id)
        if is_platform_admin(actor):
            return org, mem
        if mem and mem.role == ROLE_VIEWER:
            raise PermissionError(f"Role 'VIEWER' has read-only access and cannot {action_name}.")
        return org, mem

    def _require_org_admin(
        self,
        actor: User,
        organization_id: str,
        action_name: str
    ) -> Tuple[Organization, Optional[OrganizationMembership]]:
        """Enforces ORG_ADMIN or PLATFORM_ADMIN role for administrative operational tasks."""
        org, mem = self._resolve_context(actor, organization_id)
        if is_platform_admin(actor):
            return org, mem
        if not mem or mem.role not in (ROLE_ORG_ADMIN, "ADMIN"):
            raise PermissionError(f"Administrative privilege required to {action_name}.")
        return org, mem

    # =========================================================================
    # 1. CAMERA CONFIGURATION MANAGEMENT
    # =========================================================================

    def get_camera_configs(self, actor: User, organization_id: str) -> List[TenantCameraConfig]:
        """Returns the 4 camera slots configured for the active organization."""
        org, _ = self._resolve_context(actor, organization_id)
        return self.db.get_camera_configs(org.id)

    def update_camera_config(
        self,
        actor: User,
        organization_id: str,
        slot_id: str,
        name: str,
        source_type: str,
        source: str,
        device_name: Optional[str] = None,
        enabled: bool = True,
        detection_mode: str = "PERSON"
    ) -> TenantCameraConfig:
        """
        Updates a specific camera slot for an organization.
        Enforces that VIEWER cannot modify cameras.
        """
        org, _ = self._require_non_viewer(actor, organization_id, "modify camera configurations")

        clean_slot = slot_id.strip().upper()
        if clean_slot not in ("CAM-01", "CAM-02", "CAM-03", "CAM-04"):
            raise ValueError(f"Invalid camera slot ID '{slot_id}'. Must be one of CAM-01..CAM-04.")

        cfg = self.db.upsert_camera_config(
            organization_id=org.id,
            slot_id=clean_slot,
            name=name.strip() or f"Camera {clean_slot}",
            source_type=str(source_type).lower().strip(),
            source=str(source).strip(),
            device_name=device_name.strip() if device_name else None,
            enabled=enabled,
            detection_mode=detection_mode.upper() if detection_mode in ("PERSON", "HEAD") else "PERSON"
        )

        # Audit event
        event_id = f"aud_{uuid.uuid4().hex[:12]}"
        self.db.create_audit_event(
            event_id=event_id,
            organization_id=org.id,
            actor_user_id=actor.id,
            action="CAMERA_CONFIG_UPDATED",
            target_type="CAMERA_SLOT",
            target_id=clean_slot,
            metadata={
                "slot_id": clean_slot,
                "name": cfg.name,
                "source_type": cfg.source_type,
                "enabled": cfg.enabled,
                "detection_mode": cfg.detection_mode
            }
        )
        return cfg

    # =========================================================================
    # 2. MONITORING SESSIONS & RESOURCE ALLOCATION
    # =========================================================================

    def start_monitoring_session(
        self,
        actor: User,
        organization_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Tuple[TenantMonitoringSession, Dict[str, Any]]:
        """
        Initiates an active surveillance session for an organization.
        Performs:
        1. Role verification (VIEWER cannot start monitoring).
        2. Host compute scheduling check (bounded concurrent sessions).
        3. Physical device locking for hardware devices (webcams).
        4. Clear contention reporting if a physical device is locked by another session.
        """
        org, _ = self._require_non_viewer(actor, organization_id, "start surveillance monitoring")

        # Check existing active session
        existing_session = self.db.get_active_monitoring_session(org.id)
        if existing_session:
            return existing_session, {"status": "ALREADY_ACTIVE", "device_issues": []}

        # Check host compute capacity
        session_id = f"sess_{uuid.uuid4().hex[:12]}"
        can_schedule, sched_err = self.compute_scheduler.register_session_start(
            organization_id=org.id,
            session_id=session_id,
            camera_count=4
        )
        if not can_schedule:
            raise RuntimeError(sched_err)

        # Retrieve camera configs and evaluate physical device ownership
        configs = self.db.get_camera_configs(org.id)
        device_issues = []
        acquired_devices = []

        for cam in configs:
            if not cam.enabled:
                continue
            dev_id = self.device_registry.normalize_device_id(cam.source, cam.source_type)
            if dev_id:
                acquired, lock_err = self.device_registry.acquire_device(
                    device_id=dev_id,
                    organization_id=org.id,
                    session_id=session_id,
                    slot_id=cam.slot_id
                )
                if not acquired:
                    device_issues.append({
                        "slot_id": cam.slot_id,
                        "device_id": dev_id,
                        "status": "DEVICE_IN_USE",
                        "message": lock_err
                    })
                else:
                    acquired_devices.append(dev_id)

        meta = {
            **(metadata or {}),
            "acquired_devices": acquired_devices,
            "device_issues": device_issues,
            "camera_slots": [c.slot_id for c in configs if c.enabled]
        }

        session = self.db.create_monitoring_session(
            session_id=session_id,
            organization_id=org.id,
            started_by=actor.id,
            metadata=meta
        )

        # Audit event
        event_id = f"aud_{uuid.uuid4().hex[:12]}"
        self.db.create_audit_event(
            event_id=event_id,
            organization_id=org.id,
            actor_user_id=actor.id,
            action="MONITORING_STARTED",
            target_type="MONITORING_SESSION",
            target_id=session_id,
            metadata=meta
        )

        return session, {"status": "STARTED", "device_issues": device_issues}

    def stop_monitoring_session(
        self,
        actor: User,
        organization_id: str,
        session_id: Optional[str] = None
    ) -> Optional[TenantMonitoringSession]:
        """
        Terminates an active monitoring session and cleanly releases all locked hardware resources.
        """
        org, _ = self._require_non_viewer(actor, organization_id, "stop surveillance monitoring")

        if session_id:
            sess = self.db.get_monitoring_session(session_id)
        else:
            sess = self.db.get_active_monitoring_session(org.id)

        if not sess or sess.organization_id != org.id:
            return None

        # Release physical devices
        self.device_registry.release_session_devices(org.id, sess.id)

        # Deregister from compute scheduler
        self.compute_scheduler.register_session_stop(sess.id)

        # Update database session record
        stopped = self.db.stop_monitoring_session(sess.id, ended_by=actor.id, status="STOPPED")

        # Audit event
        event_id = f"aud_{uuid.uuid4().hex[:12]}"
        self.db.create_audit_event(
            event_id=event_id,
            organization_id=org.id,
            actor_user_id=actor.id,
            action="MONITORING_STOPPED",
            target_type="MONITORING_SESSION",
            target_id=sess.id,
            metadata={"session_id": sess.id}
        )
        return stopped

    def get_active_session(self, actor: User, organization_id: str) -> Optional[TenantMonitoringSession]:
        """Retrieves currently active monitoring session for the organization."""
        org, _ = self._resolve_context(actor, organization_id)
        return self.db.get_active_monitoring_session(org.id)

    def list_monitoring_sessions(self, actor: User, organization_id: str, limit: int = 50) -> List[TenantMonitoringSession]:
        """Lists historical monitoring sessions for the organization."""
        org, _ = self._resolve_context(actor, organization_id)
        return self.db.list_monitoring_sessions(org.id, limit=limit)

    # =========================================================================
    # 3. ALERTS & LIFECYCLE MANAGEMENT
    # =========================================================================

    def record_alert(
        self,
        organization_id: str,
        session_id: Optional[str],
        camera_id: str,
        camera_name: str,
        risk_level: str,
        risk_score: float,
        severity: str,
        category: str,
        reason: str,
        crowd_density: int = 0,
        person_count: int = 0,
        primary_risk_zone: str = "A1",
        primary_zone_density: int = 0,
        zone_description: str = "Top-Left",
        details: Optional[Dict[str, Any]] = None,
        alert_id: Optional[str] = None
    ) -> TenantAlertRecord:
        """
        Persists an alert strictly scoped to an organization and monitoring session.
        If alert_id is provided, preserves it to ensure cross-system identity with AlertManager.
        """
        clean_alert_id = alert_id or f"alt_{uuid.uuid4().hex[:12]}"
        alert = self.db.create_tenant_alert(
            alert_id=clean_alert_id,
            organization_id=organization_id,
            session_id=session_id,
            camera_id=camera_id,
            camera_name=camera_name,
            risk_level=risk_level,
            risk_score=risk_score,
            severity=severity,
            category=category,
            reason=reason,
            crowd_density=crowd_density,
            person_count=person_count,
            primary_risk_zone=primary_risk_zone,
            primary_zone_density=primary_zone_density,
            zone_description=zone_description,
            details=details
        )
        return alert

    def list_alerts(
        self,
        actor: User,
        organization_id: str,
        status: Optional[str] = None,
        camera_id: Optional[str] = None,
        limit: int = 100
    ) -> List[TenantAlertRecord]:
        """Lists tenant-isolated alerts."""
        org, _ = self._resolve_context(actor, organization_id)
        return self.db.list_tenant_alerts(org.id, status=status, camera_id=camera_id, limit=limit)

    def acknowledge_alert(self, actor: User, organization_id: str, alert_id: str) -> Optional[TenantAlertRecord]:
        """Acknowledges an active alert. VIEWER cannot acknowledge."""
        org, _ = self._require_non_viewer(actor, organization_id, "acknowledge alerts")
        alert = self.db.get_tenant_alert(alert_id)
        if not alert or alert.organization_id != org.id:
            raise PermissionError("Alert not found in active organization.")

        acked = self.db.acknowledge_tenant_alert(alert_id, user_id=actor.id)

        # Audit event
        event_id = f"aud_{uuid.uuid4().hex[:12]}"
        self.db.create_audit_event(
            event_id=event_id,
            organization_id=org.id,
            actor_user_id=actor.id,
            action="ALERT_ACKNOWLEDGED",
            target_type="TENANT_ALERT",
            target_id=alert_id,
            metadata={"alert_id": alert_id, "camera_id": alert.camera_id}
        )
        return acked

    def resolve_alert(
        self,
        actor: User,
        organization_id: str,
        alert_id: str,
        note: Optional[str] = None
    ) -> Optional[TenantAlertRecord]:
        """Resolves an alert. VIEWER cannot resolve."""
        org, _ = self._require_non_viewer(actor, organization_id, "resolve alerts")
        alert = self.db.get_tenant_alert(alert_id)
        if not alert or alert.organization_id != org.id:
            raise PermissionError("Alert not found in active organization.")

        resolved = self.db.resolve_tenant_alert(alert_id, user_id=actor.id, note=note)

        # Audit event
        event_id = f"aud_{uuid.uuid4().hex[:12]}"
        self.db.create_audit_event(
            event_id=event_id,
            organization_id=org.id,
            actor_user_id=actor.id,
            action="ALERT_RESOLVED",
            target_type="TENANT_ALERT",
            target_id=alert_id,
            metadata={"alert_id": alert_id, "note": note}
        )
        return resolved

    def get_analytics_summary(self, actor: User, organization_id: str) -> Dict[str, Any]:
        """Computes risk and alert metrics strictly isolated to the specified organization."""
        org, _ = self._resolve_context(actor, organization_id)
        stats = self.db.get_tenant_alerts_summary(org.id)
        sessions = self.db.list_monitoring_sessions(org.id, limit=20)
        recent_alerts = self.db.list_tenant_alerts(org.id, limit=50)

        # Camera risk distribution
        cam_counts = {}
        for a in recent_alerts:
            cam_counts[a.camera_id] = cam_counts.get(a.camera_id, 0) + 1

        return {
            "organization_name": org.name,
            "organization_slug": org.slug,
            "alert_counts": stats,
            "total_sessions": len(sessions),
            "recent_sessions": sessions,
            "camera_alert_distribution": cam_counts,
            "recent_alerts": [
                {
                    "id": a.id,
                    "camera_id": a.camera_id,
                    "risk_level": a.risk_level,
                    "risk_score": a.risk_score,
                    "reason": a.reason,
                    "status": a.status,
                    "created_at": a.created_at.strftime("%Y-%m-%d %H:%M:%S UTC")
                }
                for a in recent_alerts[:10]
            ]
        }

    # =========================================================================
    # 4. ASSET UPLOAD & STORAGE ISOLATION
    # =========================================================================

    def save_uploaded_video(
        self,
        actor: User,
        organization_id: str,
        file_bytes: bytes,
        original_filename: str,
        slot_id: Optional[str] = None
    ) -> TenantUploadedAsset:
        """
        Saves an uploaded video asset into an isolated organization directory.
        Strictly prevents directory traversal and rejects invalid filenames.
        """
        org, _ = self._require_non_viewer(actor, organization_id, "upload video assets")

        # Path traversal prevention: strip directories and dangerous characters
        clean_name = os.path.basename(original_filename.strip())
        clean_name = re.sub(r"[^a-zA-Z0-9_\-\. ]", "_", clean_name)
        if not clean_name or clean_name.startswith("."):
            clean_name = f"upload_{uuid.uuid4().hex[:8]}.mp4"

        # Ensure isolated storage directory
        org_dir = BASE_TENANT_DATA_DIR / org.id / "videos"
        org_dir.mkdir(parents=True, exist_ok=True)

        target_path = (org_dir / f"{uuid.uuid4().hex[:8]}_{clean_name}").resolve()

        # Enforce canonical path containment
        base_dir_resolved = org_dir.resolve()
        if not str(target_path).startswith(str(base_dir_resolved)):
            raise PermissionError("Access denied: path traversal attempt detected.")

        with open(target_path, "wb") as f:
            f.write(file_bytes)

        asset_id = f"asset_{uuid.uuid4().hex[:12]}"
        asset = self.db.create_uploaded_asset(
            asset_id=asset_id,
            organization_id=org.id,
            uploaded_by=actor.id,
            filename=clean_name,
            storage_path=str(target_path),
            file_size_bytes=len(file_bytes),
            mime_type="video/mp4",
            slot_id=slot_id
        )

        # Audit event
        event_id = f"aud_{uuid.uuid4().hex[:12]}"
        self.db.create_audit_event(
            event_id=event_id,
            organization_id=org.id,
            actor_user_id=actor.id,
            action="VIDEO_UPLOADED",
            target_type="TENANT_ASSET",
            target_id=asset_id,
            metadata={"filename": clean_name, "size_bytes": len(file_bytes), "slot_id": slot_id}
        )
        return asset

    def list_uploaded_assets(self, actor: User, organization_id: str) -> List[TenantUploadedAsset]:
        """Lists uploaded video assets belonging to the active organization."""
        org, _ = self._resolve_context(actor, organization_id)
        return self.db.list_uploaded_assets(org.id)

    # =========================================================================
    # 5. NOTIFICATION SETTINGS
    # =========================================================================

    def get_notification_settings(self, actor: User, organization_id: str) -> TenantNotificationSettings:
        """Retrieves organization-specific notification settings."""
        org, _ = self._resolve_context(actor, organization_id)
        return self.db.get_tenant_notification_settings(org.id)

    def update_notification_settings(
        self,
        actor: User,
        organization_id: str,
        email_enabled: Optional[bool] = None,
        email_recipients: Optional[List[str]] = None,
        email_severities: Optional[List[str]] = None,
        sms_enabled: Optional[bool] = None,
        sms_recipients: Optional[List[str]] = None,
        sms_severities: Optional[List[str]] = None,
        smtp_host: Optional[str] = None,
        smtp_port: Optional[int] = None,
        smtp_username: Optional[str] = None,
        smtp_password: Optional[str] = None,
        smtp_use_tls: Optional[bool] = None,
        email_sender: Optional[str] = None
    ) -> TenantNotificationSettings:
        """Updates notification settings for the organization (ORG_ADMIN only)."""
        org, _ = self._require_org_admin(actor, organization_id, "modify notification settings")

        clean_recipients = [r.strip().lower() for r in (email_recipients or []) if "@" in r]

        updated = self.db.update_tenant_notification_settings(
            organization_id=org.id,
            email_enabled=email_enabled,
            email_recipients=clean_recipients,
            email_severities=email_severities,
            sms_enabled=sms_enabled,
            sms_recipients=sms_recipients,
            sms_severities=sms_severities,
            smtp_host=smtp_host,
            smtp_port=smtp_port,
            smtp_username=smtp_username,
            smtp_password=smtp_password,
            smtp_use_tls=smtp_use_tls,
            email_sender=email_sender
        )

        # Audit event
        event_id = f"aud_{uuid.uuid4().hex[:12]}"
        self.db.create_audit_event(
            event_id=event_id,
            organization_id=org.id,
            actor_user_id=actor.id,
            action="NOTIFICATION_SETTINGS_UPDATED",
            target_type="NOTIFICATION_SETTINGS",
            target_id=org.id,
            metadata={"email_recipients_count": len(clean_recipients)}
        )
        return updated

    def get_notification_dispatcher(self, actor: User, organization_id: str, autostart: bool = True):
        """
        Builds and returns an asynchronous NotificationDispatcher configured strictly
        for the target organization's recipient lists and severity routing rules.
        """
        settings = self.get_notification_settings(actor=actor, organization_id=organization_id)
        from src.notification_dispatcher import NotificationConfig, NotificationDispatcher
        config = NotificationConfig.from_tenant_settings(settings)
        return NotificationDispatcher(config=config, autostart_worker=autostart)
