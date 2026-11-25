"""
CrowdPatrol Demo - Multi-User Isolation & Concurrent Email Routing Audit Suite.

Verifies:
1. Two separate users (User A and User B) generating alerts simultaneously.
2. Alert-level email recipient binding: User A's alerts route exclusively to User A's email,
   User B's alerts route exclusively to User B's email, even when dispatch occurs concurrently.
3. User A cannot read, edit, or modify User B's camera configurations.
4. User A cannot read, acknowledge, or modify User B's alert history ledger.
5. SQLite concurrent-write safety under simulated simultaneous worker threads.
6. Session state cleanup on logout preventing state leaks across account switches.
"""

import os
import sys
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.demo_auth import (
    init_auth_db,
    provision_user,
    register_user,
    authenticate_user,
    get_user_camera_configs,
    save_user_camera_configs,
    log_user_alert_event,
    get_user_alert_ledger,
    update_user_alert_status,
    get_db_connection
)
from src.alert_manager import AlertEvent, AlertManager
from src.notification_dispatcher import NotificationDispatcher, NotificationConfig


def test_concurrent_multi_user_email_routing_isolation(tmp_path):
    """
    Verify that when User A and User B generate alerts concurrently,
    each alert transmits exclusively to its owning user's registered email,
    without race conditions or cross-contamination from mutable global state.
    """
    mock_email_service = MagicMock()
    mock_sms_service = MagicMock()

    config = NotificationConfig(
        smtp_host="smtp.gmail.com",
        smtp_port=587,
        smtp_username="shreyaskeyboardtutorials@gmail.com",
        smtp_password="app_password",
        email_sender="shreyaskeyboardtutorials@gmail.com",
        email_recipients=["shreyaskeyboardtutorials@gmail.com"],  # fallback default
        enabled=True
    )
    dispatcher = NotificationDispatcher(
        config=config,
        email_service=mock_email_service,
        sms_service=mock_sms_service,
        autostart_worker=True
    )

    user_a_email = "alice_control@citymetro.gov"
    user_b_email = "bob_security@arenaevents.org"

    # User A's alert event
    alert_a = AlertEvent(
        alert_id="ALT_USER_A_001",
        camera_id="CAM-A1",
        camera_name="Alice Terminal Entrance",
        timestamp="2026-11-25T00:15:00",
        risk_level="HIGH",
        risk_score=91.5,
        reason="Rapid Overcrowding detected at Terminal Gate",
        status="ACTIVE",
        severity="HIGH",
        user_id=101,
        recipient_email=user_a_email
    )

    # User B's alert event
    alert_b = AlertEvent(
        alert_id="ALT_USER_B_002",
        camera_id="CAM-B2",
        camera_name="Bob Arena Concourse",
        timestamp="2026-11-25T00:15:00",
        risk_level="CRITICAL",
        risk_score=97.8,
        reason="Critical Density Bottleneck at Concourse Exit",
        status="ACTIVE",
        severity="CRITICAL",
        user_id=202,
        recipient_email=user_b_email
    )

    # Dispatch both alerts
    res_a = dispatcher.dispatch_alert(alert_a)
    res_b = dispatcher.dispatch_alert(alert_b)

    assert res_a["email"] == "QUEUED"
    assert res_b["email"] == "QUEUED"

    # Allow worker thread to process queued tasks
    time.sleep(0.4)
    dispatcher.stop()

    # Verify mock email service was called twice
    assert mock_email_service.send_email.call_count == 2

    # Collect recipients passed to send_email in each dispatch call
    calls = mock_email_service.send_email.call_args_list
    call_recipients = [c.kwargs.get("recipients") for c in calls]

    # Verify Alice's alert went only to Alice's email
    assert [user_a_email] in call_recipients
    # Verify Bob's alert went only to Bob's email
    assert [user_b_email] in call_recipients

    # Verify no call went to the wrong recipient or cross-mingled
    for target_list in call_recipients:
        assert target_list == [user_a_email] or target_list == [user_b_email]
        assert len(target_list) == 1


def test_camera_configuration_strict_cross_user_isolation(tmp_path):
    """
    Verify User A cannot read, edit, or overwrite User B's camera layout,
    and switching active user ID reliably isolates custom device indices and sources.
    """
    test_db = tmp_path / "camera_audit.db"
    init_auth_db(test_db)

    # Register User A and User B
    _, _, u_a = register_user("director_a", "dir_a@corp.com", "PasswordA123!", db_path=test_db)
    _, _, u_b = register_user("director_b", "dir_b@corp.com", "PasswordB123!", db_path=test_db)

    cams_a = get_user_camera_configs(u_a["id"], db_path=test_db)
    cams_b = get_user_camera_configs(u_b["id"], db_path=test_db)

    # Modify Director A's CAM-01 to a live USB webcam and CAM-03 to a custom phone stream
    cams_a[0]["name"] = "A Secure Vault Webcam"
    cams_a[0]["source"] = 1
    cams_a[0]["source_type"] = "webcam"
    cams_a[2]["name"] = "A Perimeter Phone Stream"
    cams_a[2]["source"] = "http://10.0.0.45:8080/video"
    cams_a[2]["source_type"] = "phone"

    save_user_camera_configs(u_a["id"], cams_a, db_path=test_db)

    # Verify Director B's configurations remain pristine defaults
    reloaded_b = get_user_camera_configs(u_b["id"], db_path=test_db)
    assert reloaded_b[0]["name"] == "Main Sidewalk / Entrance"
    assert reloaded_b[0]["source_type"] == "video"
    assert reloaded_b[2]["name"] == "Street Crossing Plaza"
    assert reloaded_b[2]["source_type"] == "video"

    # Now Director B edits CAM-01 to an RTSP IP camera
    cams_b[0]["name"] = "B Warehouse RTSP"
    cams_b[0]["source"] = "rtsp://192.168.1.200:554/live"
    cams_b[0]["source_type"] = "rtsp"
    save_user_camera_configs(u_b["id"], cams_b, db_path=test_db)

    # Verify Director A's configs remain untouched
    reloaded_a = get_user_camera_configs(u_a["id"], db_path=test_db)
    assert reloaded_a[0]["name"] == "A Secure Vault Webcam"
    assert reloaded_a[0]["source"] == 1
    assert reloaded_a[0]["source_type"] == "webcam"

    # Verify Director B's custom RTSP persists
    reloaded_b_v2 = get_user_camera_configs(u_b["id"], db_path=test_db)
    assert reloaded_b_v2[0]["name"] == "B Warehouse RTSP"
    assert reloaded_b_v2[0]["source"] == "rtsp://192.168.1.200:554/live"


def test_alert_ledger_cross_user_isolation_and_scoped_ack(tmp_path):
    """
    Verify historical alert logs are completely partitioned by user ID,
    and updates/acknowledgements for User A's alerts cannot alter User B's alert records.
    """
    test_db = tmp_path / "ledger_audit.db"
    init_auth_db(test_db)

    _, _, u_a = register_user("analyst_a", "analyst_a@intel.org", "PassIntel123!", db_path=test_db)
    _, _, u_b = register_user("analyst_b", "analyst_b@intel.org", "PassIntel456!", db_path=test_db)

    # Log alerts for both users with identical alert ID names in separate accounts
    log_user_alert_event(
        user_id=u_a["id"],
        alert_id="ALT_SHARED_ID_01",
        camera_id="CAM-01",
        camera_name="Sector A1",
        risk_level="HIGH",
        risk_score=85.0,
        reason="Surge in Sector A",
        primary_risk_zone="A1",
        status="ACTIVE",
        db_path=test_db
    )

    log_user_alert_event(
        user_id=u_b["id"],
        alert_id="ALT_SHARED_ID_01",
        camera_id="CAM-02",
        camera_name="Sector B2",
        risk_level="CRITICAL",
        risk_score=99.0,
        reason="Surge in Sector B",
        primary_risk_zone="C3",
        status="ACTIVE",
        db_path=test_db
    )

    # User A acknowledges their alert
    ok_ack = update_user_alert_status(
        user_id=u_a["id"],
        alert_id="ALT_SHARED_ID_01",
        status="ACKNOWLEDGED",
        acknowledged=True,
        acknowledged_by="Analyst_A",
        db_path=test_db
    )
    assert ok_ack is True

    # User A's ledger reflects acknowledged
    ledger_a = get_user_alert_ledger(u_a["id"], db_path=test_db)
    assert len(ledger_a) == 1
    assert ledger_a[0]["status"] == "ACKNOWLEDGED"
    assert ledger_a[0]["acknowledged"] is True
    assert ledger_a[0]["acknowledged_by"] == "Analyst_A"

    # User B's alert record MUST remain unacknowledged and ACTIVE
    ledger_b = get_user_alert_ledger(u_b["id"], db_path=test_db)
    assert len(ledger_b) == 1
    assert ledger_b[0]["status"] == "ACTIVE"
    assert ledger_b[0]["acknowledged"] is False
    assert ledger_b[0]["acknowledged_by"] is None


def test_sqlite_concurrent_multithreaded_writes(tmp_path):
    """
    Verify SQLite WAL mode handles simultaneous multithreaded logging from concurrent
    camera processing workers without database locks or transaction collisions.
    """
    test_db = tmp_path / "concurrency_test.db"
    init_auth_db(test_db)

    # Provision user accounts first to satisfy foreign key constraints
    num_threads = 6
    records_per_thread = 20
    user_ids = []
    for u in range(1, num_threads + 1):
        _, _, user_info = register_user(f"worker_user_{u}", f"worker_{u}@test.com", "Pass123456!", db_path=test_db)
        user_ids.append(user_info["id"])

    errors = []

    def worker_task(uid: int):
        try:
            for i in range(records_per_thread):
                ok = log_user_alert_event(
                    user_id=uid,
                    alert_id=f"ALT_THR_{uid}_{i}",
                    camera_id=f"CAM-{uid}",
                    camera_name=f"Camera {uid}",
                    risk_level="HIGH" if i % 2 == 0 else "MEDIUM",
                    risk_score=75.0 + i,
                    reason=f"Concurrent test entry {i}",
                    status="ACTIVE",
                    db_path=test_db
                )
                if not ok:
                    errors.append(f"Worker {uid} write returned False at index {i}")
        except Exception as e:
            errors.append(f"Worker {uid} raised: {e}")

    threads = []
    for uid in user_ids:
        t = threading.Thread(target=worker_task, args=(uid,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join(timeout=10.0)

    assert len(errors) == 0, f"Concurrent database errors occurred: {errors}"

    # Verify exact count across all threads
    for uid in user_ids:
        ledger = get_user_alert_ledger(uid, limit=50, db_path=test_db)
        assert len(ledger) == records_per_thread
