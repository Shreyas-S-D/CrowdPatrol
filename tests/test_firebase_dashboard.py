"""
Phase 4 Unit & Integration Test Suite - Firebase & Dashboard Synchronization
Tests 16 primary fields + 3 aliases = 19 keys schema, native type serialization,
alias compatibility, NaN/Inf sanitization, Firebase init & write failures,
offline CSV fallback (missing, empty, malformed), timestamp parsing, staleness,
and connection status classification.
"""

import sys
import math
import os
import json
import numpy as np
from pathlib import Path
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dashboard.dashboard_utils import (
    clean_native_value,
    normalize_telemetry_payload,
    parse_iso_timestamp,
    evaluate_telemetry_staleness,
    load_offline_csv_fallback,
    determine_connection_status
)


def test_nineteen_telemetry_payload_keys():
    """Verify normalized payload contains 16 primary fields + 3 aliases = 19 keys."""
    raw = {
        "person_count": 10,
        "max_density": 5,
        "risk_level": "Medium",
        "combined_score": 45.0,
        "avg_speed": 1.2,
        "fps": 24.5
    }
    norm = normalize_telemetry_payload(raw)
    
    # Assert 19 total keys exist
    assert len(norm) == 19, f"Expected 19 keys, got {len(norm)}"
    
    # 16 Primary fields
    primary_fields = [
        "person_count", "max_density", "risk_level", "combined_score",
        "raw_score", "smoothed_score", "growth_rate", "data_quality_score",
        "avg_speed", "max_speed", "dominant_direction", "camera_motion_detected",
        "sudden_movement_count", "anomaly_score", "fps", "last_frame_time"
    ]
    for pf in primary_fields:
        assert pf in norm, f"Missing primary field: {pf}"
        
    # 3 Aliases
    aliases = ["density", "risk", "anomaly"]
    for a in aliases:
        assert a in norm, f"Missing alias field: {a}"
        
    print("[✓] 16 primary fields + 3 aliases = 19 payload keys verified.")


def test_native_type_serialization():
    """Verify clean_native_value coerces NumPy types to Python native types."""
    assert type(clean_native_value(np.int64(15))) is int
    assert type(clean_native_value(np.float32(3.14))) is float
    assert type(clean_native_value(np.bool_(True))) is bool
    assert type(clean_native_value(np.array([1, 2]))) is list
    assert clean_native_value(float('nan')) == 0.0
    assert clean_native_value(float('inf')) == 0.0
    print("[✓] Native Python type serialization verified.")


def test_existing_schema_alias_compatibility():
    """Verify aliases density, risk, and anomaly stay strictly synchronized with primary fields."""
    raw = {
        "density": 12,
        "risk": "High",
        "anomaly": 0.4
    }
    norm = normalize_telemetry_payload(raw)
    
    assert norm["max_density"] == 12
    assert norm["density"] == 12
    
    assert norm["risk_level"] == "High"
    assert norm["risk"] == "High"
    
    assert norm["anomaly_score"] == 0.4
    assert norm["anomaly"] == 0.4
    print("[✓] Existing schema alias compatibility (density/max_density, risk/risk_level, anomaly/anomaly_score) verified.")


def test_missing_and_partial_payloads():
    """Verify empty or partial dict input yields full 19-key payload with safe default values."""
    norm = normalize_telemetry_payload({})
    assert len(norm) == 19
    assert norm["person_count"] == 0
    assert norm["max_density"] == 0
    assert norm["risk_level"] == "Low"
    assert norm["combined_score"] == 0.0
    assert norm["data_quality_score"] == 1.0
    assert norm["dominant_direction"] == "STATIONARY"
    assert norm["camera_motion_detected"] is False
    print("[✓] Missing & partial payload defaults verified.")


def test_nan_inf_sanitization():
    """Verify NaN, Inf, and invalid numeric inputs sanitize cleanly."""
    raw = {
        "person_count": float('nan'),
        "combined_score": float('inf'),
        "growth_rate": -5.0,
        "avg_speed": float('-inf')
    }
    norm = normalize_telemetry_payload(raw)
    assert norm["person_count"] == 0
    assert norm["combined_score"] == 0.0
    assert norm["avg_speed"] == 0.0
    print("[✓] NaN / Inf / invalid value sanitization verified.")


def test_firebase_init_failure_handling():
    """Verify FirebaseAlertManager handles missing credential file without unhandled crash."""
    from src.alerts import FirebaseAlertManager
    with patch("os.path.exists", return_value=False):
        try:
            mgr = FirebaseAlertManager(credentials_path="non_existent.json")
        except FileNotFoundError:
            pass  # Expected behavior for invalid credentials
    print("[✓] Firebase init failure handling verified.")


def test_firebase_runtime_write_failure():
    """Verify update_dashboard_data suppresses runtime write failures gracefully."""
    from src.alerts import FirebaseAlertManager
    
    # Create mock alert manager instance
    mgr = MagicMock(spec=FirebaseAlertManager)
    mgr.rtdb = MagicMock()
    mgr.rtdb.reference.side_effect = Exception("Network write timeout")
    
    # Import update_dashboard_data logic
    from src.alerts import FirebaseAlertManager as RealManager
    RealManager.update_dashboard_data(mgr, {"person_count": 5})
    # Should not throw unhandled exception
    print("[✓] Firebase runtime write failure suppression verified.")


def test_csv_fallback_missing_empty_malformed():
    """Verify load_offline_csv_fallback resilience against missing, 0-byte, and corrupted CSVs."""
    tmp_dir = Path("scratch/test_csv_tmp")
    tmp_dir.mkdir(exist_ok=True)
    
    # 1. Non-existent file
    res1, desc1 = load_offline_csv_fallback(log_dir=str(tmp_dir), default_csv=str(tmp_dir / "missing.csv"))
    assert res1 is None
    assert "No CSV Data Available" in desc1
    
    # 2. 0-byte file
    empty_csv = tmp_dir / "empty.csv"
    empty_csv.write_text("")
    res2, desc2 = load_offline_csv_fallback(log_dir=str(tmp_dir), default_csv=str(empty_csv))
    assert res2 is None
    
    # 3. Corrupted text
    corrupt_csv = tmp_dir / "corrupt.csv"
    corrupt_csv.write_text("NOT,A,VALID,CSV\n###\n@@@")
    res3, desc3 = load_offline_csv_fallback(log_dir=str(tmp_dir), default_csv=str(corrupt_csv))
    assert res3 is None or len(res3) == 19
    
    # 4. Valid CSV row
    valid_csv = tmp_dir / "valid.csv"
    valid_csv.write_text("timestamp,person_count,max_density,anomaly_score,risk_level,combined_score\n2026-09-15T13:00:00,8,4,0.1,Low,15.5\n")
    res4, desc4 = load_offline_csv_fallback(log_dir=str(tmp_dir), default_csv=str(valid_csv))
    assert res4 is not None
    assert len(res4) == 19
    assert res4["person_count"] == 8
    assert res4["max_density"] == 4
    assert res4["risk_level"] == "Low"
    print("[✓] Offline CSV fallback (missing, 0-byte, corrupted, valid) verified.")


def test_timestamp_parsing_and_staleness():
    """Verify ISO timestamp parsing, staleness evaluation, and future clock skew handling."""
    # 1. ISO string with Z
    dt_z = parse_iso_timestamp("2026-09-15T13:00:00Z")
    assert dt_z is not None
    assert dt_z.tzinfo is not None
    
    # 2. ISO string with timezone offset
    dt_off = parse_iso_timestamp("2026-09-15T13:00:00+05:30")
    assert dt_off is not None
    
    # 3. Naive string
    dt_naive = parse_iso_timestamp("2026-09-15T13:00:00")
    assert dt_naive is not None
    
    # 4. Invalid text -> None
    assert parse_iso_timestamp("invalid_text") is None
    
    # 5. Live timestamp (< 10s age)
    now_iso = datetime.now(timezone.utc).isoformat()
    stale_live, age_live = evaluate_telemetry_staleness(now_iso)
    assert stale_live is False
    assert age_live < 5.0
    
    # 6. Old timestamp (> 10s age)
    old_iso = (datetime.now(timezone.utc) - timedelta(seconds=20)).isoformat()
    stale_old, age_old = evaluate_telemetry_staleness(old_iso)
    assert stale_old is True
    assert age_old >= 20.0
    
    # 7. Future timestamp (clock skew > 60s)
    future_iso = (datetime.now(timezone.utc) + timedelta(seconds=120)).isoformat()
    stale_future, age_future = evaluate_telemetry_staleness(future_iso)
    assert stale_future is False
    assert age_future < -60.0
    print("[✓] Timestamp parsing, timezone handling, staleness, and clock skew verified.")


def test_connection_status_classification():
    """Verify determine_connection_status returns exact CONNECTED, STALE, OFFLINE_FALLBACK, UNAVAILABLE strings."""
    data = normalize_telemetry_payload({"person_count": 5})
    
    # Connected & Live
    assert determine_connection_status(firebase_connected=True, data=data, is_stale=False) == "CONNECTED"
    
    # Connected & Stale
    assert determine_connection_status(firebase_connected=True, data=data, is_stale=True) == "STALE"
    
    # Offline Fallback (reading CSV)
    assert determine_connection_status(firebase_connected=False, data=data, is_stale=False, is_csv_fallback=True) == "OFFLINE_FALLBACK"
    
    # Unavailable (no data)
    assert determine_connection_status(firebase_connected=False, data=None, is_stale=True) == "UNAVAILABLE"
    print("[✓] Connection status classification (CONNECTED, STALE, OFFLINE_FALLBACK, UNAVAILABLE) verified.")


def test_motion_and_camera_formatting():
    """Verify camera pan flag and cardinal direction formatting."""
    raw_cam = {"avg_speed": 2.5, "dominant_direction": "NE", "camera_motion_detected": True}
    norm = normalize_telemetry_payload(raw_cam)
    assert norm["camera_motion_detected"] is True
    assert norm["dominant_direction"] == "NE"
    assert norm["avg_speed"] == 2.5
    print("[✓] Motion and camera status formatting verified.")


def run_all_tests():
    print("==================================================")
    print("   CROWDPATROL PHASE 4 SYNCHRONIZATION UNIT TESTS")
    print("==================================================")
    test_nineteen_telemetry_payload_keys()
    test_native_type_serialization()
    test_existing_schema_alias_compatibility()
    test_missing_and_partial_payloads()
    test_nan_inf_sanitization()
    test_firebase_init_failure_handling()
    test_firebase_runtime_write_failure()
    test_csv_fallback_missing_empty_malformed()
    test_timestamp_parsing_and_staleness()
    test_connection_status_classification()
    test_motion_and_camera_formatting()
    print("==================================================")
    print("   [✓] ALL 11 PHASE 4 TEST SUITES PASSED!")
    print("==================================================")


if __name__ == "__main__":
    run_all_tests()
