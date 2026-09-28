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
    derive_alert_reason,
    extract_spatial_risk_info
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


def test_high_creates_emergency_state():
    """Phase 15 Case 1: HIGH risk creates active unacknowledged alert in emergency state."""
    manager = AlertManager(cooldown_seconds=30, enable_local_logging=False)
    alt = manager.process_camera_telemetry("CAM-01", "Entrance", {"risk_level": "HIGH", "combined_score": 85.0})
    
    assert alt is not None
    assert alt.risk_level == "HIGH"
    assert alt.acknowledged is False
    assert alt.alarm_played is False
    
    unack = manager.get_unacknowledged_high_alerts()
    assert len(unack) == 1
    assert unack[0].camera_id == "CAM-01"


def test_medium_does_not_create_emergency_state():
    """Phase 15 Case 2: MEDIUM risk creates active warning alert but NOT an unacknowledged emergency state."""
    manager = AlertManager(cooldown_seconds=30, enable_local_logging=False)
    alt = manager.process_camera_telemetry("CAM-01", "Entrance", {"risk_level": "MEDIUM", "combined_score": 50.0})
    
    assert alt is not None
    assert alt.risk_level == "MEDIUM"
    
    # MEDIUM is warning state, not emergency HIGH
    unack = manager.get_unacknowledged_high_alerts()
    assert len(unack) == 0


def test_multiple_high_cameras_independent_acknowledgement():
    """Phase 15 Case 3: Acknowledging CAM-01 leaves CAM-02 unacknowledged in emergency state."""
    manager = AlertManager(cooldown_seconds=30, enable_local_logging=False)
    
    manager.process_camera_telemetry("CAM-01", "Gate 1", {"risk_level": "HIGH", "combined_score": 82.0})
    manager.process_camera_telemetry("CAM-02", "Gate 2", {"risk_level": "HIGH", "combined_score": 88.0})
    
    assert len(manager.get_unacknowledged_high_alerts()) == 2
    
    # Acknowledge CAM-01 only
    ok = manager.acknowledge_alert("CAM-01", operator_id="Op1")
    assert ok is True
    
    unack = manager.get_unacknowledged_high_alerts()
    assert len(unack) == 1
    assert unack[0].camera_id == "CAM-02"
    assert manager.get_camera_alert_status("CAM-01").acknowledged is True


def test_acknowledgement_does_not_resolve_risk():
    """Phase 15 Case 4: Operator acknowledgement does NOT resolve active camera risk level."""
    manager = AlertManager(cooldown_seconds=30, enable_local_logging=False)
    manager.process_camera_telemetry("CAM-01", "Gate 1", {"risk_level": "HIGH", "combined_score": 85.0})
    
    manager.acknowledge_alert("CAM-01", operator_id="Op1")
    
    # Risk remains HIGH
    tracker = manager.camera_trackers["CAM-01"]
    assert tracker.current_risk_level == "HIGH"
    assert tracker.active_alert is not None
    assert tracker.active_alert.acknowledged is True


def test_high_escalation_triggers_emergency():
    """Phase 15 Case 5: Escalation MEDIUM -> HIGH creates a new unacknowledged emergency alert."""
    manager = AlertManager(cooldown_seconds=30, enable_local_logging=False)
    
    # LOW -> MEDIUM
    manager.process_camera_telemetry("CAM-01", "Gate 1", {"risk_level": "MEDIUM", "combined_score": 50.0})
    assert len(manager.get_unacknowledged_high_alerts()) == 0
    
    # MEDIUM -> HIGH escalation
    alt_esc = manager.process_camera_telemetry("CAM-01", "Gate 1", {"risk_level": "HIGH", "combined_score": 80.0})
    assert alt_esc is not None
    assert alt_esc.status == "ESCALATED"
    assert len(manager.get_unacknowledged_high_alerts()) == 1


def test_sustained_high_does_not_retrigger_alarm():
    """Phase 15 Case 6: Pending sound alarm triggers ONCE per HIGH alert event, not on every frame."""
    manager = AlertManager(cooldown_seconds=30, enable_local_logging=False)
    manager.process_camera_telemetry("CAM-01", "Gate 1", {"risk_level": "HIGH", "combined_score": 80.0})
    
    # First query retrieves pending alarm alert and marks alarm_played = True
    pending1 = manager.get_pending_alarm_alerts()
    assert len(pending1) == 1
    assert pending1[0].alarm_played is True
    
    # Second frame sustained HIGH
    manager.process_camera_telemetry("CAM-01", "Gate 1", {"risk_level": "HIGH", "combined_score": 82.0})
    pending2 = manager.get_pending_alarm_alerts()
    assert len(pending2) == 0  # Alarm suppressed on sustained frame


def test_resolved_alerts_clear_emergency_state():
    """Phase 15 Case 7: Transition to LOW resolves active alert and clears emergency state."""
    manager = AlertManager(cooldown_seconds=30, enable_local_logging=False)
    manager.process_camera_telemetry("CAM-01", "Gate 1", {"risk_level": "HIGH", "combined_score": 80.0})
    assert len(manager.get_unacknowledged_high_alerts()) == 1
    
    # HIGH -> LOW
    manager.process_camera_telemetry("CAM-01", "Gate 1", {"risk_level": "LOW", "combined_score": 10.0})
    assert len(manager.get_unacknowledged_high_alerts()) == 0
    assert manager.get_camera_alert_status("CAM-01") is None


def test_direct_stream_alert_lifecycle_and_isolation():
    """Phase 15 Direct Stream: Verify DIRECT-01 alert lifecycle (LOW -> MEDIUM -> HIGH -> ACK -> LOW) and isolation from CCTV streams."""
    manager = AlertManager(cooldown_seconds=30, enable_local_logging=False)
    
    # 1. DIRECT-01 LOW
    manager.process_camera_telemetry("DIRECT-01", "Direct Stream", {"risk_level": "LOW", "combined_score": 15.0})
    assert manager.get_camera_alert_status("DIRECT-01") is None
    assert len(manager.get_unacknowledged_high_alerts()) == 0
    
    # 2. DIRECT-01 MEDIUM
    alt_med = manager.process_camera_telemetry("DIRECT-01", "Direct Stream", {"risk_level": "MEDIUM", "combined_score": 45.0})
    assert alt_med is not None
    assert alt_med.camera_id == "DIRECT-01"
    assert alt_med.risk_level == "MEDIUM"
    assert len(manager.get_unacknowledged_high_alerts()) == 0  # MEDIUM is warning, not emergency alarm
    
    # 3. DIRECT-01 HIGH escalation & one-shot alarm
    alt_high = manager.process_camera_telemetry("DIRECT-01", "Direct Stream", {"risk_level": "HIGH", "combined_score": 85.0})
    assert alt_high is not None
    assert alt_high.risk_level == "HIGH"
    assert alt_high.status == "ESCALATED"
    
    unack = manager.get_unacknowledged_high_alerts()
    assert len(unack) == 1
    assert unack[0].camera_id == "DIRECT-01"
    
    pending = manager.get_pending_alarm_alerts()
    assert len(pending) == 1
    assert pending[0].camera_id == "DIRECT-01"
    
    # 4. Sustained HIGH no spam
    alt_sustained = manager.process_camera_telemetry("DIRECT-01", "Direct Stream", {"risk_level": "HIGH", "combined_score": 87.0})
    assert alt_sustained is None  # Suppressed by cooldown
    assert len(manager.get_pending_alarm_alerts()) == 0  # Alarm played once
    
    # 5. Isolation check from CCTV Command Center cameras (CAM-01..04)
    manager.process_camera_telemetry("CAM-01", "Entrance", {"risk_level": "LOW", "combined_score": 10.0})
    assert manager.get_camera_alert_status("CAM-01") is None
    assert manager.get_camera_alert_status("DIRECT-01").risk_level == "HIGH"
    assert len(manager.get_unacknowledged_high_alerts()) == 1  # Only DIRECT-01
    
    # 6. HIGH acknowledgement
    ok = manager.acknowledge_alert("DIRECT-01", operator_id="DirectStreamOperator")
    assert ok is True
    assert manager.get_camera_alert_status("DIRECT-01").acknowledged is True
    assert len(manager.get_unacknowledged_high_alerts()) == 0  # Removed from unacknowledged emergency list
    assert manager.get_camera_alert_status("DIRECT-01").risk_level == "HIGH"  # Underlying risk score preserved
    
    # 7. HIGH -> LOW resolution
    alt_res = manager.process_camera_telemetry("DIRECT-01", "Direct Stream", {"risk_level": "LOW", "combined_score": 12.0})
    assert manager.get_camera_alert_status("DIRECT-01") is None  # Active alert resolved


def test_cctv_and_direct_stream_independent_acknowledgements():
    """Verify CCTV streams (CAM-01..04) and Direct Stream (DIRECT-01) operate with completely independent alert states."""
    manager = AlertManager(cooldown_seconds=30, enable_local_logging=False)
    
    # Trigger HIGH risk on both DIRECT-01 and CAM-02
    manager.process_camera_telemetry("DIRECT-01", "Direct Stream", {"risk_level": "HIGH", "combined_score": 88.0})
    manager.process_camera_telemetry("CAM-02", "Overhead Dense Zone", {"risk_level": "HIGH", "combined_score": 92.0})
    
    assert len(manager.get_unacknowledged_high_alerts()) == 2
    
    # Acknowledge DIRECT-01 only
    ok_direct = manager.acknowledge_alert("DIRECT-01", operator_id="DirectOperator")
    assert ok_direct is True
    
    # CAM-02 remains unacknowledged
    unack = manager.get_unacknowledged_high_alerts()
    assert len(unack) == 1
    assert unack[0].camera_id == "CAM-02"
    
    # Acknowledge CAM-02
    ok_cam2 = manager.acknowledge_alert("CAM-02", operator_id="CCTVOperator")
    assert ok_cam2 is True
    assert len(manager.get_unacknowledged_high_alerts()) == 0


def test_spatial_cell_naming_convention():
    """Requirement 1: Verify correct 4x4 grid cell naming (A1-D4) and descriptions."""
    # Top-Left (0, 0) -> A1
    map_a1 = [[0]*4 for _ in range(4)]
    map_a1[0][0] = 5
    info_a1 = extract_spatial_risk_info(map_a1)
    assert info_a1["primary_risk_zone"] == "A1"
    assert info_a1["zone_description"] == "Top-Left"
    
    # Upper/Right-Center (1, 2) -> B3
    map_b3 = [[0]*4 for _ in range(4)]
    map_b3[1][2] = 18
    info_b3 = extract_spatial_risk_info(map_b3)
    assert info_b3["primary_risk_zone"] == "B3"
    assert info_b3["zone_description"] == "Upper/Right-Center"
    
    # Bottom-Right (3, 3) -> D4
    map_d4 = [[0]*4 for _ in range(4)]
    map_d4[3][3] = 22
    info_d4 = extract_spatial_risk_info(map_d4)
    assert info_d4["primary_risk_zone"] == "D4"
    assert info_d4["zone_description"] == "Bottom-Right"


def test_highest_density_cell_identification():
    """Requirement 2: Highest-density cell in 4x4 matrix is correctly identified."""
    density_grid = [
        [2, 3, 1, 0],
        [4, 5, 18, 2],  # B3 = 18
        [1, 0, 8, 3],
        [0, 1, 2, 4]
    ]
    spatial_info = extract_spatial_risk_info(density_grid)
    assert spatial_info["primary_risk_zone"] == "B3"
    assert spatial_info["primary_zone_density"] == 18
    assert spatial_info["zone_description"] == "Upper/Right-Center"


def test_zone_attached_to_alert():
    """Requirement 3: Primary risk zone and density are attached to alert payload."""
    tracker = CameraAlertTracker("CAM-03", "Plaza Feed", cooldown_seconds=30)
    density_grid = [
        [0, 0, 0, 0],
        [0, 0, 18, 0],  # B3 = 18
        [0, 0, 0, 0],
        [0, 0, 0, 0]
    ]
    telemetry = {
        "risk_level": "HIGH",
        "combined_score": 78.4,
        "density_map": density_grid,
        "max_density": 18
    }
    alert, _ = tracker.process_telemetry(telemetry)
    assert alert is not None
    assert alert.primary_risk_zone == "B3"
    assert alert.primary_zone_density == 18
    assert alert.zone_description == "Upper/Right-Center"
    assert alert.details["primary_risk_zone"] == "B3"
    assert alert.details["primary_zone_density"] == 18


def test_tied_density_values_deterministic():
    """Requirement 4: Tied peak density values are handled deterministically in row-major order."""
    density_grid = [
        [0, 10, 0, 0],  # A2 = 10
        [0, 0, 0, 0],
        [0, 0, 10, 0],  # C3 = 10
        [0, 0, 0, 0]
    ]
    spatial_info = extract_spatial_risk_info(density_grid)
    # A2 comes first in row-major order
    assert spatial_info["primary_risk_zone"] == "A2"
    assert spatial_info["primary_zone_density"] == 10
    assert "C3" in spatial_info["secondary_zones"]


def test_independent_camera_spatial_zones():
    """Requirement 5: CAM-01 and CAM-02 maintain completely independent risk zones."""
    manager = AlertManager(cooldown_seconds=30, enable_local_logging=False)
    
    # CAM-01 peak at A2
    grid_cam1 = [[0, 12, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]]
    # CAM-02 peak at C3
    grid_cam2 = [[0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 15, 0], [0, 0, 0, 0]]
    
    alt1 = manager.process_camera_telemetry("CAM-01", "Entrance", {"risk_level": "HIGH", "combined_score": 80.0, "density_map": grid_cam1})
    alt2 = manager.process_camera_telemetry("CAM-02", "Concourse", {"risk_level": "HIGH", "combined_score": 85.0, "density_map": grid_cam2})
    
    assert alt1.primary_risk_zone == "A2"
    assert alt1.primary_zone_density == 12
    
    assert alt2.primary_risk_zone == "C3"
    assert alt2.primary_zone_density == 15
    
    # Verify no overwrite across cameras
    assert manager.get_camera_alert_status("CAM-01").primary_risk_zone == "A2"
    assert manager.get_camera_alert_status("CAM-02").primary_risk_zone == "C3"


def test_high_alert_contains_spatial_info():
    """Requirement 6: HIGH alert event contains full spatial risk zone fields."""
    manager = AlertManager(cooldown_seconds=30, enable_local_logging=False)
    grid_high = [[0, 0, 0, 0], [0, 0, 20, 0], [0, 0, 0, 0], [0, 0, 0, 0]]
    alt = manager.process_camera_telemetry("CAM-03", "Main Plaza", {"risk_level": "HIGH", "combined_score": 88.0, "density_map": grid_high})
    
    assert alt is not None
    assert alt.risk_level == "HIGH"
    assert alt.primary_risk_zone == "B3"
    assert alt.primary_zone_density == 20
    assert alt.zone_description == "Upper/Right-Center"


def test_medium_alert_contains_spatial_info():
    """Requirement 7: MEDIUM alert event contains full spatial risk zone fields."""
    manager = AlertManager(cooldown_seconds=30, enable_local_logging=False)
    grid_med = [[0, 0, 0, 0], [0, 0, 6, 0], [0, 0, 0, 0], [0, 0, 0, 0]]
    alt = manager.process_camera_telemetry("CAM-03", "Main Plaza", {"risk_level": "MEDIUM", "combined_score": 36.9, "density_map": grid_med})
    
    assert alt is not None
    assert alt.risk_level == "MEDIUM"
    assert alt.primary_risk_zone == "B3"
    assert alt.primary_zone_density == 6


def test_low_risk_no_emergency_alert():
    """Requirement 8: LOW risk telemetry does not generate an active alert event."""
    manager = AlertManager(cooldown_seconds=30, enable_local_logging=False)
    grid_low = [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]
    alt = manager.process_camera_telemetry("CAM-01", "Quiet Gate", {"risk_level": "LOW", "combined_score": 12.0, "density_map": grid_low})
    
    assert alt is None
    assert manager.get_camera_alert_status("CAM-01") is None


def test_direct_stream_independent_spatial_zone():
    """Requirement 9: Direct Stream (DIRECT-01) calculates and maintains its own spatial risk zone independently."""
    manager = AlertManager(cooldown_seconds=30, enable_local_logging=False)
    grid_direct = [[0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0], [14, 0, 0, 0]]  # D1 = 14
    
    alt_direct = manager.process_camera_telemetry("DIRECT-01", "Direct Stream", {"risk_level": "HIGH", "combined_score": 82.0, "density_map": grid_direct})
    
    assert alt_direct is not None
    assert alt_direct.camera_id == "DIRECT-01"
    assert alt_direct.primary_risk_zone == "D1"
    assert alt_direct.primary_zone_density == 14
    assert alt_direct.zone_description == "Bottom-Left"




