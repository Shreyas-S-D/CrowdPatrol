"""
CrowdPatrol 2.0 — Phase 2B.4 End-to-End Operational Integration Tests
Validates complete integration between tenant-scoped workspaces and the CrowdPatrol AI pipeline:
1. Tenant camera configs -> MultiCameraManager
2. Camera start/stop & cleanup
3. CCTV Grid & Focus Feed frame generation
4. Person & Head Mode thresholds (0.35 / 0.25) & 640x640 imgsz
5. AlertManager events -> tenant alert storage
6. ACTIVE -> ACKNOWLEDGED -> RESOLVED alert lifecycle
7. Tenant analytics and trend aggregation
8. Uploaded video storage & AI pipeline execution
9. Mocked SMTP email delivery for HIGH/CRITICAL alerts
10. Cross-tenant isolation boundaries
11. VIEWER strictly read-only
12. Resource cleanup & device unlocking on shutdown/exceptions
"""

import os
import shutil
import tempfile
import time
import unittest.mock as mock
from datetime import datetime, timezone
from pathlib import Path
import cv2
import numpy as np
import pytest

from src.auth.database import AuthDatabase, User, Organization, OrganizationMembership
from src.auth.service import AuthService
from src.auth.organization_service import OrganizationService, MembershipService
from src.auth.tenant_operational_service import TenantOperationalService
from src.resource_manager import get_device_registry, get_compute_scheduler, PhysicalDeviceRegistry, ComputeScheduler
from src.multi_camera_manager import MultiCameraManager, CameraState
from src.alert_manager import AlertManager, AlertEvent
from src.detection import PersonDetector
from src.experimental_head_mode import ExperimentalHeadDetector
from src.notification_dispatcher import NotificationConfig, NotificationDispatcher


def create_synthetic_test_video(file_path: Path, num_frames: int = 10, width: int = 640, height: int = 480) -> Path:
    """Generates a small deterministic MP4 test video for pipeline verification."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(str(file_path), fourcc, 30.0, (width, height))
    for i in range(num_frames):
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        # Draw moving circle to simulate motion
        cv2.circle(frame, (100 + i * 15, 120 + i * 5), 25, (255, 255, 255), -1)
        out.write(frame)
    out.release()
    return file_path


@pytest.fixture
def test_env():
    """Sets up an isolated database, directories, and test services."""
    tmp_dir = tempfile.mkdtemp(prefix="cp_test_p2b4_")
    db_path = Path(tmp_dir) / "test_auth.db"
    db = AuthDatabase(db_path=db_path)
    auth_service = AuthService(db)
    org_service = OrganizationService(db)
    member_service = MembershipService(db)

    # Use clean isolated registries
    dev_reg = PhysicalDeviceRegistry()
    scheduler = ComputeScheduler(max_concurrent_sessions=4)
    tenant_op = TenantOperationalService(db, device_registry=dev_reg, compute_scheduler=scheduler)

    # Provision platform admin and org
    p_admin = auth_service.register_user("p_admin", "admin@platform.org", "AdminPass123!", role="PLATFORM_ADMIN")
    org = org_service.create_organization(name="Acme Security", slug="acme-sec", description="Test Organization", actor=p_admin)

    # Provision Operator and Viewer
    op_user = auth_service.register_user("operator_1", "operator@acme.org", "OperatorPass123!", role="USER")
    member_service.add_member(org_id=org.id, actor=p_admin, user_id=op_user.id, role="OPERATOR")

    viewer_user = auth_service.register_user("viewer_1", "viewer@acme.org", "ViewerPass123!", role="USER")
    member_service.add_member(org_id=org.id, actor=p_admin, user_id=viewer_user.id, role="VIEWER")

    # Initialize default camera slots
    tenant_op.get_camera_configs(p_admin, org.id)

    yield {
        "tmp_dir": tmp_dir,
        "db": db,
        "auth_service": auth_service,
        "org_service": org_service,
        "member_service": member_service,
        "tenant_op": tenant_op,
        "p_admin": p_admin,
        "op_user": op_user,
        "viewer_user": viewer_user,
        "org": org,
        "dev_reg": dev_reg,
        "scheduler": scheduler
    }

    shutil.rmtree(tmp_dir, ignore_errors=True)


# ==============================================================================
# TEST 1: Tenant Camera Configs -> MultiCameraManager Connection
# ==============================================================================

def test_tenant_camera_config_connected_to_multi_camera_manager(test_env):
    """Verifies tenant-specific slot configurations properly initialize and run in MultiCameraManager."""
    tenant_op = test_env["tenant_op"]
    op_user = test_env["op_user"]
    org = test_env["org"]
    tmp_dir = Path(test_env["tmp_dir"])

    # Create synthetic video for CAM-01
    video_path = create_synthetic_test_video(tmp_dir / "cam01_test.mp4", num_frames=5)

    # Reconfigure CAM-01 to use video
    tenant_op.update_camera_config(
        actor=op_user,
        organization_id=org.id,
        slot_id="CAM-01",
        name="Main Entrance Gate",
        source_type="video",
        source=str(video_path),
        enabled=True,
        detection_mode="PERSON"
    )

    # Start session
    sess, _ = tenant_op.start_monitoring_session(actor=op_user, organization_id=org.id)
    configs = tenant_op.get_camera_configs(actor=op_user, organization_id=org.id)

    mc = MultiCameraManager(
        camera_configs=configs,
        detection_mode="PERSON",
        device="cpu",
        detect_interval=1,
        organization_id=org.id,
        session_id=sess.id,
        tenant_op_service=tenant_op
    )

    opened = mc.start_all_cameras()
    assert opened >= 1
    assert "CAM-01" in mc.cameras
    cam1 = mc.cameras["CAM-01"]
    assert cam1.status == "ONLINE"
    assert cam1.source_type == "video"
    assert cam1.name == "Main Entrance Gate"
    assert cam1.organization_id == org.id
    assert cam1.session_id == sess.id

    # Step frame and verify annotated frame is produced
    ret = mc.step_camera("CAM-01")
    assert ret is not None
    assert cam1.annotated_frame is not None
    assert cam1.annotated_frame.shape == (480, 640, 3)

    mc.stop_all_cameras()
    tenant_op.stop_monitoring_session(actor=op_user, organization_id=org.id, session_id=sess.id)


# ==============================================================================
# TEST 2: Detection Mode Thresholds & 640x640 Input Preservation
# ==============================================================================

def test_detection_mode_thresholds_and_640_imgsz(test_env):
    """Verifies Person Mode and Head Mode preserve existing detection thresholds and 640x640 input."""
    # Test PersonDetector
    p_detector = PersonDetector(confidence=0.35, imgsz=640)
    assert p_detector.confidence == 0.35
    assert p_detector.imgsz == 640

    # Test ExperimentalHeadDetector
    h_detector = ExperimentalHeadDetector(confidence=0.25, imgsz=640)
    assert h_detector.confidence == 0.25
    assert h_detector.imgsz == 640

    # Test MultiCameraManager detection mode switching
    configs = test_env["tenant_op"].get_camera_configs(test_env["op_user"], test_env["org"].id)
    mc = MultiCameraManager(
        camera_configs=configs,
        detection_mode="PERSON",
        device="cpu",
        yolo_imgsz=640
    )
    assert mc.detection_mode == "PERSON"
    assert isinstance(mc.shared_detector, PersonDetector)
    assert mc.shared_detector.confidence == 0.35
    assert mc.shared_detector.imgsz == 640

    # Switch to Head Mode
    mc.set_detection_mode("HEAD")
    assert mc.detection_mode == "HEAD"
    assert isinstance(mc.shared_detector, ExperimentalHeadDetector)
    assert mc.shared_detector.confidence == 0.25
    assert mc.shared_detector.imgsz == 640


# ==============================================================================
# TEST 3: CCTV Grid and Focus Feed Frame Stepping
# ==============================================================================

def test_cctv_grid_and_focus_feed_stepping(test_env):
    """Verifies stepping all feeds in 2x2 grid and detailed focus feed inspection."""
    tenant_op = test_env["tenant_op"]
    op_user = test_env["op_user"]
    org = test_env["org"]
    tmp_dir = Path(test_env["tmp_dir"])

    # Setup 4 synthetic videos
    for i in range(1, 5):
        slot = f"CAM-0{i}"
        v_path = create_synthetic_test_video(tmp_dir / f"{slot}.mp4", num_frames=6)
        tenant_op.update_camera_config(
            actor=op_user,
            organization_id=org.id,
            slot_id=slot,
            name=f"Slot {slot}",
            source_type="video",
            source=str(v_path),
            enabled=True
        )

    sess, _ = tenant_op.start_monitoring_session(actor=op_user, organization_id=org.id)
    configs = tenant_op.get_camera_configs(actor=op_user, organization_id=org.id)

    mc = MultiCameraManager(
        camera_configs=configs,
        detection_mode="PERSON",
        device="cpu",
        organization_id=org.id,
        session_id=sess.id,
        tenant_op_service=tenant_op
    )
    mc.start_all_cameras()

    # 1. Step all (2x2 grid)
    grid_frames = mc.step_all()
    assert len(grid_frames) == 4
    for slot_id in ["CAM-01", "CAM-02", "CAM-03", "CAM-04"]:
        assert slot_id in grid_frames
        assert grid_frames[slot_id] is not None
        assert mc.cameras[slot_id].annotated_frame is not None

    # 2. Step Focus Feed on CAM-02
    focus_frames = mc.step_focus("CAM-02", step_background=True)
    assert len(focus_frames) >= 1
    assert "CAM-02" in focus_frames
    assert mc.cameras["CAM-02"].annotated_frame is not None

    mc.stop_all_cameras()
    tenant_op.stop_monitoring_session(actor=op_user, organization_id=org.id, session_id=sess.id)


# ==============================================================================
# TEST 4: AlertManager -> Tenant Scoped Alert Storage Integration
# ==============================================================================

def test_alert_manager_to_tenant_scoped_storage_integration(test_env):
    """Verifies AlertManager automatically syncs newly triggered alerts to tenant_alerts table."""
    tenant_op = test_env["tenant_op"]
    op_user = test_env["op_user"]
    org = test_env["org"]

    sess, _ = tenant_op.start_monitoring_session(actor=op_user, organization_id=org.id)

    # Initialize AlertManager with tenant_op_service bound
    alert_mgr = AlertManager(
        organization_id=org.id,
        session_id=sess.id,
        tenant_op_service=tenant_op,
        cooldown_seconds=1.0
    )

    # Process telemetry simulating critical crowd surge
    telemetry = {
        "severity": "HIGH",
        "risk_level": "HIGH",
        "category": "CROWD_SURGE",
        "risk_score": 88.5,
        "max_density": 35,
        "density": 35,
        "person_count": 65,
        "avg_speed": 3.2,
        "anomaly_score": 0.72,
        "primary_risk_zone": "B2",
        "primary_zone_density": 35,
        "zone_description": "Upper-Center",
        "reason": "Sudden Crowd Surge (+3.5 p/s)"
    }

    event = alert_mgr.process_camera_telemetry("CAM-01", "Main Sidewalk", telemetry)
    assert event is not None
    assert event.alert_id.startswith("ALT_")
    assert event.risk_level == "HIGH"

    # Query tenant_alerts table directly via tenant_op_service
    tenant_alerts = tenant_op.list_alerts(actor=op_user, organization_id=org.id, status="ACTIVE")
    assert len(tenant_alerts) >= 1
    stored = next((a for a in tenant_alerts if a.id == event.alert_id), None)
    assert stored is not None
    assert stored.camera_id == "CAM-01"
    assert stored.organization_id == org.id
    assert stored.session_id == sess.id
    assert stored.risk_score == 88.5
    assert stored.status == "ACTIVE"
    assert stored.primary_risk_zone == "B2"


# ==============================================================================
# TEST 5: ACTIVE -> ACKNOWLEDGED -> RESOLVED Lifecycle Transitions
# ==============================================================================

def test_active_acknowledged_resolved_lifecycle(test_env):
    """Verifies complete state machine transitions from ACTIVE to ACKNOWLEDGED to RESOLVED."""
    tenant_op = test_env["tenant_op"]
    op_user = test_env["op_user"]
    org = test_env["org"]

    sess, _ = tenant_op.start_monitoring_session(actor=op_user, organization_id=org.id)
    alert = tenant_op.record_alert(
        organization_id=org.id,
        session_id=sess.id,
        camera_id="CAM-01",
        camera_name="Main Gate",
        risk_level="HIGH",
        risk_score=75.0,
        severity="HIGH",
        category="CROWD_DENSITY",
        reason="Elevated Crowd Density",
        crowd_density=25,
        person_count=40,
        primary_risk_zone="A1"
    )
    assert alert.status == "ACTIVE"
    assert alert.acknowledged is False

    # 1. Acknowledge
    acked = tenant_op.acknowledge_alert(actor=op_user, organization_id=org.id, alert_id=alert.id)
    assert acked.status == "ACKNOWLEDGED"
    assert acked.acknowledged is True
    assert acked.acknowledged_by == op_user.id
    assert acked.acknowledged_at is not None

    # 2. Resolve
    resolved = tenant_op.resolve_alert(
        actor=op_user,
        organization_id=org.id,
        alert_id=alert.id,
        note="Crowd dispersed after security intervention"
    )
    assert resolved.status == "RESOLVED"
    assert resolved.resolved_by == op_user.id
    assert resolved.resolved_at is not None
    assert resolved.details.get("resolution_note") == "Crowd dispersed after security intervention"

    # Verify active list no longer includes this alert
    active_now = tenant_op.list_alerts(actor=op_user, organization_id=org.id, status="ACTIVE")
    assert not any(a.id == alert.id for a in active_now)


# ==============================================================================
# TEST 6: Analytics & Trend Aggregation Connected to Tenant Data
# ==============================================================================

def test_analytics_and_trends_connected_to_tenant_data(test_env):
    """Verifies analytics summary accurately aggregates active, acked, and resolved metrics per organization."""
    tenant_op = test_env["tenant_op"]
    op_user = test_env["op_user"]
    org = test_env["org"]

    sess, _ = tenant_op.start_monitoring_session(actor=op_user, organization_id=org.id)

    # Create 3 alerts with varying severities and states
    a1 = tenant_op.record_alert(
        organization_id=org.id, session_id=sess.id, camera_id="CAM-01", camera_name="Entrance",
        risk_level="CRITICAL", risk_score=95.0, severity="CRITICAL", category="SURGE", reason="Stampede risk"
    )
    a2 = tenant_op.record_alert(
        organization_id=org.id, session_id=sess.id, camera_id="CAM-02", camera_name="Overhead",
        risk_level="HIGH", risk_score=80.0, severity="HIGH", category="DENSITY", reason="High density"
    )
    a3 = tenant_op.record_alert(
        organization_id=org.id, session_id=sess.id, camera_id="CAM-01", camera_name="Entrance",
        risk_level="MEDIUM", risk_score=55.0, severity="MEDIUM", category="MOTION", reason="Elevated motion"
    )

    tenant_op.acknowledge_alert(actor=op_user, organization_id=org.id, alert_id=a1.id)
    tenant_op.resolve_alert(actor=op_user, organization_id=org.id, alert_id=a3.id, note="Resolved")

    # Fetch analytics
    summary = tenant_op.get_analytics_summary(actor=op_user, organization_id=org.id)
    counts = summary["alert_counts"]

    assert counts["total"] == 3
    assert counts["active"] == 1  # a2 is still ACTIVE
    assert counts["acknowledged"] == 1  # a1 is ACKNOWLEDGED
    assert counts["resolved"] == 1  # a3 is RESOLVED
    assert counts["critical"] == 1
    assert counts["high"] == 1
    assert counts["medium"] == 1

    # Camera distribution
    cam_dist = summary["camera_alert_distribution"]
    assert cam_dist["CAM-01"] == 2
    assert cam_dist["CAM-02"] == 1


# ==============================================================================
# TEST 7: Uploaded Video Storage & AI Pipeline Execution
# ==============================================================================

def test_uploaded_video_processed_through_ai_pipeline(test_env):
    """Verifies uploaded video is stored under tenant directory and processed by MultiCameraManager."""
    tenant_op = test_env["tenant_op"]
    op_user = test_env["op_user"]
    org = test_env["org"]
    tmp_dir = Path(test_env["tmp_dir"])

    raw_video = create_synthetic_test_video(tmp_dir / "sample_upload.mp4", num_frames=8)
    with open(raw_video, "rb") as f:
        file_bytes = f.read()

    asset = tenant_op.save_uploaded_video(
        actor=op_user,
        organization_id=org.id,
        file_bytes=file_bytes,
        original_filename="security_clip.mp4",
        slot_id="CAM-03"
    )

    assert "data" in asset.storage_path and "tenants" in asset.storage_path
    assert Path(asset.storage_path).exists()

    # Assign asset to CAM-03
    tenant_op.update_camera_config(
        actor=op_user,
        organization_id=org.id,
        slot_id="CAM-03",
        name="Plaza Surveillance",
        source_type="video",
        source=asset.storage_path,
        enabled=True
    )

    sess, _ = tenant_op.start_monitoring_session(actor=op_user, organization_id=org.id)
    configs = tenant_op.get_camera_configs(actor=op_user, organization_id=org.id)

    mc = MultiCameraManager(
        camera_configs=configs,
        detection_mode="PERSON",
        device="cpu",
        organization_id=org.id,
        session_id=sess.id
    )
    mc.start_all_cameras()

    # Step CAM-03
    ret = mc.step_camera("CAM-03")
    assert ret is not None
    assert mc.cameras["CAM-03"].status == "ONLINE"
    assert mc.cameras["CAM-03"].annotated_frame is not None

    mc.stop_all_cameras()
    tenant_op.stop_monitoring_session(actor=op_user, organization_id=org.id, session_id=sess.id)


# ==============================================================================
# TEST 8: Mocked SMTP Email Delivery for HIGH & CRITICAL Alerts
# ==============================================================================

def test_notification_settings_and_mocked_smtp_email_delivery(test_env):
    """Verifies tenant notification settings route HIGH/CRITICAL alerts via SMTP with mocked transport."""
    tenant_op = test_env["tenant_op"]
    p_admin = test_env["p_admin"]
    op_user = test_env["op_user"]
    org = test_env["org"]

    # Configure tenant notification settings
    tenant_op.update_notification_settings(
        actor=p_admin,
        organization_id=org.id,
        email_enabled=True,
        email_recipients=["sec_lead@acme.org"],
        email_severities=["HIGH", "CRITICAL"],
        smtp_host="smtp.gmail.com",
        smtp_port=587,
        smtp_username="alerts@acme.org",
        smtp_password="AppPassword123!",
        email_sender="alerts@acme.org"
    )

    dispatcher = tenant_op.get_notification_dispatcher(actor=op_user, organization_id=org.id, autostart=False)
    assert dispatcher.config.is_email_configured is True
    assert "sec_lead@acme.org" in dispatcher.config.email_recipients
    assert "HIGH" in dispatcher.config.email_severities

    alert = AlertEvent(
        alert_id="ALT_TEST_HIGH_01",
        camera_id="CAM-01",
        camera_name="Main Gate",
        timestamp=datetime.now(timezone.utc).isoformat(),
        risk_level="HIGH",
        risk_score=85.0,
        reason="Rapid Crowd Surge",
        status="ACTIVE",
        primary_risk_zone="A2",
        primary_zone_density=28,
        zone_description="Top/Left-Center",
        severity="HIGH",
        category="CROWD_SURGE",
        crowd_density=28,
        person_count=52,
        organization_id=org.id
    )

    with mock.patch("smtplib.SMTP") as mock_smtp_cls:
        mock_server = mock.MagicMock()
        mock_smtp_cls.return_value = mock_server

        from src.notification_dispatcher import format_alert_email_html, format_alert_email_text
        html_body = format_alert_email_html(alert)
        text_body = format_alert_email_text(alert)
        # Dispatch synchronously for testing
        success = dispatcher.email_service.send_email(
            subject=f"[CROWDPATROL {alert.severity} ALERT] {alert.camera_id}: {alert.reason}",
            html_body=html_body,
            text_body=text_body,
            recipients=["sec_lead@acme.org"]
        )
        assert success is True
        assert mock_server.sendmail.called
        args, kwargs = mock_server.sendmail.call_args
        sender, recipients, msg_str = args
        assert sender == "alerts@acme.org"
        assert "sec_lead@acme.org" in recipients
        assert "CAM-01" in msg_str

        # Decode MIME multipart body to verify content
        import email
        parsed_email = email.message_from_string(msg_str)
        assert parsed_email["Subject"].startswith("[CROWDPATROL HIGH ALERT]")
        decoded_payloads = [part.get_payload(decode=True).decode("utf-8") for part in parsed_email.get_payload()]
        combined_body = "\n".join(decoded_payloads)
        assert "ALT_TEST_HIGH_01" in combined_body
        assert "CAM-01" in combined_body
        assert "Rapid Crowd Surge" in combined_body


# ==============================================================================
# TEST 9: Cross-Tenant Isolation Enforcement
# ==============================================================================

def test_cross_tenant_isolation_boundary(test_env):
    """Verifies switching organizations strictly isolates feeds, alerts, sessions, and files."""
    tenant_op = test_env["tenant_op"]
    org_service = test_env["org_service"]
    member_service = test_env["member_service"]
    auth_service = test_env["auth_service"]
    p_admin = test_env["p_admin"]
    op_user = test_env["op_user"]
    org1 = test_env["org"]

    # Create Org 2
    org2 = org_service.create_organization(name="Beta Campus", slug="beta-campus", description="Second Tenant", actor=p_admin)
    tenant_op.get_camera_configs(p_admin, org2.id)

    # op_user belongs ONLY to org1, NOT org2
    with pytest.raises(PermissionError, match="is not an active member"):
        tenant_op.get_camera_configs(actor=op_user, organization_id=org2.id)

    with pytest.raises(PermissionError, match="is not an active member"):
        tenant_op.start_monitoring_session(actor=op_user, organization_id=org2.id)

    with pytest.raises(PermissionError, match="is not an active member"):
        tenant_op.list_alerts(actor=op_user, organization_id=org2.id)

    with pytest.raises(PermissionError, match="is not an active member"):
        tenant_op.get_analytics_summary(actor=op_user, organization_id=org2.id)

    with pytest.raises(PermissionError, match="is not an active member"):
        tenant_op.list_uploaded_assets(actor=op_user, organization_id=org2.id)


# ==============================================================================
# TEST 10: VIEWER Role Strictly Read-Only
# ==============================================================================

def test_viewer_role_operational_restrictions(test_env):
    """Verifies that VIEWER role is strictly prohibited from executing mutating actions."""
    tenant_op = test_env["tenant_op"]
    viewer = test_env["viewer_user"]
    org = test_env["org"]

    # VIEWER cannot start monitoring
    with pytest.raises(PermissionError, match="read-only access and cannot"):
        tenant_op.start_monitoring_session(actor=viewer, organization_id=org.id)

    # VIEWER cannot update camera configs
    with pytest.raises(PermissionError, match="read-only access and cannot"):
        tenant_op.update_camera_config(actor=viewer, organization_id=org.id, slot_id="CAM-01", name="X", source_type="video", source="x.mp4")

    # VIEWER cannot acknowledge or resolve alerts
    p_admin = test_env["p_admin"]
    sess, _ = tenant_op.start_monitoring_session(actor=p_admin, organization_id=org.id)
    alt = tenant_op.record_alert(org.id, sess.id, "CAM-01", "Gate", "HIGH", 80.0, "HIGH", "DENSITY", "High Risk")

    with pytest.raises(PermissionError, match="read-only access and cannot"):
        tenant_op.acknowledge_alert(actor=viewer, organization_id=org.id, alert_id=alt.id)

    with pytest.raises(PermissionError, match="read-only access and cannot"):
        tenant_op.resolve_alert(actor=viewer, organization_id=org.id, alert_id=alt.id)

    # VIEWER cannot upload files
    with pytest.raises(PermissionError, match="read-only access and cannot"):
        tenant_op.save_uploaded_video(actor=viewer, organization_id=org.id, file_bytes=b"test", original_filename="v.mp4")

    # VIEWER CAN read configs and view alerts
    configs = tenant_op.get_camera_configs(actor=viewer, organization_id=org.id)
    assert len(configs) == 4
    alerts = tenant_op.list_alerts(actor=viewer, organization_id=org.id)
    assert len(alerts) >= 1

    tenant_op.stop_monitoring_session(actor=p_admin, organization_id=org.id, session_id=sess.id)


# ==============================================================================
# TEST 11: Monitoring Shutdown & Exception Resource Cleanup
# ==============================================================================

def test_monitoring_shutdown_and_exception_resource_cleanup(test_env):
    """Verifies device locks and compute capacity are unconditionally freed even if exceptions occur."""
    tenant_op = test_env["tenant_op"]
    dev_reg = test_env["dev_reg"]
    scheduler = test_env["scheduler"]
    op_user = test_env["op_user"]
    org = test_env["org"]

    # Configure CAM-01 to webcam device index 0
    tenant_op.update_camera_config(
        actor=op_user,
        organization_id=org.id,
        slot_id="CAM-01",
        name="Webcam Slot",
        source_type="webcam",
        source="0",
        enabled=True
    )

    sess, _ = tenant_op.start_monitoring_session(actor=op_user, organization_id=org.id)
    assert dev_reg.get_device_status("webcam_0")["locked"] is True
    assert scheduler.get_active_session_count() == 1

    # 1. Normal stop
    tenant_op.stop_monitoring_session(actor=op_user, organization_id=org.id, session_id=sess.id)
    assert dev_reg.get_device_status("webcam_0")["locked"] is False
    assert scheduler.get_active_session_count() == 0

    # 2. Simulate exception during monitoring
    sess2, _ = tenant_op.start_monitoring_session(actor=op_user, organization_id=org.id)
    assert dev_reg.get_device_status("webcam_0")["locked"] is True
    assert scheduler.get_active_session_count() == 1

    configs = tenant_op.get_camera_configs(actor=op_user, organization_id=org.id)
    mc = MultiCameraManager(
        camera_configs=configs,
        organization_id=org.id,
        session_id=sess2.id,
        tenant_op_service=tenant_op
    )

    try:
        raise RuntimeError("Simulated unhandled runtime failure in pipeline")
    except RuntimeError:
        pass
    finally:
        # Cleanup block executed on exception
        mc.stop_all_cameras()
        tenant_op.stop_monitoring_session(actor=op_user, organization_id=org.id, session_id=sess2.id)

    assert dev_reg.get_device_status("webcam_0")["locked"] is False
    assert scheduler.get_active_session_count() == 0


# ==============================================================================
# TEST 12: Streamlit AppTest Headless Integration
# ==============================================================================

def test_workspace_ui_cctv_grid_and_focus_feed_apptest():
    """Verifies that the Streamlit application initializes headlessly with the integrated workspace."""
    from streamlit.testing.v1 import AppTest
    dash_path = str(Path(__file__).parent.parent / "dashboard" / "simple_dashboard.py")
    at = AppTest.from_file(dash_path)
    at.run(timeout=30)
    assert len(at.exception) == 0
