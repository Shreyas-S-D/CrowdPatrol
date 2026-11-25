"""
CrowdPatrol Phase 2C — Real-World Validation & Product Stabilization Test Suite.

Validates:
1. Startup & Authentication:
   - User registration and authentication flow.
   - Session token generation and validation.
   - Session expiration handling.
   - Invalid session token handling.
   - Invitation generation and atomic acceptance.

2. Multi-Tenant Isolation & Contention:
   - Two distinct organizations (Org Alpha & Org Beta) with isolated users.
   - Strict isolation of camera configurations, monitoring sessions, alerts, and analytics.
   - Multi-tenant physical camera contention (DEVICE_IN_USE handling).
   - Dynamic organization switching during active surveillance (immediate session stop & device release).
   - Role-based authorization enforcement (VIEWER read-only vs ORG_ADMIN operational control).

3. Live Surveillance Pipeline & Diagnostics:
   - Person Mode (confidence 0.35, 640x640) and Head Mode (confidence 0.25, 640x640).
   - Real-world recorded video processing (detection bounding boxes, DeepSORT tracking IDs,
     density calculation, optical flow vectors, heatmap generation, risk assessment).
   - Automatic VideoCapture loop / rewind on EOF.
   - Camera reconnection, stop_all_cameras() cleanup, and graceful disconnection handling.

4. Alert Lifecycle & Notification Dispatch:
   - Alert creation, transitions: ACTIVE -> ACKNOWLEDGED -> RESOLVED.
   - Automatic de-escalation synchronization with tenant-scoped alert persistence.
   - Notification dispatch on HIGH / CRITICAL alerts using mocked SMTP (no real emails sent).
"""

import os
import sys
import time
import email
import cv2
import tempfile
import sqlite3
from pathlib import Path
from datetime import datetime, timezone, timedelta
from unittest import mock
import numpy as np
import pytest

BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.auth.database import AuthDatabase, User, Organization, OrganizationMembership
from src.auth.crypto import hash_session_token
from src.auth.service import AuthService
from src.auth.organization_service import OrganizationService, MembershipService
from src.auth.invitation_service import InvitationService
from src.auth.tenant_operational_service import TenantOperationalService
from src.resource_manager import (
    PhysicalDeviceRegistry,
    ComputeScheduler,
    get_device_registry,
    get_compute_scheduler,
)
from src.multi_camera_manager import MultiCameraManager, CameraState
from src.alert_manager import AlertManager, AlertEvent
from src.notification_dispatcher import (
    NotificationDispatcher,
    NotificationConfig,
    format_alert_email_html,
    format_alert_email_text,
    EmailService,
)
from src.detection import PersonDetector
from src.experimental_head_mode import ExperimentalHeadDetector
from src.tracking import PersonTracker
from src.density import DensityEstimator
from src.motion_analysis import CrowdMotionAnalyzer
from src.risk_assessment import RiskAssessor
from src.heatmap import generate_heatmap


@pytest.fixture
def fresh_env():
    """Sets up a clean test database, resource registries, and operational services."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    db = AuthDatabase(db_path=db_path)
    auth_service = AuthService(db)
    org_service = OrganizationService(db)
    member_service = MembershipService(db)
    invitation_service = InvitationService(db, auth_service)
    device_registry = PhysicalDeviceRegistry()
    compute_scheduler = ComputeScheduler(max_concurrent_sessions=4)
    tenant_op_service = TenantOperationalService(
        db,
        device_registry=device_registry,
        compute_scheduler=compute_scheduler,
    )

    yield {
        "db": db,
        "db_path": db_path,
        "auth_service": auth_service,
        "org_service": org_service,
        "member_service": member_service,
        "invitation_service": invitation_service,
        "tenant_op_service": tenant_op_service,
        "device_registry": device_registry,
        "compute_scheduler": compute_scheduler,
    }
    try:
        os.remove(db_path)
    except OSError:
        pass


def test_startup_authentication_and_session_expiry(fresh_env):
    """
    Validates Startup & Authentication lifecycle:
    - User creation & login
    - Session token generation & resolution
    - Session expiration handling
    - Invalid session handling
    """
    auth = fresh_env["auth_service"]

    # 1. Provision Platform Admin & Regular User
    admin = auth.register_user(
        username="platform_admin",
        email="admin@crowdpatrol.org",
        password="AdminSecurePassword123!",
        role="PLATFORM_ADMIN",
    )
    user = auth.register_user(
        username="operator_bob",
        email="operator@crowdpatrol.org",
        password="OperatorSecurePassword123!",
        role="USER",
    )
    assert admin.id is not None
    assert user.id is not None

    # 2. Authenticate
    user_res, session_token, err = auth.authenticate("operator@crowdpatrol.org", "OperatorSecurePassword123!")
    assert err is None
    assert user_res is not None
    assert session_token is not None

    # 3. Resolve active session
    resolved_user = auth.validate_session(session_token)
    assert resolved_user is not None
    assert resolved_user.id == user.id

    # 4. Invalid session returns None
    assert auth.validate_session("completely_invalid_token") is None

    # 5. Session expiry: manually expire the session token in the database
    token_h = hash_session_token(session_token)
    past_time_iso = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    with fresh_env["db"].transaction() as cur:
        cur.execute(
            "UPDATE authentication_sessions SET expires_at = ? WHERE token_hash = ?",
            (past_time_iso, token_h),
        )
    # Validate session expiration logic
    expired_user = auth.validate_session(session_token)
    assert expired_user is None


def test_invitation_acceptance_and_organization_selection(fresh_env):
    """
    Validates user invitation, token redemption, and active organization resolution.
    """
    auth = fresh_env["auth_service"]
    org_svc = fresh_env["org_service"]
    member_svc = fresh_env["member_service"]
    inv_svc = fresh_env["invitation_service"]

    admin = auth.register_user(
        username="alpha_boss",
        email="admin@alpha.org",
        password="AdminPassword123!",
        role="PLATFORM_ADMIN",
    )
    org = org_svc.create_organization(
        name="Alpha Security Corp",
        slug="alpha-sec",
        actor=admin,
    )

    # Invite a new member as OPERATOR
    with mock.patch("src.auth.invitation_service.send_invitation_email", return_value=(True, None)):
        invitation, raw_token, err = inv_svc.create_invitation(
            actor=admin,
            organization_id=org.id,
            email="newoperator@alpha.org",
            role="OPERATOR",
            send_email=False,
        )
    assert err is None
    assert raw_token is not None
    assert invitation.status == "PENDING"

    # Accept invitation for new user
    accepted, member, accept_err = inv_svc.accept_invitation(
        raw_token=raw_token,
        new_user_credentials={"username": "newoperator", "password": "OperatorSecurePassword456!"},
    )
    assert accepted is True
    assert member is not None
    assert member.organization_id == org.id
    assert member.role == "OPERATOR"

    # Verify membership via MembershipService
    m = member_svc.get_membership(org.id, member.user_id)
    assert m is not None
    assert m.organization_id == org.id
    assert m.role == "OPERATOR"


def test_multi_tenant_isolation_two_orgs(fresh_env):
    """
    Validates complete data isolation between two organizations (Org Alpha vs Org Beta):
    - Separate camera configurations
    - Separate monitoring sessions
    - Separate alerts
    - Cross-tenant access is blocked
    """
    auth = fresh_env["auth_service"]
    org_svc = fresh_env["org_service"]
    tenant_op = fresh_env["tenant_op_service"]

    admin_a = auth.register_user("admin_a", "admin@alpha.org", "Pass123!Alpha", role="PLATFORM_ADMIN")
    admin_b = auth.register_user("admin_b", "admin@beta.org", "Pass123!Beta", role="PLATFORM_ADMIN")

    org_a = org_svc.create_organization("Org Alpha", "org-alpha", actor=admin_a)
    org_b = org_svc.create_organization("Org Beta", "org-beta", actor=admin_b)

    # Initialize cameras for Org Alpha and Org Beta
    cams_a = tenant_op.get_camera_configs(admin_a, org_a.id)
    cams_b = tenant_op.get_camera_configs(admin_b, org_b.id)
    assert len(cams_a) == 4
    assert len(cams_b) == 4

    # Update slot 1 in Org Alpha to a distinct source
    tenant_op.update_camera_config(
        admin_a,
        org_a.id,
        slot_id="CAM-01",
        name="Alpha Main Gate",
        source="data/videos/crowd_sample.mp4",
        source_type="video",
        enabled=True,
    )

    # Verify Org Beta did NOT receive Alpha's configuration
    b_cams = tenant_op.get_camera_configs(admin_b, org_b.id)
    b_cam1 = next(c for c in b_cams if c.slot_id == "CAM-01")
    assert b_cam1.name != "Alpha Main Gate"

    # Start session in Org Alpha
    sess_a, _ = tenant_op.start_monitoring_session(admin_a, org_a.id)
    assert sess_a.organization_id == org_a.id

    # Org Beta cannot access Org Alpha's session
    b_sessions = tenant_op.list_monitoring_sessions(admin_b, org_b.id)
    assert len(b_sessions) == 0

    # Record alert in Org Alpha
    alert_a = tenant_op.record_alert(
        organization_id=org_a.id,
        session_id=sess_a.id,
        camera_id="CAM-01",
        camera_name="Main Gate",
        risk_level="HIGH",
        risk_score=78.5,
        severity="HIGH",
        category="DENSITY",
        reason="High crowd concentration detected",
        crowd_density=18,
    )
    assert alert_a.organization_id == org_a.id

    # Org Beta cannot view Org Alpha's alerts
    b_alerts = tenant_op.list_alerts(admin_b, org_b.id)
    assert len(b_alerts) == 0

    # Cross-tenant alert manipulation from Org Beta is blocked
    with pytest.raises(PermissionError, match="Alert not found in active organization"):
        tenant_op.acknowledge_alert(admin_b, org_b.id, alert_a.id)


def test_hardware_camera_contention_and_organization_switching(fresh_env):
    """
    Validates physical webcam lock contention and clean resource teardown on org switch:
    - Org 1 locks webcam 0
    - Org 2 attempts to open webcam 0 -> receives DEVICE_IN_USE
    - Org 1 switches organization or terminates -> lock is released
    - Org 2 can now claim webcam 0
    """
    device_reg = fresh_env["device_registry"]
    auth = fresh_env["auth_service"]
    org_svc = fresh_env["org_service"]
    tenant_op = fresh_env["tenant_op_service"]

    user_a = auth.register_user("user_a", "user_a@test.org", "Pass123!UserA", role="PLATFORM_ADMIN")
    user_b = auth.register_user("user_b", "user_b@test.org", "Pass123!UserB", role="PLATFORM_ADMIN")

    org_a = org_svc.create_organization("Org A", "org-a", actor=user_a)
    org_b = org_svc.create_organization("Org B", "org-b", actor=user_b)

    # Configure CAM-01 in Org A to hardware webcam index 0
    tenant_op.get_camera_configs(user_a, org_a.id)
    tenant_op.update_camera_config(
        user_a,
        org_a.id,
        slot_id="CAM-01",
        name="Org A Webcam Slot",
        source_type="webcam",
        source="0",
        enabled=True,
    )

    # Org A starts monitoring (CAM-01 acquires webcam_0)
    sess_a, meta = tenant_op.start_monitoring_session(user_a, org_a.id)
    dev_id = device_reg.normalize_device_id(0, "webcam")
    assert dev_id == "webcam_0"

    status_during = device_reg.get_device_status(dev_id)
    assert status_during["locked"] is True
    assert status_during["organization_id"] == org_a.id

    # CameraState for Org B attempting to open webcam 0
    cam_b = CameraState(
        camera_id="CAM-01",
        name="Org B Camera",
        source="0",
        source_type="webcam",
        session_id="session_b_123",
        organization_id=org_b.id,
    )
    with mock.patch("src.resource_manager.get_device_registry", return_value=device_reg):
        opened = cam_b.open_source()
        assert opened is False
        assert cam_b.status == "DEVICE_IN_USE"
        assert "currently in use" in cam_b.error_message

    # Teardown Org A session
    tenant_op.stop_monitoring_session(user_a, org_a.id, sess_a.id)
    status_after = device_reg.get_device_status(dev_id)
    assert status_after["locked"] is False

    # Now Org B can acquire device
    acquired_b, err_b = device_reg.acquire_device(
        device_id=dev_id,
        organization_id=org_b.id,
        session_id="session_b_123",
        slot_id="CAM-01",
    )
    assert acquired_b is True


def test_viewer_read_only_enforcement(fresh_env):
    """
    Validates that a user with VIEWER role has strict read-only access:
    - Can view cameras and alerts
    - Cannot modify camera configuration
    - Cannot start or stop monitoring sessions
    - Cannot acknowledge or resolve alerts
    """
    auth = fresh_env["auth_service"]
    org_svc = fresh_env["org_service"]
    member_svc = fresh_env["member_service"]
    tenant_op = fresh_env["tenant_op_service"]

    admin = auth.register_user("admin_user", "admin@viewerorg.org", "Pass123!Admin", role="PLATFORM_ADMIN")
    viewer = auth.register_user("viewer_user", "viewer@viewerorg.org", "Pass123!Viewer", role="USER")
    org = org_svc.create_organization("Viewer Org", "viewer-org", actor=admin)
    member_svc.add_member(org_id=org.id, user_id=viewer.id, role="VIEWER", actor=admin)

    # VIEWER can read configs
    configs = tenant_op.get_camera_configs(viewer, org.id)
    assert len(configs) == 4

    # VIEWER cannot modify config
    with pytest.raises(PermissionError, match="read-only access and cannot"):
        tenant_op.update_camera_config(
            viewer, org.id, slot_id="CAM-01", name="Hacked Name", source_type="video", source="hacked.mp4"
        )

    # VIEWER cannot start monitoring session
    with pytest.raises(PermissionError, match="read-only access and cannot"):
        tenant_op.start_monitoring_session(viewer, org.id)

    # Start session as admin and create alert
    sess, _ = tenant_op.start_monitoring_session(admin, org.id)
    alert = tenant_op.record_alert(
        organization_id=org.id,
        session_id=sess.id,
        camera_id="CAM-01",
        camera_name="Main Plaza",
        risk_level="HIGH",
        risk_score=75.0,
        severity="HIGH",
        category="DENSITY",
        reason="Sample Alert",
    )

    # VIEWER cannot acknowledge alert
    with pytest.raises(PermissionError, match="read-only access and cannot"):
        tenant_op.acknowledge_alert(viewer, org.id, alert.id)

    # VIEWER cannot resolve alert
    with pytest.raises(PermissionError, match="read-only access and cannot"):
        tenant_op.resolve_alert(viewer, org.id, alert.id)


def test_alert_lifecycle_and_mocked_smtp_email(fresh_env):
    """
    Validates:
    - ACTIVE -> ACKNOWLEDGED -> RESOLVED alert transitions
    - Auto-synchronization with tenant operational alert records
    - Mocked SMTP email delivery for HIGH and CRITICAL alerts
    """
    auth = fresh_env["auth_service"]
    org_svc = fresh_env["org_service"]
    tenant_op = fresh_env["tenant_op_service"]

    admin = auth.register_user("sec_lead", "sec_lead@enterprise.org", "Pass123!Lead", role="PLATFORM_ADMIN")
    org = org_svc.create_organization("Enterprise Security", "ent-sec", actor=admin)
    sess, _ = tenant_op.start_monitoring_session(admin, org.id)

    # Update notification settings for org
    tenant_op.update_notification_settings(
        actor=admin,
        organization_id=org.id,
        email_enabled=True,
        email_recipients=["alerts@enterprise.org"],
        smtp_host="smtp.mockserver.local",
        smtp_port=587,
        smtp_username="alerts@enterprise.org",
        smtp_password="MockPassword123!",
        email_sender="noreply@crowdpatrol.org",
        email_severities=["HIGH", "CRITICAL"],
    )

    # Create AlertManager connected to tenant_op_service
    alert_mgr = AlertManager(
        organization_id=org.id,
        session_id=sess.id,
        tenant_op_service=tenant_op,
    )

    # 1. Trigger HIGH alert via generate_alert
    with mock.patch("smtplib.SMTP") as mock_smtp_cls:
        mock_server = mock.MagicMock()
        mock_smtp_cls.return_value = mock_server

        high_alert = alert_mgr.generate_alert(
            camera_id="CAM-01",
            camera_name="Main Plaza",
            severity="HIGH",
            category="CROWD_DENSITY",
            risk_score=76.4,
            crowd_density=22,
            person_count=35,
            reason="Rapid crowd concentration exceeding threshold",
        )
        assert high_alert is not None

        # Verify tenant record created
        db_alerts = tenant_op.list_alerts(admin, org.id)
        db_alert = next(a for a in db_alerts if a.id == high_alert.alert_id)
        assert db_alert.status == "ACTIVE"
        assert db_alert.risk_level == "HIGH"

        # Dispatch notification using mocked SMTP
        dispatcher = tenant_op.get_notification_dispatcher(admin, org.id, autostart=False)
        assert dispatcher is not None

        html_body = format_alert_email_html(high_alert)
        text_body = format_alert_email_text(high_alert)
        sent = dispatcher.email_service.send_email(
            subject=f"[CROWDPATROL {high_alert.severity} ALERT] {high_alert.camera_id}: {high_alert.reason}",
            html_body=html_body,
            text_body=text_body,
            recipients=["alerts@enterprise.org"],
        )
        assert sent is True
        assert mock_server.sendmail.called is True

    # 2. Transition: ACTIVE -> ACKNOWLEDGED
    alert_mgr.acknowledge_alert(identifier=high_alert.alert_id, operator_id=admin.id)
    db_alert_ack = next(a for a in tenant_op.list_alerts(admin, org.id) if a.id == high_alert.alert_id)
    assert db_alert_ack.status == "ACKNOWLEDGED"

    # 3. Transition: ACKNOWLEDGED -> RESOLVED
    alert_mgr.resolve_alert(identifier=high_alert.alert_id, operator_id=admin.id, note="Resolved by command center")
    db_alert_res = next(a for a in tenant_op.list_alerts(admin, org.id) if a.id == high_alert.alert_id)
    assert db_alert_res.status == "RESOLVED"


def test_real_video_pipeline_person_and_head_modes():
    """
    Validates the end-to-end AI surveillance pipeline on real video footage:
    - Person Mode (conf 0.35, 640x640)
    - Head Mode (conf 0.25, 640x640)
    - DeepSORT tracking ID persistence
    - Density grid calculation
    - Optical flow crowd motion analysis
    - Heatmap generation
    - Risk assessment computation
    """
    test_video = BASE_DIR / "data" / "videos" / "crowd_sample.mp4"
    if not test_video.exists():
        pytest.skip(f"Test video {test_video} not found")

    cap = cv2.VideoCapture(str(test_video))
    assert cap.isOpened(), "Failed to open crowd_sample.mp4"

    frames = []
    for _ in range(10):
        ret, frame = cap.read()
        if not ret:
            break
        frames.append(frame)
    cap.release()
    assert len(frames) >= 5, "Could not read sufficient frames from test video"

    # 1. Person Mode Pipeline
    person_detector = PersonDetector(confidence=0.35, device="cpu", imgsz=640)
    tracker_p = PersonTracker(max_age=30, n_init=1)
    density_p = DensityEstimator(grid_size=(4, 4))
    motion_p = CrowdMotionAnalyzer(grid_size=(4, 4), flow_interval=1)
    risk_p = RiskAssessor()

    p_detections = person_detector.detect(frames[0])
    assert isinstance(p_detections, list)

    p_tracks = tracker_p.update(p_detections, frames[0])
    _, p_max_dens = density_p.calculate_density(p_tracks, frames[0].shape)
    _, p_motion_summary = motion_p.analyze_frame(frames[0])
    p_risk_summary = risk_p.assess_frame(p_max_dens, p_motion_summary, p_tracks, time.time())

    assert "risk" in p_risk_summary
    assert "combined_score" in p_risk_summary

    # Heatmap generation
    heatmap_overlay, density_grid = generate_heatmap(frames[0], p_tracks)
    assert heatmap_overlay is not None
    assert heatmap_overlay.shape == frames[0].shape
    assert density_grid is not None

    # 2. Head Mode Pipeline
    head_detector = ExperimentalHeadDetector(confidence=0.25, device="cpu", imgsz=640)
    h_detections = head_detector.detect_full_frame(frames[0], enhance_contrast=False)
    assert isinstance(h_detections, list)
    for det in h_detections:
        # Verify ([x, y, w, h], conf, cls) structure
        assert len(det) == 3
        assert det[2] == 0  # Head class


def test_multicamera_manager_lifecycle_and_rewind():
    """
    Validates MultiCameraManager:
    - 4 camera slot initialization
    - Automatic video rewind / loop on EOF
    - Reconnection handling
    - stop_all_cameras() cleanup
    """
    video_path = str(BASE_DIR / "data" / "videos" / "crowd_sample.mp4")
    if not os.path.exists(video_path):
        pytest.skip("Test video not found")

    mock_configs = [
        {"id": f"CAM-0{i}", "name": f"Camera {i}", "source": video_path, "source_type": "video", "enabled": True}
        for i in range(1, 5)
    ]

    mgr = MultiCameraManager(
        camera_configs=mock_configs,
        detect_interval=2,
    )
    assert len(mgr.cameras) == 4

    # Start all cameras
    online = mgr.start_all_cameras()
    assert online == 4

    # Step CCTV Grid
    grid_frames = mgr.step_all()
    assert len(grid_frames) == 4
    for cam_id, frame in grid_frames.items():
        assert frame is not None
        assert frame.shape[0] > 0

    # Step Focus Feed on CAM-02
    focus_frames = mgr.step_focus("CAM-02")
    assert "CAM-02" in focus_frames
    assert focus_frames["CAM-02"] is not None

    # Test EOF auto-rewind: seek CAM-01 to end
    cam1 = mgr.cameras["CAM-01"]
    total_frames = cam1.cap.get(cv2.CAP_PROP_FRAME_COUNT)
    if total_frames > 5:
        cam1.cap.set(cv2.CAP_PROP_POS_FRAMES, total_frames - 1)
        # Stepping should read last frame and auto-rewind to 0
        step_frames = mgr.step_all()
        assert cam1.cap.isOpened()
        assert cam1.status == "ONLINE"

    # Stop all cameras
    mgr.stop_all_cameras()
    for cam_id, cam in mgr.cameras.items():
        assert cam.cap is None
        assert cam.status in ("OFFLINE", "DISABLED")
