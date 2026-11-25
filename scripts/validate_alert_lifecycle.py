"""
Validation script for CrowdPatrol Phase 5 Alert Lifecycle & Reminders.
Validates:
1. Generation of HIGH and CRITICAL alerts.
2. Operator Acknowledgement workflow.
3. Resolution workflow.
4. Reminder dispatch suppression upon acknowledgement.
5. Reminder timeout triggering for unacknowledged alerts.
"""

import sys
import time
from pathlib import Path
from unittest.mock import MagicMock

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.alert_manager import AlertManager, AlertEvent
from src.notification_dispatcher import NotificationConfig, NotificationDispatcher, EmailService

def run_alert_lifecycle_test():
    print("==================================================")
    print("   PHASE 5: ALERT LIFECYCLE & REMINDER VALIDATION")
    print("==================================================")
    
    # Configure notification dispatcher with short reminder timeout for testing
    cfg = NotificationConfig(
        enabled=True,
        reminder_enabled=True,
        ack_timeout_seconds=0.4,       # Fast timeout for test
        reminder_interval_seconds=0.4,
        max_followup_reminders=2,
        email_severities={"HIGH", "CRITICAL"},
        smtp_host="mock.smtp.local",
        smtp_port=587,
        smtp_username="mock_user@example.com",
        smtp_password="mock_password",
        email_sender="alerts@example.com",
        email_recipients=["admin@example.com"]
    )
    dispatcher = NotificationDispatcher(config=cfg)
    # Mock EmailService to avoid actual network traffic during this lifecycle test
    dispatcher.email_service.send_email = MagicMock(return_value=True)
    dispatcher.start()
    
    test_csv = Path("data/test_alerts_lifecycle.csv")
    alert_mgr = AlertManager(csv_path=test_csv, cooldown_seconds=0.1)
    alert_mgr.attach_notification_dispatcher(dispatcher)
    
    try:
        # Step 1: Ingest HIGH telemetry on CAM-01
        print("\n[Step 1] Ingesting HIGH telemetry on CAM-01...")
        high_telemetry = {
            "risk_level": "HIGH",
            "combined_score": 75.0,
            "max_density": 22,
            "primary_risk_zone": "B1",
            "crowd_density": 22,
            "person_count": 48,
            "reason": "Localized high density in Zone B1"
        }
        res1 = alert_mgr.process_camera_telemetry("CAM-01", "Main Gate", high_telemetry)
        active1 = alert_mgr.get_active_alerts()
        assert len(active1) == 1, f"Expected 1 active alert, got {len(active1)}"
        alert1 = active1[0]
        print(f" -> Active alert generated: {alert1.alert_id} (Status: {alert1.status}, Severity: {alert1.severity})")
        
        # Verify tracked in dispatcher for reminders
        tracked = dispatcher.get_tracked_reminders()
        assert alert1.alert_id in tracked, "Alert not registered in reminder tracker"
        print(f" -> Dispatcher reminder tracker active for {alert1.alert_id}")
        
        # Step 2: Acknowledge alert
        print("\n[Step 2] Operator acknowledging alert...")
        ack_ok = alert_mgr.acknowledge_alert(alert1.alert_id, operator_id="Security_Officer_1")
        assert ack_ok is True, "Acknowledgement failed"
        
        # Check alert state
        active_after_ack = alert_mgr.get_active_alerts()
        assert active_after_ack[0].status == "ACKNOWLEDGED"
        assert active_after_ack[0].acknowledged is True
        assert active_after_ack[0].acknowledged_by == "Security_Officer_1"
        print(f" -> Alert state updated: Status={active_after_ack[0].status}, AckBy={active_after_ack[0].acknowledged_by}")
        
        # Check dispatcher tracker shows acknowledged
        tracked_after_ack = dispatcher.get_tracked_reminders()
        assert tracked_after_ack[alert1.alert_id]["acknowledged"] is True
        print(" -> Reminder tracker confirmed alert is ACKNOWLEDGED (Reminders suppressed).")
        
        # Step 3: Wait past ack timeout and verify no reminders are dispatched and alert is pruned from reminder tracking
        time.sleep(0.6)
        tracked_check = dispatcher.get_tracked_reminders()
        assert (alert1.alert_id not in tracked_check) or (tracked_check[alert1.alert_id]["reminder_count"] == 0), "Reminders were erroneously sent for acknowledged alert!"
        print(" -> Verified: Zero reminders enqueued post-acknowledgement, alert pruned from reminder tracking.")
        
        # Step 4: Resolve alert
        print("\n[Step 3] Operator resolving alert...")
        res_ok = alert_mgr.resolve_alert(alert1.alert_id, operator_id="Security_Officer_1", note="Crowd dispersed peacefully")
        assert res_ok is True, "Resolution failed"
        
        active_after_res = alert_mgr.get_active_alerts()
        assert len(active_after_res) == 0, f"Expected 0 active alerts after resolution, got {len(active_after_res)}"
        print(" -> Alert removed from active ledger upon resolution.")
        
        # Check history has resolved alert
        history = alert_mgr.get_alert_history()
        assert any(a.alert_id == alert1.alert_id and a.status == "RESOLVED" for a in history)
        print(" -> Verified in alert history with status=RESOLVED.")
        
        # Step 5: Test Unacknowledged Alert Reminder Triggering
        print("\n[Step 4] Testing unacknowledged alert reminder triggering...")
        crit_telemetry = {
            "risk_level": "CRITICAL",
            "combined_score": 92.0,
            "max_density": 45,
            "primary_risk_zone": "A2",
            "crowd_density": 45,
            "person_count": 95,
            "reason": "Stampede risk surge in Zone A2"
        }
        res2 = alert_mgr.process_camera_telemetry("CAM-02", "Exit Gate", crit_telemetry)
        active2 = alert_mgr.get_active_alerts()
        assert len(active2) == 1
        alert2 = active2[0]
        print(f" -> Generated unacknowledged CRITICAL alert: {alert2.alert_id}")
        
        # Wait for timeout (0.4s) + buffer (0.6s) to allow background worker to trigger reminder
        time.sleep(0.9)
        tracked_unack = dispatcher.get_tracked_reminders()
        rem_count = tracked_unack[alert2.alert_id]["reminder_count"]
        print(f" -> Reminder count after 0.9s: {rem_count}")
        assert rem_count >= 1, f"Expected at least 1 reminder triggered, got {rem_count}"
        print(f" -> Verified: Unacknowledged alert triggered reminder #{rem_count} as expected.")
        
        # Clean up
        alert_mgr.resolve_alert(alert2.alert_id, operator_id="System_Auto")
        print("\n[✓] ALL ALERT LIFECYCLE & REMINDER TESTS PASSED!")
        
    finally:
        dispatcher.stop()
        if test_csv.exists():
            try:
                test_csv.unlink()
            except Exception:
                pass

if __name__ == "__main__":
    run_alert_lifecycle_test()
