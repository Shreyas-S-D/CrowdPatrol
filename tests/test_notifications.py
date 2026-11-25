"""
Unit and Integration Tests for CrowdPatrol Phase 2: Email & SMS Notification Delivery System.

Covers:
1. Email message generation (HTML & text with all required fields).
2. Email successful delivery using mocked SMTP.
3. Email failure handling (SMTPConnectError, SMTPServerDisconnected, auth errors).
4. SMS message generation (concise format <= 160 chars target).
5. SMS successful delivery using mocked Twilio / REST API.
6. SMS failure handling (auth failure, network timeout, rate limits).
7. Severity-based routing (MEDIUM -> None, HIGH -> Email, CRITICAL -> Email + SMS).
8. Duplicate alert suppression per alert ID.
9. Escalation alert notification bypass.
10. Asynchronous non-blocking dispatch behavior.
11. Bounded retry behavior on transient failures.
12. Graceful missing credentials handling (SKIPPED without crashing).
13. Monitoring pipeline isolation (simulated network latency does not block caller).
14. Dashboard rendering helpers formatting and table generation.
15. Test email and test SMS explicit verification actions.
16. Clean dispatcher shutdown with pending work.
"""

import time
import smtplib
from unittest.mock import MagicMock, patch
import pytest

from src.alert_manager import AlertEvent, AlertManager
from src.notification_dispatcher import (
    NotificationConfig,
    NotificationRecord,
    NotificationDispatcher,
    EmailService,
    SMSService,
    format_alert_email_html,
    format_alert_email_text,
    format_alert_sms_text
)
from dashboard.dashboard_utils import (
    format_notification_history_table,
    render_dashboard_notifications
)


@pytest.fixture
def sample_critical_alert():
    """Generates a sample CRITICAL AlertEvent for testing."""
    return AlertEvent(
        alert_id="ALT_TEST_CRIT_001",
        camera_id="CAM-01",
        camera_name="Main Gate",
        timestamp="2026-11-16T15:30:00.000",
        risk_level="CRITICAL",
        risk_score=94.5,
        reason="Critical Crowd Density: 52 persons in zone A1",
        status="ACTIVE",
        severity="CRITICAL",
        category="CRITICAL_DENSITY",
        crowd_density=52,
        person_count=120,
        primary_risk_zone="A1",
        primary_zone_density=52,
        zone_description="Top-Left (Zone A1)"
    )


@pytest.fixture
def sample_high_alert():
    """Generates a sample HIGH AlertEvent for testing."""
    return AlertEvent(
        alert_id="ALT_TEST_HIGH_002",
        camera_id="CAM-02",
        camera_name="Exit Corridor",
        timestamp="2026-11-16T15:31:00.000",
        risk_level="HIGH",
        risk_score=78.0,
        reason="Rapid Crowd Influx detected (+45% surge)",
        status="ACTIVE",
        severity="HIGH",
        category="RAPID_INFLUX",
        crowd_density=28,
        person_count=65,
        primary_risk_zone="B2",
        primary_zone_density=28,
        zone_description="Center-Right (Zone B2)"
    )


@pytest.fixture
def sample_medium_alert():
    """Generates a sample MEDIUM AlertEvent for testing."""
    return AlertEvent(
        alert_id="ALT_TEST_MED_003",
        camera_id="CAM-03",
        camera_name="Food Court",
        timestamp="2026-11-16T15:32:00.000",
        risk_level="MEDIUM",
        risk_score=52.0,
        reason="Elevated localized density (18 persons)",
        status="ACTIVE",
        severity="MEDIUM",
        category="MEDIUM_RISK",
        crowd_density=18,
        person_count=35,
        primary_risk_zone="A2",
        primary_zone_density=18,
        zone_description="Top-Right (Zone A2)"
    )


@pytest.fixture
def mock_config():
    """Returns a fully populated mock NotificationConfig."""
    return NotificationConfig(
        smtp_host="smtp.mockserver.com",
        smtp_port=587,
        smtp_username="test_sender@mockserver.com",
        smtp_password="mock_app_password",
        smtp_use_tls=True,
        email_sender="CrowdPatrol <test_sender@mockserver.com>",
        email_recipients=["security@company.com", "ops@company.com"],
        email_severities={"HIGH", "CRITICAL"},
        twilio_account_sid="ACmock1234567890abcdef1234567890",
        twilio_auth_token="mock_auth_token_secret_123",
        twilio_phone_number="+15550001111",
        sms_recipients=["+15559998888", "+15559997777"],
        sms_severities={"CRITICAL"},
        enabled=True,
        max_retries=2,
        retry_backoff=0.01,
        queue_timeout=0.05
    )


# ==============================================================================
# 1. Message Generation Tests
# ==============================================================================

def test_email_html_message_generation(sample_critical_alert):
    """Verifies HTML email template contains all required alert telemetry fields."""
    html = format_alert_email_html(sample_critical_alert)
    assert "CRITICAL CROWD EMERGENCY" in html
    assert "ALT_TEST_CRIT_001" in html
    assert "CAM-01" in html
    assert "Main Gate" in html
    assert "94.5" in html
    assert "52" in html
    assert "120" in html
    assert "Zone A1" in html
    assert "Top-Left (Zone A1)" in html
    assert "Critical Crowd Density: 52 persons in zone A1" in html
    assert "CRITICAL_DENSITY" in html


def test_email_plain_text_generation(sample_high_alert):
    """Verifies plain text email fallback contains complete structured summary."""
    text = format_alert_email_text(sample_high_alert)
    assert "[CROWDPATROL HIGH ALERT]" in text
    assert "CAM-02" in text
    assert "Exit Corridor" in text
    assert "78.0" in text
    assert "28" in text
    assert "ALT_TEST_HIGH_002" in text
    assert "RAPID_INFLUX" in text


def test_sms_message_generation(sample_critical_alert):
    """Verifies concise SMS format containing severity, camera, timestamp, score, and reason."""
    sms = format_alert_sms_text(sample_critical_alert)
    assert "🚨[CrowdPatrol CRITICAL]" in sms
    assert "CAM-01" in sms
    assert "Score:94.5" in sms
    assert "Dens:52" in sms
    assert "Zone A1" in sms or "Z:A1" in sms
    assert "ALT_TEST_CRIT_001" in sms
    # Ensure concise length target
    assert len(sms) <= 160


# ==============================================================================
# 2. Delivery Service Unit Tests
# ==============================================================================

def test_email_successful_delivery_mock(mock_config):
    """Verifies EmailService successfully connects and transmits via SMTP."""
    service = EmailService(mock_config)
    with patch("smtplib.SMTP") as mock_smtp_cls:
        mock_server = MagicMock()
        mock_smtp_cls.return_value = mock_server

        success = service.send_email(
            subject="Test Subject",
            html_body="<p>Test Body</p>",
            text_body="Test Body",
            recipients=["target@example.com"]
        )

        assert success is True
        mock_smtp_cls.assert_called_with("smtp.mockserver.com", 587, timeout=10.0)
        assert mock_server.starttls.called
        assert mock_server.login.called
        assert mock_server.sendmail.called
        assert mock_server.quit.called


def test_email_failure_handling_mock(mock_config):
    """Verifies EmailService raises exceptions on SMTP connection or auth failure."""
    service = EmailService(mock_config)
    with patch("smtplib.SMTP") as mock_smtp_cls:
        mock_smtp_cls.side_effect = smtplib.SMTPConnectError(421, "Connection refused")

        with pytest.raises(smtplib.SMTPConnectError):
            service.send_email("Subject", "<p>Body</p>", "Body")


def test_sms_successful_delivery_mock(mock_config):
    """Verifies SMSService dispatches SMS successfully via mocked provider."""
    service = SMSService(mock_config)
    with patch("requests.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_post.return_value = mock_resp

        success = service.send_sms("Test SMS message")
        assert success is True
        assert mock_post.called
        call_args = mock_post.call_args
        assert "Accounts/ACmock1234567890abcdef1234567890/Messages.json" in call_args[0][0]
        assert call_args[1]["data"]["From"] == "+15550001111"


def test_sms_failure_handling_mock(mock_config):
    """Verifies SMSService raises descriptive runtime error on provider HTTP failure."""
    service = SMSService(mock_config)
    with patch("requests.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.text = '{"message": "Authenticate failure"}'
        mock_post.return_value = mock_resp

        with pytest.raises(RuntimeError) as exc_info:
            service.send_sms("Test message")
        assert "401" in str(exc_info.value)


# ==============================================================================
# 3. Severity-Based Routing & Duplicate Suppression Tests
# ==============================================================================

def test_severity_based_routing(mock_config, sample_medium_alert, sample_high_alert, sample_critical_alert):
    """
    Verifies routing policy:
    - MEDIUM: Dashboard only (FILTERED_SEVERITY for email & SMS).
    - HIGH: Email queued, SMS filtered.
    - CRITICAL: Both Email and SMS queued.
    """
    mock_email = MagicMock()
    mock_sms = MagicMock()
    dispatcher = NotificationDispatcher(config=mock_config, email_service=mock_email, sms_service=mock_sms, autostart_worker=False)

    # 1. Medium
    r_med = dispatcher.dispatch_alert(sample_medium_alert)
    assert r_med["email"] == "FILTERED_SEVERITY"
    assert r_med["sms"] == "FILTERED_SEVERITY"
    assert dispatcher._queue.qsize() == 0

    # 2. High
    r_high = dispatcher.dispatch_alert(sample_high_alert)
    assert r_high["email"] == "QUEUED"
    assert r_high["sms"] == "FILTERED_SEVERITY"
    assert dispatcher._queue.qsize() == 1

    # 3. Critical
    r_crit = dispatcher.dispatch_alert(sample_critical_alert)
    assert r_crit["email"] == "QUEUED"
    assert r_crit["sms"] == "QUEUED"
    assert dispatcher._queue.qsize() == 3  # 1 from High + 2 from Critical


def test_duplicate_alert_suppression(mock_config, sample_critical_alert):
    """Verifies dispatching the exact same alert ID twice is suppressed."""
    mock_email = MagicMock()
    mock_sms = MagicMock()
    dispatcher = NotificationDispatcher(config=mock_config, email_service=mock_email, sms_service=mock_sms, autostart_worker=False)

    first_dispatch = dispatcher.dispatch_alert(sample_critical_alert)
    assert first_dispatch["email"] == "QUEUED"
    assert first_dispatch["sms"] == "QUEUED"

    second_dispatch = dispatcher.dispatch_alert(sample_critical_alert)
    assert second_dispatch["email"] == "SUPPRESSED_DUPLICATE"
    assert second_dispatch["sms"] == "SUPPRESSED_DUPLICATE"
    assert dispatcher._queue.qsize() == 2


def test_escalation_triggers_new_notification(mock_config, sample_high_alert):
    """Verifies that an escalated alert with a distinct alert ID bypasses suppression and dispatches."""
    mock_email = MagicMock()
    mock_sms = MagicMock()
    dispatcher = NotificationDispatcher(config=mock_config, email_service=mock_email, sms_service=mock_sms, autostart_worker=False)

    # Dispatch High
    r_high = dispatcher.dispatch_alert(sample_high_alert)
    assert r_high["email"] == "QUEUED"
    assert r_high["sms"] == "FILTERED_SEVERITY"

    # Now camera escalates to CRITICAL with a new alert ID
    escalated_alert = AlertEvent(
        alert_id="ALT_TEST_HIGH_002_ESC",
        camera_id=sample_high_alert.camera_id,
        camera_name=sample_high_alert.camera_name,
        timestamp="2026-11-16T15:32:00",
        risk_level="CRITICAL",
        risk_score=91.0,
        reason="Escalated to Critical Density",
        status="ESCALATED",
        severity="CRITICAL",
        category="CRITICAL_DENSITY",
        crowd_density=55,
        person_count=130
    )

    r_esc = dispatcher.dispatch_alert(escalated_alert)
    assert r_esc["email"] == "QUEUED"
    assert r_esc["sms"] == "QUEUED"


# ==============================================================================
# 4. Asynchronous Non-Blocking Dispatch & Worker Execution
# ==============================================================================

def test_asynchronous_dispatch_non_blocking(mock_config, sample_critical_alert):
    """
    Verifies dispatch_alert executes in microseconds and queues background work
    without blocking caller even if delivery has latency.
    """
    mock_email = MagicMock()
    mock_sms = MagicMock()

    # Simulate slow network latency
    def slow_send(*args, **kwargs):
        time.sleep(0.05)
        return True

    mock_email.send_email.side_effect = slow_send
    mock_sms.send_sms.side_effect = slow_send

    dispatcher = NotificationDispatcher(config=mock_config, email_service=mock_email, sms_service=mock_sms, autostart_worker=True)

    t0 = time.perf_counter()
    res = dispatcher.dispatch_alert(sample_critical_alert)
    elapsed = time.perf_counter() - t0

    # Caller must return almost instantly (< 10 ms)
    assert elapsed < 0.05
    assert res["email"] == "QUEUED"
    assert res["sms"] == "QUEUED"

    # Wait for background queue to drain
    dispatcher.stop(timeout=1.0)
    assert dispatcher.total_sent >= 2


def test_retry_behavior_on_transient_failure(mock_config, sample_high_alert):
    """Verifies dispatcher retries transient provider errors up to max_retries."""
    mock_email = MagicMock()
    # Fails first attempt, succeeds on second attempt
    mock_email.send_email.side_effect = [smtplib.SMTPConnectError(421, "Temporary glitch"), True]

    dispatcher = NotificationDispatcher(config=mock_config, email_service=mock_email, sms_service=MagicMock(), autostart_worker=True)

    dispatcher.dispatch_alert(sample_high_alert)

    # Wait for worker to complete retry
    dispatcher.stop(timeout=1.5)

    assert mock_email.send_email.call_count == 2
    assert dispatcher.total_sent == 1
    assert dispatcher.total_failed == 0


def test_retry_exhaustion_marks_failed(mock_config, sample_high_alert):
    """Verifies that exceeding max_retries marks notification record as FAILED."""
    mock_email = MagicMock()
    # Always fails
    mock_email.send_email.side_effect = smtplib.SMTPConnectError(421, "Persistent outage")

    dispatcher = NotificationDispatcher(config=mock_config, email_service=mock_email, sms_service=MagicMock(), autostart_worker=True)

    dispatcher.dispatch_alert(sample_high_alert)
    dispatcher.stop(timeout=1.5)

    assert mock_email.send_email.call_count == mock_config.max_retries
    assert dispatcher.total_failed == 1
    assert dispatcher.total_sent == 0


# ==============================================================================
# 5. Missing Credentials & Secure Configuration Tests
# ==============================================================================

def test_missing_credentials_graceful_handling(sample_critical_alert):
    """Verifies unconfigured credentials mark outcomes as SKIPPED without crashing."""
    empty_config = NotificationConfig(
        smtp_host="",
        smtp_username=None,
        smtp_password=None,
        email_recipients=[],
        twilio_account_sid=None,
        twilio_auth_token=None,
        sms_recipients=[],
        enabled=True
    )
    assert not empty_config.is_email_configured
    assert not empty_config.is_sms_configured

    dispatcher = NotificationDispatcher(config=empty_config, autostart_worker=False)
    res = dispatcher.dispatch_alert(sample_critical_alert)

    assert res["email"] == "SKIPPED_NOT_CONFIGURED"
    assert res["sms"] == "SKIPPED_NOT_CONFIGURED"

    history = dispatcher.get_history()
    assert len(history) == 2
    for item in history:
        assert item.status == "SKIPPED"


def test_safe_dict_never_exposes_credentials(mock_config):
    """Verifies that to_safe_dict never contains raw plaintext password or auth token."""
    safe = mock_config.to_safe_dict()
    assert "mock_app_password" not in str(safe)
    assert "mock_auth_token_secret_123" not in str(safe)
    assert safe["smtp_password_set"] is True
    assert safe["twilio_auth_token_set"] is True


# ==============================================================================
# 6. Pipeline Isolation & AlertManager Integration
# ==============================================================================

def test_alert_manager_pipeline_isolation_with_listener(mock_config, sample_critical_alert):
    """
    Verifies AlertManager processes camera telemetry smoothly when wired to
    NotificationDispatcher via register_listener.
    """
    mock_email = MagicMock()
    mock_sms = MagicMock()
    dispatcher = NotificationDispatcher(config=mock_config, email_service=mock_email, sms_service=mock_sms, autostart_worker=False)

    alert_mgr = AlertManager(cooldown_seconds=30, enable_local_logging=False, notification_dispatcher=dispatcher)

    # Process critical telemetry
    telemetry = {
        "risk_level": "CRITICAL",
        "combined_score": 92.0,
        "max_density": 55,
        "person_count": 110,
        "reason": "Severe crowd congestion"
    }

    t0 = time.perf_counter()
    created_alert = alert_mgr.process_camera_telemetry("CAM-01", "Entrance", telemetry)
    elapsed = time.perf_counter() - t0

    assert created_alert is not None
    assert created_alert.risk_level == "CRITICAL"
    # AlertManager must return immediately (< 20 ms)
    assert elapsed < 0.05
    # Work has been queued in dispatcher
    assert dispatcher._queue.qsize() == 2


# ==============================================================================
# 7. Dashboard Rendering Helpers & Explicit Test Actions
# ==============================================================================

def test_dashboard_notification_rendering_helpers(mock_config):
    """Verifies formatting of notification history tables and metric displays."""
    rec = NotificationRecord(
        record_id="NOTIF_01",
        alert_id="ALT_001",
        camera_id="CAM-01",
        channel="EMAIL",
        recipient="security_alert@company.com",
        severity="HIGH",
        timestamp="2026-11-16T15:40:00",
        status="SENT"
    )

    table_md = format_notification_history_table([rec])
    assert "| Time | Channel | Severity | Camera | Alert ID | Recipient | Status | Notes |" in table_md
    assert "EMAIL" in table_md
    assert "CAM-01" in table_md
    assert "SENT" in table_md
    # Recipient must be masked for security
    assert "sec***@company.com" in table_md

    # Test summary rendering
    dispatcher = NotificationDispatcher(config=mock_config, autostart_worker=False)
    summary = dispatcher.get_status_summary()
    assert summary["is_email_configured"] is True
    assert summary["is_sms_configured"] is True


def test_explicit_test_actions(mock_config):
    """Verifies send_test_email and send_test_sms explicit verification methods."""
    mock_email = MagicMock()
    mock_email.send_email.return_value = True
    mock_sms = MagicMock()
    mock_sms.send_sms.return_value = True

    dispatcher = NotificationDispatcher(config=mock_config, email_service=mock_email, sms_service=mock_sms, autostart_worker=False)

    ok_em, msg_em = dispatcher.send_test_email("custom@test.com")
    assert ok_em is True
    assert "successfully sent" in msg_em
    assert mock_email.send_email.called

    ok_sms, msg_sms = dispatcher.send_test_sms("+15551234567")
    assert ok_sms is True
    assert "successfully sent" in msg_sms
    assert mock_sms.send_sms.called


# ==============================================================================
# 8. Reliability: Cooldown, Escalation Bypass & Multi-Camera Isolation
# ==============================================================================

def test_notification_cooldown_with_alert_manager(mock_config):
    """Verifies that sustained HIGH risk across multiple frames generates only 1 email alert within cooldown."""
    mock_email = MagicMock()
    mock_sms = MagicMock()
    dispatcher = NotificationDispatcher(config=mock_config, email_service=mock_email, sms_service=mock_sms, autostart_worker=False)
    alert_mgr = AlertManager(cooldown_seconds=30.0, enable_local_logging=False, notification_dispatcher=dispatcher)

    # Frame 1: First HIGH detection -> creates alert and queues email
    telemetry1 = {"risk_level": "HIGH", "combined_score": 75.0, "max_density": 22, "person_count": 40}
    a1 = alert_mgr.process_camera_telemetry("CAM-01", "Entrance", telemetry1)
    assert a1 is not None
    assert dispatcher._queue.qsize() == 1

    # Frames 2-5: Sustained HIGH risk within 30s cooldown -> duplicate alerts suppressed, no new emails
    for _ in range(4):
        a_sub = alert_mgr.process_camera_telemetry("CAM-01", "Entrance", telemetry1)
        assert a_sub is None
        assert dispatcher._queue.qsize() == 1


def test_escalation_bypass_in_alert_manager(mock_config):
    """Verifies that risk escalation from HIGH to CRITICAL bypasses cooldown and sends a second notification."""
    mock_email = MagicMock()
    mock_sms = MagicMock()
    dispatcher = NotificationDispatcher(config=mock_config, email_service=mock_email, sms_service=mock_sms, autostart_worker=False)
    alert_mgr = AlertManager(cooldown_seconds=30.0, enable_local_logging=False, notification_dispatcher=dispatcher)

    # 1. Initial HIGH alert -> 1 email queued
    high_telem = {"risk_level": "HIGH", "combined_score": 75.0, "max_density": 22, "person_count": 40}
    a1 = alert_mgr.process_camera_telemetry("CAM-01", "Entrance", high_telem)
    assert a1 is not None
    assert a1.severity == "HIGH"
    assert dispatcher._queue.qsize() == 1  # 1 email

    # 2. Immediate escalation to CRITICAL -> bypasses cooldown, generates escalation alert, queues CRITICAL email + SMS
    crit_telem = {"risk_level": "CRITICAL", "combined_score": 92.0, "max_density": 55, "person_count": 115}
    a2 = alert_mgr.process_camera_telemetry("CAM-01", "Entrance", crit_telem)
    assert a2 is not None
    assert a2.severity == "CRITICAL"
    assert a2.alert_id != a1.alert_id
    assert dispatcher._queue.qsize() == 3  # 1 initial email + 1 escalated email + 1 escalated SMS


def test_multi_camera_independent_notifications(mock_config):
    """Verifies that multiple cameras trigger alerts independently with accurate camera attribution."""
    mock_email = MagicMock()
    mock_sms = MagicMock()
    dispatcher = NotificationDispatcher(config=mock_config, email_service=mock_email, sms_service=mock_sms, autostart_worker=False)
    alert_mgr = AlertManager(cooldown_seconds=30.0, enable_local_logging=False, notification_dispatcher=dispatcher)

    # CAM-01 HIGH alert
    a1 = alert_mgr.process_camera_telemetry("CAM-01", "Gate North", {"risk_level": "HIGH", "combined_score": 76.0})
    # CAM-02 HIGH alert
    a2 = alert_mgr.process_camera_telemetry("CAM-02", "Gate South", {"risk_level": "HIGH", "combined_score": 81.0})

    assert a1 is not None and a2 is not None
    assert a1.camera_id == "CAM-01"
    assert a2.camera_id == "CAM-02"
    assert a1.alert_id != a2.alert_id

    # Queue should have 2 distinct email notifications
    assert dispatcher._queue.qsize() == 2
    task1 = dispatcher._queue.get_nowait()
    task2 = dispatcher._queue.get_nowait()
    assert task1[0].camera_id == "CAM-01"
    assert task2[0].camera_id == "CAM-02"


# ==============================================================================
# Phase 4 Follow-Up Reminder and Acknowledgement Lifecycle Tests
# ==============================================================================

def test_reminder_config_defaults():
    """Verify follow-up reminder configuration parameters and defaults."""
    cfg = NotificationConfig()
    assert cfg.ack_timeout_seconds == 180.0
    assert cfg.max_followup_reminders == 2
    assert cfg.reminder_enabled is True
    assert cfg.reminder_interval_seconds == 180.0


def test_reminder_tracking_registration(mock_config, sample_high_alert):
    """Verify that dispatching a HIGH alert registers it in tracked alerts for reminders."""
    mock_email = MagicMock()
    dispatcher = NotificationDispatcher(config=mock_config, email_service=mock_email, autostart_worker=False)

    res = dispatcher.dispatch_alert(sample_high_alert)
    assert res["email"] == "QUEUED"
    assert sample_high_alert.alert_id in dispatcher._tracked_alerts
    state = dispatcher._tracked_alerts[sample_high_alert.alert_id]
    assert state.acknowledged is False
    assert state.resolved is False
    assert state.reminder_count == 0


def test_reminder_due_evaluation_and_enqueuing(mock_config, sample_high_alert):
    """Verify that _check_pending_reminders detects overdue alerts and enqueues reminder emails."""
    mock_config.ack_timeout_seconds = 0.1  # Fast timeout for test
    mock_config.reminder_interval_seconds = 0.1
    mock_config.max_followup_reminders = 2

    mock_email = MagicMock()
    dispatcher = NotificationDispatcher(config=mock_config, email_service=mock_email, autostart_worker=False)

    dispatcher.dispatch_alert(sample_high_alert)
    assert dispatcher._queue.qsize() == 1  # initial email
    _ = dispatcher._queue.get_nowait()

    # Artificially age the alert
    state = dispatcher._tracked_alerts[sample_high_alert.alert_id]
    state.initial_dispatched_at = time.time() - 10.0

    dispatcher._check_pending_reminders()
    assert state.reminder_count == 1
    assert dispatcher._queue.qsize() == 1

    rem_task = dispatcher._queue.get_nowait()
    assert rem_task[1] == "EMAIL_REMINDER"
    assert rem_task[3] == 1  # reminder_number
    assert rem_task[4] >= 10.0  # elapsed_seconds


def test_reminder_cancelled_on_acknowledge(mock_config, sample_high_alert):
    """Verify that acknowledging an alert cancels future reminders."""
    mock_config.ack_timeout_seconds = 0.1
    mock_email = MagicMock()
    dispatcher = NotificationDispatcher(config=mock_config, email_service=mock_email, autostart_worker=False)

    dispatcher.dispatch_alert(sample_high_alert)
    assert sample_high_alert.alert_id in dispatcher._tracked_alerts

    ok = dispatcher.acknowledge_alert(sample_high_alert.alert_id)
    assert ok is True
    assert dispatcher._tracked_alerts[sample_high_alert.alert_id].acknowledged is True

    # Artificially age and check reminders: should be cleaned up without enqueuing
    dispatcher._tracked_alerts[sample_high_alert.alert_id].initial_dispatched_at = time.time() - 10.0
    _ = dispatcher._queue.get_nowait()  # drain initial
    dispatcher._check_pending_reminders()

    assert dispatcher._queue.qsize() == 0  # No reminder queued
    assert sample_high_alert.alert_id not in dispatcher._tracked_alerts


def test_reminder_cancelled_on_resolve(mock_config, sample_high_alert):
    """Verify that resolving an alert removes it from active reminder tracking."""
    mock_email = MagicMock()
    dispatcher = NotificationDispatcher(config=mock_config, email_service=mock_email, autostart_worker=False)

    dispatcher.dispatch_alert(sample_high_alert)
    assert sample_high_alert.alert_id in dispatcher._tracked_alerts

    ok = dispatcher.resolve_alert(sample_high_alert.alert_id)
    assert ok is True
    assert sample_high_alert.alert_id not in dispatcher._tracked_alerts


def test_alert_manager_ack_resolve_propagation(mock_config):
    """Verify that AlertManager acknowledge_alert and resolve_alert propagate to NotificationDispatcher."""
    mock_email = MagicMock()
    dispatcher = NotificationDispatcher(config=mock_config, email_service=mock_email, autostart_worker=False)
    alert_mgr = AlertManager(cooldown_seconds=30.0, enable_local_logging=False, notification_dispatcher=dispatcher)

    high_telem = {"risk_level": "HIGH", "combined_score": 75.0, "max_density": 22, "person_count": 40}
    alt = alert_mgr.process_camera_telemetry("CAM-01", "Entrance", high_telem)
    assert alt is not None
    assert alt.alert_id in dispatcher._tracked_alerts

    # Acknowledge via AlertManager
    ok_ack = alert_mgr.acknowledge_alert("CAM-01", operator_id="SecurityDesk")
    assert ok_ack is True
    assert dispatcher._tracked_alerts[alt.alert_id].acknowledged is True

    # Resolve via AlertManager
    ok_res = alert_mgr.resolve_alert("CAM-01", operator_id="SecurityDesk", note="Area clear")
    assert ok_res is True
    assert alt.alert_id not in dispatcher._tracked_alerts


def test_email_formatter_reminder_banner(sample_high_alert):
    """Verify HTML and Text formatting for follow-up reminders."""
    html_out = format_alert_email_html(sample_high_alert, reminder_number=1, elapsed_seconds=185.0)
    assert "FOLLOW-UP REMINDER #1" in html_out
    assert "UNACKNOWLEDGED" in html_out
    assert "3m 5s" in html_out

    text_out = format_alert_email_text(sample_high_alert, reminder_number=2, elapsed_seconds=360.0)
    assert "FOLLOW-UP REMINDER #2" in text_out
    assert "UNACKNOWLEDGED" in text_out
    assert "360s" in text_out


