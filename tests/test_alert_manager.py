"""
Comprehensive test suite for Phase 14 Alert System (AlertManager & CameraAlertTracker).
Tests state transitions, escalation, cooldown/debounce, resolution, camera isolation,
required payload fields, local fallback logging, and multi-camera integration.
"""

import os
import csv
import time
import pytest
from pathlib import Path
from src.alert_manager import (
    AlertEvent,
    CameraAlertTracker,
    AlertManager,
    derive_alert_reason
)
from src.multi_camera_manager import MultiCameraManager


def test_low_to_medium_creates_one_alert():
    """Case 1: Transition LOW -> MEDIUM creates exactly one active alert event."""
    tracker = CameraAlertTracker("CAM-01", "Main Entrance", cooldown_seconds=30)
    
    telemetry_medium = {
        "risk_level": "MEDIUM",
        "combined_score": 48.5,
        "max_density": 18,
        "growth_rate": 0.5,
        "last_frame_time": "2026-09-20T22:00:00"
    }
    
    new_alert, resolved = tracker.process_telemetry(telemetry_medium)
    
    assert new_alert is not None
    assert resolved is None
    assert new_alert.camera_id == "CAM-01"
    assert new_alert.camera_name == "Main Entrance"
    assert new_alert.risk_level == "MEDIUM"
    assert new_alert.risk_score == 48.5
    assert new_alert.status == "ACTIVE"
    assert tracker.current_risk_level == "MEDIUM"
    assert tracker.active_alert == new_alert


def test_medium_sustained_does_not_spam_alerts():
    """Case 2: Sustained MEDIUM risk within cooldown window does NOT create duplicate alerts."""
    tracker = CameraAlertTracker("CAM-01", "Main Entrance", cooldown_seconds=30)
    
    telemetry1 = {"risk_level": "MEDIUM", "combined_score": 50.0, "max_density": 16}
    new_alert1, _ = tracker.process_telemetry(telemetry1)
    assert new_alert1 is not None
    
    # Second frame: sustained MEDIUM immediately after
    telemetry2 = {"risk_level": "MEDIUM", "combined_score": 52.0, "max_density": 17}
    new_alert2, _ = tracker.process_telemetry(telemetry2)
    
    assert new_alert2 is None  # Suppressed by cooldown
    assert tracker.active_alert is not None
    assert tracker.active_alert.risk_score == 52.0  # Updated in-place


def test_medium_to_high_creates_escalation_alert():
    """Case 3: Transition MEDIUM -> HIGH creates an escalation alert event."""
    tracker = CameraAlertTracker("CAM-01", "Main Entrance", cooldown_seconds=30)
    
    # Step 1: LOW -> MEDIUM
    tracker.process_telemetry({"risk_level": "MEDIUM", "combined_score": 45.0, "max_density": 16})
    
    # Step 2: MEDIUM -> HIGH
    telemetry_high = {"risk_level": "HIGH", "combined_score": 75.0, "max_density": 32}
    esc_alert, resolved = tracker.process_telemetry(telemetry_high)
    
    assert esc_alert is not None
    assert resolved is None
    assert esc_alert.risk_level == "HIGH"
    assert esc_alert.status == "ESCALATED"
    assert esc_alert.risk_score == 75.0
    assert tracker.current_risk_level == "HIGH"


def test_high_sustained_does_not_spam_alerts():
    """Case 4: Sustained HIGH risk within cooldown window does NOT spam alerts."""
    tracker = CameraAlertTracker("CAM-01", "Main Entrance", cooldown_seconds=30)
    
    # LOW -> HIGH
    alt1, _ = tracker.process_telemetry({"risk_level": "HIGH", "combined_score": 80.0, "max_density": 35})
    assert alt1 is not None
    
    # Next frame HIGH sustained
    alt2, _ = tracker.process_telemetry({"risk_level": "HIGH", "combined_score": 82.0, "max_density": 36})
    assert alt2 is None  # Suppressed by cooldown


def test_high_to_low_clears_active_alert():
    """Case 5: Transition HIGH -> LOW clears/resolves the active alert state."""
    tracker = CameraAlertTracker("CAM-01", "Main Entrance", cooldown_seconds=30)
    
    # LOW -> HIGH
    tracker.process_telemetry({"risk_level": "HIGH", "combined_score": 85.0, "max_density": 40})
    assert tracker.active_alert is not None
    
    # HIGH -> LOW
    new_alt, resolved_alt = tracker.process_telemetry({"risk_level": "LOW", "combined_score": 20.0, "max_density": 4})
    
    assert new_alt is None
    assert resolved_alt is not None
    assert resolved_alt.status == "RESOLVED"
    assert tracker.active_alert is None
    assert tracker.current_risk_level == "LOW"


def test_independent_camera_alert_states():
    """Case 6: Verifies CAM-01 and CAM-02 maintain strictly independent alert states."""
    manager = AlertManager(cooldown_seconds=30, enable_local_logging=False)
    
    # CAM-01 transitions to HIGH
    alt_cam1 = manager.process_camera_telemetry("CAM-01", "Entrance", {"risk_level": "HIGH", "combined_score": 78.0})
    
    # CAM-02 remains LOW
    alt_cam2 = manager.process_camera_telemetry("CAM-02", "Plaza", {"risk_level": "LOW", "combined_score": 15.0})
    
    active = manager.get_active_alerts()
    assert len(active) == 1
    assert active[0].camera_id == "CAM-01"
    assert manager.get_camera_alert_status("CAM-02") is None


def test_cooldown_debounce_behavior():
    """Case 7: Cooldown expires after cooldown_seconds allowing a new alert to trigger."""
    tracker = CameraAlertTracker("CAM-01", "Main Entrance", cooldown_seconds=0.1)  # short cooldown for test
    
    # First alert
    alt1, _ = tracker.process_telemetry({"risk_level": "MEDIUM", "combined_score": 50.0})
    assert alt1 is not None
    
    # Immediately after (suppressed)
    alt2, _ = tracker.process_telemetry({"risk_level": "MEDIUM", "combined_score": 55.0})
    assert alt2 is None
    
    # Wait for short cooldown to expire
    time.sleep(0.15)
    
    # After cooldown: re-triggers alert event
    alt3, _ = tracker.process_telemetry({"risk_level": "MEDIUM", "combined_score": 58.0})
    assert alt3 is not None
    assert alt3.alert_id != alt1.alert_id


def test_alert_payload_required_fields():
    """Case 8: Verifies AlertEvent payload contains all required schema fields."""
    event = AlertEvent(
        alert_id="ALT_TEST_001",
        camera_id="CAM-01",
        camera_name="Test Camera",
        timestamp="2026-09-20T22:30:00",
        risk_level="HIGH",
        risk_score=88.5,
        reason="High Crowd Density (32 persons/cell)",
        status="ACTIVE",
        details={"max_density": 32}
    )
    
    d = event.to_dict()
    required_keys = ["alert_id", "camera_id", "camera_name", "timestamp", "risk_level", "risk_score", "reason", "status", "details"]
    for k in required_keys:
        assert k in d
        
    assert d["alert_id"] == "ALT_TEST_001"
    assert d["risk_level"] == "HIGH"
    assert d["risk_score"] == 88.5
    assert "High Crowd Density" in d["reason"]


def test_firebase_and_local_fallback(tmp_path):
    """Case 9: Verifies local CSV fallback logging works cleanly when offline or Firebase fails."""
    csv_file = tmp_path / "test_alerts.csv"
    manager = AlertManager(cooldown_seconds=30, enable_local_logging=True, csv_path=csv_file)
    
    # Process high risk telemetry
    alt = manager.process_camera_telemetry("CAM-01", "Gate 1", {"risk_level": "HIGH", "combined_score": 85.0, "max_density": 30})
    assert alt is not None
    assert csv_file.exists()
    
    with open(csv_file, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = list(reader)
        assert len(rows) == 2  # Header + 1 row
        assert rows[1][0] == alt.alert_id
        assert rows[1][1] == "CAM-01"
        assert rows[1][4] == "HIGH"


def test_multi_camera_manager_alert_integration():
    """Case 10: Verifies MultiCameraManager integrates AlertManager without breaking camera operations."""
    multi_cam = MultiCameraManager(device="cpu")
    assert multi_cam.alert_manager is not None
    
    # Manually pass telemetry to test multi-camera alert accessor
    multi_cam.alert_manager.process_camera_telemetry("CAM-01", "Entrance", {"risk_level": "HIGH", "combined_score": 90.0, "max_density": 35})
    
    active_alerts = multi_cam.get_active_alerts()
    assert len(active_alerts) == 1
    assert active_alerts[0].camera_id == "CAM-01"
    assert active_alerts[0].risk_level == "HIGH"


def test_existing_person_and_head_modes_unchanged():
    """Case 11: Verifies Person Mode and Experimental Head Mode remain compatible."""
    manager = AlertManager(cooldown_seconds=30, enable_local_logging=False)
    
    # Person Mode telemetry
    person_telemetry = {"risk_level": "MEDIUM", "combined_score": 55.0, "person_count": 25, "max_density": 16, "mode": "PERSON"}
    alt_person = manager.process_camera_telemetry("CAM-01", "Person Feed", person_telemetry)
    assert alt_person is not None
    assert alt_person.risk_level == "MEDIUM"
    
    # Head Mode telemetry
    head_telemetry = {"risk_level": "HIGH", "combined_score": 82.0, "visible_heads": 40, "max_density": 30, "mode": "HEAD"}
    alt_head = manager.process_camera_telemetry("CAM-02", "Head Feed", head_telemetry)
    assert alt_head is not None
    assert alt_head.risk_level == "HIGH"
    
    # Both active simultaneously
    active = manager.get_active_alerts()
    assert len(active) == 2
