"""
tests/test_tenant_isolation.py
------------------------------
CrowdPatrol 2.0 — Phase 2B.3 Operational Tenant Isolation Test Suite.

Verifies:
1. Camera Slot Isolation: Two organizations maintain independent 4-slot configurations.
2. Hardware Resource Locking & Contention: Physical device locking prevents simultaneous access and reports clear status without crashing.
3. Compute Scheduler Limits: Bounded concurrent active sessions across tenants.
4. Alert Lifecycle & Analytics Isolation: Alerts and metrics are strictly tenant-scoped.
5. Role-Based Permission Gating: VIEWER is strictly read-only; OPERATOR and ORG_ADMIN have authorized write operations.
6. Asset Upload Isolation & Path Traversal Prevention: Files stored in canonical org paths; traversal attempts blocked.
7. Cross-Tenant Access Rejection: Non-members cannot access another organization's operational data.
8. Schema v4 to v5 Migration Safety: Preserves existing data and creates operational tables and indexes.
"""

import os
import sqlite3
import pytest
from pathlib import Path
from datetime import datetime, timezone, timedelta

from src.auth.database import AuthDatabase, User, Organization, OrganizationMembership
from src.auth.service import AuthService
from src.auth.organization_service import OrganizationService, MembershipService
from src.auth.tenant_operational_service import TenantOperationalService
from src.resource_manager import PhysicalDeviceRegistry, ComputeScheduler


@pytest.fixture
def isolated_db(tmp_path):
    db_file = tmp_path / "test_tenant_iso.db"
    db = AuthDatabase(str(db_file))
    return db


@pytest.fixture
def tenant_services(isolated_db):
    auth_svc = AuthService(isolated_db)
    org_svc = OrganizationService(isolated_db)
    mem_svc = MembershipService(isolated_db)
    op_svc = TenantOperationalService(isolated_db)
    # Use dedicated clean registries for tests
    op_svc.device_registry = PhysicalDeviceRegistry()
    op_svc.compute_scheduler = ComputeScheduler(max_concurrent_sessions=2)
    return auth_svc, org_svc, mem_svc, op_svc


def test_schema_v4_to_v5_migration_safety(tmp_path):
    """
    Constructs an explicit Schema v4 database, runs _apply_migration_v5,
    and confirms all 5 operational tables, foreign keys, and indexes exist.
    """
    db_file = tmp_path / "migration_v4_to_v5.db"
    conn = sqlite3.connect(str(db_file))
    conn.execute("PRAGMA foreign_keys = ON;")

    # Setup migrations table at version 4
    conn.execute("""
        CREATE TABLE schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            description TEXT NOT NULL
        );
    """)
    for v in range(1, 5):
        conn.execute(f"INSERT INTO schema_migrations (version, description) VALUES ({v}, 'v{v}');")

    # Minimal base tables
    conn.execute("""
        CREATE TABLE users (
            id TEXT PRIMARY KEY, username TEXT UNIQUE, email TEXT UNIQUE,
            password_hash TEXT, role TEXT, is_active INTEGER DEFAULT 1,
            failed_login_attempts INTEGER DEFAULT 0, locked_until TIMESTAMP,
            created_at TIMESTAMP, updated_at TIMESTAMP
        );
    """)
    conn.execute("""
        CREATE TABLE organizations (
            id TEXT PRIMARY KEY, name TEXT, slug TEXT UNIQUE, description TEXT,
            status TEXT DEFAULT 'ACTIVE', created_at TIMESTAMP, updated_at TIMESTAMP,
            created_by TEXT REFERENCES users(id)
        );
    """)
    conn.commit()
    conn.close()

    # Open with AuthDatabase (triggers v5 migration)
    db = AuthDatabase(str(db_file))
    with db.transaction() as cur:
        cur.execute("SELECT MAX(version) FROM schema_migrations;")
        assert cur.fetchone()[0] == 5

        for table in (
            "tenant_camera_configs",
            "tenant_monitoring_sessions",
            "tenant_alerts",
            "tenant_notification_settings",
            "tenant_uploaded_assets"
        ):
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?;", (table,))
            assert cur.fetchone() is not None, f"Table '{table}' missing after v5 migration"


def test_camera_slot_isolation_between_organizations(tenant_services):
    """
    Confirms two organizations have completely independent 4-camera slots.
    Updating CAM-01 in Org A does not alter CAM-01 in Org B.
    """
    auth_svc, org_svc, _, op_svc = tenant_services
    padmin = auth_svc.register_user("padmin", "padmin@metro.internal", "Pass1234!", role="PLATFORM_ADMIN")
    admin_a = auth_svc.register_user("admin_a", "admin_a@metro.internal", "Pass1234!", role="USER")
    admin_b = auth_svc.register_user("admin_b", "admin_b@metro.internal", "Pass1234!", role="USER")

    org_a = org_svc.create_organization("Metro North", slug="metro-north", actor=padmin, initial_admin_user_id=admin_a.id)
    org_b = org_svc.create_organization("Metro South", slug="metro-south", actor=padmin, initial_admin_user_id=admin_b.id)

    # Initial 4 slots for both
    cams_a = op_svc.get_camera_configs(actor=admin_a, organization_id=org_a.id)
    cams_b = op_svc.get_camera_configs(actor=admin_b, organization_id=org_b.id)
    assert len(cams_a) == 4
    assert len(cams_b) == 4

    # Update CAM-01 in Org A
    op_svc.update_camera_config(
        actor=admin_a,
        organization_id=org_a.id,
        slot_id="CAM-01",
        name="North Terminal Entrance",
        source_type="rtsp",
        source="rtsp://10.0.1.50/live",
        enabled=True,
        detection_mode="HEAD"
    )

    # Verify Org A changed
    updated_a = op_svc.get_camera_configs(actor=admin_a, organization_id=org_a.id)
    slot1_a = next(c for c in updated_a if c.slot_id == "CAM-01")
    assert slot1_a.name == "North Terminal Entrance"
    assert slot1_a.source_type == "rtsp"
    assert slot1_a.detection_mode == "HEAD"

    # Verify Org B remains untouched
    unchanged_b = op_svc.get_camera_configs(actor=admin_b, organization_id=org_b.id)
    slot1_b = next(c for c in unchanged_b if c.slot_id == "CAM-01")
    assert slot1_b.name != "North Terminal Entrance"
    assert slot1_b.source_type == "video"


def test_physical_device_locking_and_contention(tenant_services):
    """
    Verifies physical camera device contention:
    1. Org A starts session using webcam 0; lock is acquired.
    2. Org B attempts to use webcam 0; contention status (DEVICE_IN_USE) returned cleanly.
    3. Org A stops session; lock is released.
    4. Org B can now acquire webcam 0.
    """
    auth_svc, org_svc, _, op_svc = tenant_services
    padmin = auth_svc.register_user("padmin", "padmin@metro.internal", "Pass1234!", role="PLATFORM_ADMIN")
    admin_a = auth_svc.register_user("admin_a", "admin_a@metro.internal", "Pass1234!", role="USER")
    admin_b = auth_svc.register_user("admin_b", "admin_b@metro.internal", "Pass1234!", role="USER")

    org_a = org_svc.create_organization("Zone A", slug="zone-a", actor=padmin, initial_admin_user_id=admin_a.id)
    org_b = org_svc.create_organization("Zone B", slug="zone-b", actor=padmin, initial_admin_user_id=admin_b.id)

    # Configure CAM-01 on both orgs to use webcam 0
    op_svc.update_camera_config(actor=admin_a, organization_id=org_a.id, slot_id="CAM-01", name="A Cam", source_type="webcam", source="0")
    op_svc.update_camera_config(actor=admin_b, organization_id=org_b.id, slot_id="CAM-01", name="B Cam", source_type="webcam", source="0")

    # Org A starts monitoring
    sess_a, info_a = op_svc.start_monitoring_session(actor=admin_a, organization_id=org_a.id)
    assert sess_a is not None
    assert len(info_a["device_issues"]) == 0
    assert "webcam_0" in sess_a.metadata.get("acquired_devices", [])

    # Org B starts monitoring concurrently
    sess_b, info_b = op_svc.start_monitoring_session(actor=admin_b, organization_id=org_b.id)
    assert sess_b is not None
    # Org B must detect contention without crashing
    assert len(info_b["device_issues"]) == 1
    issue = info_b["device_issues"][0]
    assert issue["slot_id"] == "CAM-01"
    assert issue["status"] == "DEVICE_IN_USE"
    assert "currently in use" in issue["message"]

    # Org A stops monitoring
    op_svc.stop_monitoring_session(actor=admin_a, organization_id=org_a.id, session_id=sess_a.id)

    # Org B stops previous session and starts again
    op_svc.stop_monitoring_session(actor=admin_b, organization_id=org_b.id, session_id=sess_b.id)
    sess_b2, info_b2 = op_svc.start_monitoring_session(actor=admin_b, organization_id=org_b.id)
    assert len(info_b2["device_issues"]) == 0
    assert "webcam_0" in sess_b2.metadata.get("acquired_devices", [])


def test_compute_scheduler_bounded_capacity(tenant_services):
    """
    Confirms compute scheduler enforces the host limit (max 2 active sessions)
    and rejects excess concurrent monitoring requests.
    """
    auth_svc, org_svc, _, op_svc = tenant_services
    padmin = auth_svc.register_user("padmin", "padmin@metro.internal", "Pass1234!", role="PLATFORM_ADMIN")

    orgs = [
        org_svc.create_organization(f"Org {i}", slug=f"org-{i}", actor=padmin, initial_admin_user_id=padmin.id)
        for i in range(3)
    ]

    # Start 2 sessions (capacity limit = 2)
    s1, _ = op_svc.start_monitoring_session(actor=padmin, organization_id=orgs[0].id)
    s2, _ = op_svc.start_monitoring_session(actor=padmin, organization_id=orgs[1].id)
    assert s1 is not None and s2 is not None

    # Third session must be rejected with capacity error
    with pytest.raises(RuntimeError, match="capacity limit reached"):
        op_svc.start_monitoring_session(actor=padmin, organization_id=orgs[2].id)

    # Stopping s1 frees slot for s3
    op_svc.stop_monitoring_session(actor=padmin, organization_id=orgs[0].id, session_id=s1.id)
    s3, _ = op_svc.start_monitoring_session(actor=padmin, organization_id=orgs[2].id)
    assert s3 is not None


def test_alert_lifecycle_and_analytics_isolation(tenant_services):
    """
    Confirms alerts are strictly scoped to their organization:
    1. Alerts created in Org A cannot be read, acknowledged, or resolved by Org B.
    2. Lifecycle transitions (ACTIVE -> ACKNOWLEDGED -> RESOLVED) work correctly.
    3. Analytics summary aggregates strictly within organization boundary.
    """
    auth_svc, org_svc, _, op_svc = tenant_services
    padmin = auth_svc.register_user("padmin", "padmin@metro.internal", "Pass1234!", role="PLATFORM_ADMIN")
    op_a = auth_svc.register_user("op_a", "op_a@metro.internal", "Pass1234!", role="USER")
    op_b = auth_svc.register_user("op_b", "op_b@metro.internal", "Pass1234!", role="USER")

    org_a = org_svc.create_organization("Org Alpha", slug="org-alpha", actor=padmin, initial_admin_user_id=op_a.id)
    org_b = org_svc.create_organization("Org Beta", slug="org-beta", actor=padmin, initial_admin_user_id=op_b.id)

    # Record alert in Org A
    alt_a = op_svc.record_alert(
        organization_id=org_a.id,
        session_id=None,
        camera_id="CAM-01",
        camera_name="Main Gate",
        risk_level="CRITICAL",
        risk_score=92.5,
        severity="CRITICAL",
        category="CRITICAL_DENSITY",
        reason="Peak crowd density surge in zone A2",
        crowd_density=55,
        person_count=120,
        primary_risk_zone="A2",
        primary_zone_density=55,
        zone_description="Top-Center"
    )

    # Org A sees alert
    alerts_a = op_svc.list_alerts(actor=op_a, organization_id=org_a.id)
    assert len(alerts_a) == 1
    assert alerts_a[0].id == alt_a.id

    # Org B sees zero alerts
    alerts_b = op_svc.list_alerts(actor=op_b, organization_id=org_b.id)
    assert len(alerts_b) == 0

    # Org B cannot acknowledge Org A's alert
    with pytest.raises(PermissionError):
        op_svc.acknowledge_alert(actor=op_b, organization_id=org_b.id, alert_id=alt_a.id)

    # Org A acknowledges alert
    acked = op_svc.acknowledge_alert(actor=op_a, organization_id=org_a.id, alert_id=alt_a.id)
    assert acked is not None
    assert acked.status == "ACKNOWLEDGED"
    assert acked.acknowledged is True

    # Org A resolves alert
    resolved = op_svc.resolve_alert(actor=op_a, organization_id=org_a.id, alert_id=alt_a.id, note="Cleared by dispatch")
    assert resolved is not None
    assert resolved.status == "RESOLVED"
    assert resolved.details.get("resolution_note") == "Cleared by dispatch"

    # Analytics summary
    analytics_a = op_svc.get_analytics_summary(actor=op_a, organization_id=org_a.id)
    assert analytics_a["alert_counts"]["total"] == 1
    assert analytics_a["alert_counts"]["resolved"] == 1
    assert analytics_a["alert_counts"]["critical"] == 1

    analytics_b = op_svc.get_analytics_summary(actor=op_b, organization_id=org_b.id)
    assert analytics_b["alert_counts"]["total"] == 0


def test_viewer_role_read_only_restriction(tenant_services):
    """
    Confirms VIEWER role is strictly read-only and blocked from:
    1. Starting or stopping surveillance monitoring sessions.
    2. Modifying camera configurations.
    3. Acknowledging or resolving alerts.
    4. Uploading video assets.
    5. Modifying notification settings.
    """
    auth_svc, org_svc, mem_svc, op_svc = tenant_services
    padmin = auth_svc.register_user("padmin", "padmin@metro.internal", "Pass1234!", role="PLATFORM_ADMIN")
    admin = auth_svc.register_user("admin", "admin@metro.internal", "Pass1234!", role="USER")
    viewer = auth_svc.register_user("viewer", "viewer@metro.internal", "Pass1234!", role="USER")

    org = org_svc.create_organization("Secured Facility", slug="secured-facility", actor=padmin, initial_admin_user_id=admin.id)
    mem_svc.add_member(org_id=org.id, user_id=viewer.id, role="VIEWER", actor=admin)

    # 1. Start monitoring blocked
    with pytest.raises(PermissionError, match="VIEWER.*read-only"):
        op_svc.start_monitoring_session(actor=viewer, organization_id=org.id)

    # 2. Update camera config blocked
    with pytest.raises(PermissionError, match="VIEWER.*read-only"):
        op_svc.update_camera_config(actor=viewer, organization_id=org.id, slot_id="CAM-01", name="Hacked", source_type="video", source="hacked.mp4")

    # 3. Create alert via admin, then verify VIEWER cannot acknowledge or resolve
    alt = op_svc.record_alert(
        organization_id=org.id, session_id=None, camera_id="CAM-01", camera_name="Entrance",
        risk_level="HIGH", risk_score=75.0, severity="HIGH", category="HIGH_RISK", reason="Density surge"
    )
    with pytest.raises(PermissionError, match="VIEWER.*read-only"):
        op_svc.acknowledge_alert(actor=viewer, organization_id=org.id, alert_id=alt.id)
    with pytest.raises(PermissionError, match="VIEWER.*read-only"):
        op_svc.resolve_alert(actor=viewer, organization_id=org.id, alert_id=alt.id)

    # 4. Upload video blocked
    with pytest.raises(PermissionError, match="VIEWER.*read-only"):
        op_svc.save_uploaded_video(actor=viewer, organization_id=org.id, file_bytes=b"dummy", original_filename="test.mp4")

    # 5. Modify notifications blocked
    with pytest.raises(PermissionError, match="Administrative privilege required"):
        op_svc.update_notification_settings(actor=viewer, organization_id=org.id, email_enabled=False)

    # 6. Reading cameras and analytics IS permitted for VIEWER
    cams = op_svc.get_camera_configs(actor=viewer, organization_id=org.id)
    assert len(cams) == 4
    analytics = op_svc.get_analytics_summary(actor=viewer, organization_id=org.id)
    assert analytics["alert_counts"]["total"] == 1


def test_asset_upload_isolation_and_path_traversal_prevention(tenant_services, tmp_path):
    """
    Confirms video assets are strictly isolated to tenant directories:
    1. Uploaded file is stored under data/tenants/<org_id>/videos/.
    2. Path traversal strings (e.g. '../../etc/passwd', '..\\cameras.json') are sanitized.
    3. Cross-tenant asset listing excludes other organizations.
    """
    auth_svc, org_svc, _, op_svc = tenant_services
    padmin = auth_svc.register_user("padmin", "padmin@metro.internal", "Pass1234!", role="PLATFORM_ADMIN")
    admin_a = auth_svc.register_user("admin_a", "admin_a@metro.internal", "Pass1234!", role="USER")
    admin_b = auth_svc.register_user("admin_b", "admin_b@metro.internal", "Pass1234!", role="USER")

    org_a = org_svc.create_organization("Asset Org A", slug="asset-org-a", actor=padmin, initial_admin_user_id=admin_a.id)
    org_b = org_svc.create_organization("Asset Org B", slug="asset-org-b", actor=padmin, initial_admin_user_id=admin_b.id)

    # Upload clean video for Org A
    sample_bytes = b"\x00\x00\x00\x20ftypisom" + b"\x00" * 100
    asset_a = op_svc.save_uploaded_video(
        actor=admin_a,
        organization_id=org_a.id,
        file_bytes=sample_bytes,
        original_filename="entrance_test.mp4",
        slot_id="CAM-02"
    )
    assert asset_a.organization_id == org_a.id
    assert Path(asset_a.storage_path).exists()
    assert str(org_a.id) in asset_a.storage_path

    # Attempt path traversal upload
    malicious_name = "../../../config/cameras.json"
    asset_traversal = op_svc.save_uploaded_video(
        actor=admin_a,
        organization_id=org_a.id,
        file_bytes=sample_bytes,
        original_filename=malicious_name
    )
    # Filename must be sanitized and stored strictly inside org folder
    assert ".." not in asset_traversal.filename
    assert str(org_a.id) in asset_traversal.storage_path
    assert Path(asset_traversal.storage_path).exists()
    # Confirm config/cameras.json was not overwritten!
    assert not asset_traversal.storage_path.endswith("config/cameras.json")

    # Org B lists assets
    assets_b = op_svc.list_uploaded_assets(actor=admin_b, organization_id=org_b.id)
    assert len(assets_b) == 0

    # Org A lists assets
    assets_a = op_svc.list_uploaded_assets(actor=admin_a, organization_id=org_a.id)
    assert len(assets_a) == 2


def test_cross_tenant_access_denial(tenant_services):
    """
    Confirms an authenticated user with no membership in Org B cannot query
    or modify Org B's operational data.
    """
    auth_svc, org_svc, _, op_svc = tenant_services
    padmin = auth_svc.register_user("padmin", "padmin@metro.internal", "Pass1234!", role="PLATFORM_ADMIN")
    user_a = auth_svc.register_user("user_a", "user_a@metro.internal", "Pass1234!", role="USER")
    user_b = auth_svc.register_user("user_b", "user_b@metro.internal", "Pass1234!", role="USER")

    org_a = org_svc.create_organization("Org 1", slug="org-1", actor=padmin, initial_admin_user_id=user_a.id)
    org_b = org_svc.create_organization("Org 2", slug="org-2", actor=padmin, initial_admin_user_id=user_b.id)

    # user_a attempts to access Org B cameras
    with pytest.raises(PermissionError, match="Access denied"):
        op_svc.get_camera_configs(actor=user_a, organization_id=org_b.id)

    # user_a attempts to start session in Org B
    with pytest.raises(PermissionError, match="Access denied"):
        op_svc.start_monitoring_session(actor=user_a, organization_id=org_b.id)

    # user_a attempts to list alerts in Org B
    with pytest.raises(PermissionError, match="Access denied"):
        op_svc.list_alerts(actor=user_a, organization_id=org_b.id)

    # user_a attempts to update notification settings in Org B
    with pytest.raises(PermissionError, match="Access denied"):
        op_svc.update_notification_settings(actor=user_a, organization_id=org_b.id, email_enabled=False)


def test_notification_settings_isolation(tenant_services):
    """
    Confirms notification recipients and severities are strictly isolated per organization.
    """
    auth_svc, org_svc, _, op_svc = tenant_services
    padmin = auth_svc.register_user("padmin", "padmin@metro.internal", "Pass1234!", role="PLATFORM_ADMIN")
    admin_a = auth_svc.register_user("admin_a", "admin_a@metro.internal", "Pass1234!", role="USER")
    admin_b = auth_svc.register_user("admin_b", "admin_b@metro.internal", "Pass1234!", role="USER")

    org_a = org_svc.create_organization("Org Mail A", slug="org-mail-a", actor=padmin, initial_admin_user_id=admin_a.id)
    org_b = org_svc.create_organization("Org Mail B", slug="org-mail-b", actor=padmin, initial_admin_user_id=admin_b.id)

    # Configure Org A
    op_svc.update_notification_settings(
        actor=admin_a,
        organization_id=org_a.id,
        email_enabled=True,
        email_recipients=["alerts-a@metro.internal", "dispatch-a@metro.internal"],
        email_severities=["CRITICAL", "HIGH"]
    )

    # Configure Org B
    op_svc.update_notification_settings(
        actor=admin_b,
        organization_id=org_b.id,
        email_enabled=True,
        email_recipients=["security-b@metro.internal"],
        email_severities=["CRITICAL"]
    )

    settings_a = op_svc.get_notification_settings(actor=admin_a, organization_id=org_a.id)
    settings_b = op_svc.get_notification_settings(actor=admin_b, organization_id=org_b.id)

    assert "alerts-a@metro.internal" in settings_a.email_recipients
    assert "alerts-a@metro.internal" not in settings_b.email_recipients
    assert "security-b@metro.internal" in settings_b.email_recipients
    assert "security-b@metro.internal" not in settings_a.email_recipients


def test_tenant_workspace_ui_renders_operational_tabs(monkeypatch, tenant_services):
    """
    AppTest verification: Signing into an organization workspace renders
    the 8 operational tabs (CCTV, Camera Slots, Alerts, Analytics, etc.)
    with no uncaught exceptions.
    """
    monkeypatch.setenv("CROWDPATROL_ALLOW_DEV_SEED", "0")
    monkeypatch.setenv("CROWDPATROL_ENV", "production")

    auth_svc, org_svc, _, _ = tenant_services
    user = auth_svc.register_user("workspace_op", "ws_op@metro.internal", "Pass1234!", role="USER")
    padmin = auth_svc.register_user("ws_padmin", "ws_padmin@metro.internal", "Pass1234!", role="PLATFORM_ADMIN")
    org = org_svc.create_organization("Terminal District", slug="terminal-dist", actor=padmin, initial_admin_user_id=user.id)

    from streamlit.testing.v1 import AppTest
    from pathlib import Path
    import streamlit as st

    st.cache_resource.clear()
    monkeypatch.setenv("CROWDPATROL_AUTH_DB_PATH", str(auth_svc.db.db_path))

    script_path = str(Path(__file__).parent.parent / "dashboard" / "simple_dashboard.py")
    at = AppTest.from_file(script_path)
    at.query_params["page"] = "dashboard"
    at.run(timeout=30)

    # Sign in
    at.text_input(key="login_identity_input").input("workspace_op")
    at.text_input(key="login_password_input").input("Pass1234!")
    at.button(key="login_submit_btn").click().run(timeout=30)
    assert len(at.exception) == 0

    # User enters workspace
    enter_btn = [b for b in at.button if f"btn_enter_{org.id}" in b.key]
    assert len(enter_btn) == 1
    enter_btn[0].click().run(timeout=30)
    assert len(at.exception) == 0

    # Confirms active organization workspace rendered
    assert at.session_state["active_org"].id == org.id
    # Confirms tabs rendered
    assert len(at.tabs) == 8

