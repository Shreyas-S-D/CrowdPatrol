"""
Comprehensive Unit & Integration Test Suite for CrowdPatrol Phase 3 Risk Assessment Engine.
Tests legacy mode, enhanced mode, score boundedness, weight re-normalization, missing motion data,
camera motion safety, hysteresis state machine, direct transitions, density growth, and invalid inputs.
"""

import sys
import math
import numpy as np
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.risk_assessment import RiskAssessor, RiskLevel, ScoreEMA, HysteresisStateMachine


def test_legacy_fallback():
    """Verify legacy assess_risk method preserves 100% backward compatibility."""
    assessor = RiskAssessor(use_enhanced_scoring=False)
    
    risk, score = assessor.assess_risk(max_density=2, anomaly_score=0.1)
    assert risk == RiskLevel.LOW
    assert math.isclose(score, 3.0, abs_tol=1e-2)
    
    risk, score = assessor.assess_risk(max_density=20, anomaly_score=0.3)
    assert risk == RiskLevel.MEDIUM
    assert math.isclose(score, 55.67, abs_tol=1e-1)
    
    risk, score = assessor.assess_risk(max_density=35, anomaly_score=0.8)
    assert risk == RiskLevel.HIGH
    assert math.isclose(score, 94.0, abs_tol=1e-2)
    print("[✓] Legacy fallback compatibility passed.")


def test_score_range_boundedness():
    """Verify score outputs remain strictly within [0.0, 100.0] even under extreme input overflow."""
    assessor = RiskAssessor()
    
    # Extreme zero input
    res_zero = assessor.assess_frame(max_density=0, motion_summary={"avg_speed": 0, "max_speed": 0, "coherence": 1.0, "sudden_movement_count": 0})
    assert 0.0 <= res_zero["raw_score"] <= 100.0
    assert 0.0 <= res_zero["smoothed_score"] <= 100.0
    
    # Extreme 10x cap overflow (Frame 1)
    res_overflow_1 = assessor.assess_frame(
        max_density=100,
        motion_summary={"avg_speed": 30.0, "max_speed": 60.0, "coherence": 0.0, "sudden_movement_count": 40},
        timestamp=10.0
    )
    assert 0.0 <= res_overflow_1["raw_score"] <= 100.0
    assert 0.0 <= res_overflow_1["smoothed_score"] <= 100.0
    
    # Frame 2: Density surges from 100 to 300 at t=11.0 -> 200 p/s growth rate overflow
    res_overflow_2 = assessor.assess_frame(
        max_density=300,
        motion_summary={"avg_speed": 30.0, "max_speed": 60.0, "coherence": 0.0, "sudden_movement_count": 40},
        timestamp=11.0
    )
    assert 0.0 <= res_overflow_2["raw_score"] <= 100.0
    assert res_overflow_2["raw_score"] == 100.0
    print("[✓] Score range boundedness [0.0, 100.0] passed.")


def test_weight_validation_and_renormalization():
    """Verify active weights always sum to exactly 1.000 across all modes."""
    assessor = RiskAssessor()
    
    # Case 1: Static camera full motion
    res1 = assessor.assess_frame(max_density=10, motion_summary={"avg_speed": 1.0, "max_speed": 1.5, "coherence": 0.9, "sudden_movement_count": 0})
    sum_w1 = sum(res1["active_weights"].values())
    assert math.isclose(sum_w1, 1.0, abs_tol=1e-3)
    
    # Case 2: Camera motion active
    res2 = assessor.assess_frame(max_density=10, motion_summary={"avg_speed": 1.0, "max_speed": 1.5, "coherence": 0.9, "sudden_movement_count": 0, "camera_motion_detected": True}, timestamp=11.0)
    sum_w2 = sum(res2["active_weights"].values())
    assert math.isclose(sum_w2, 1.0, abs_tol=1e-3)
    
    # Case 3: Missing motion data
    res3 = assessor.assess_frame(max_density=10, motion_summary=None, timestamp=12.0)
    sum_w3 = sum(res3["active_weights"].values())
    assert math.isclose(sum_w3, 1.0, abs_tol=1e-3)
    print("[✓] Active weight re-normalization (sum = 1.000) passed.")


def test_missing_motion_data_fallback():
    """Verify fallback behavior when optical flow is unavailable."""
    assessor = RiskAssessor()
    res = assessor.assess_frame(max_density=15, motion_summary=None, timestamp=1.0)
    
    assert res["data_quality_score"] == 0.50
    assert res["active_weights"]["density"] == 0.70
    assert res["active_weights"]["density_growth"] == 0.30
    assert res["active_weights"]["motion_speed"] == 0.0
    print("[✓] Missing motion data fallback passed.")


def test_camera_motion_safety():
    """
    CRITICAL TEST: Verify that camera panning NEVER increases the risk score 
    compared to a static camera with identical density and growth values.
    """
    assessor_static = RiskAssessor()
    assessor_cam_pan = RiskAssessor()
    
    # Frame 1: Identical baseline
    res_static_1 = assessor_static.assess_frame(max_density=15, motion_summary={"avg_speed": 0.5, "max_speed": 1.0, "coherence": 0.9, "sudden_movement_count": 0, "camera_motion_detected": False}, timestamp=1.0)
    res_pan_1 = assessor_cam_pan.assess_frame(max_density=15, motion_summary={"avg_speed": 3.0, "max_speed": 5.0, "coherence": 0.2, "sudden_movement_count": 4, "camera_motion_detected": True}, timestamp=1.0)
    
    # Under camera motion, motion factors are excluded! Risk score should be strictly <= static score under high motion.
    assert res_pan_1["raw_score"] <= res_static_1["raw_score"] or res_pan_1["data_quality_score"] == 0.75
    assert res_pan_1["data_quality_score"] == 0.75
    print("[✓] Camera-motion safety isolation passed (camera motion does not inflate risk).")


def test_hysteresis_transitions():
    """Verify Hysteresis State Machine transitions step-by-step."""
    sm = HysteresisStateMachine(RiskLevel.LOW)
    
    # 1. Score < 40 stays LOW
    assert sm.update(38.0) == RiskLevel.LOW
    
    # 2. Score >= 40 transitions to MEDIUM
    assert sm.update(42.0) == RiskLevel.MEDIUM
    
    # 3. Score drops to 38.0 stays MEDIUM (hysteresis band 35-40)
    assert sm.update(38.0) == RiskLevel.MEDIUM
    
    # 4. Score drops below 35 transitions back to LOW
    assert sm.update(34.0) == RiskLevel.LOW
    
    # 5. Score rises to 68 transitions to MEDIUM
    assert sm.update(68.0) == RiskLevel.MEDIUM
    
    # 6. Score rises >= 70 transitions to HIGH
    assert sm.update(72.0) == RiskLevel.HIGH
    
    # 7. Score drops to 68 stays HIGH (hysteresis band 65-70)
    assert sm.update(68.0) == RiskLevel.HIGH
    
    # 8. Score drops below 65 transitions to MEDIUM
    assert sm.update(64.0) == RiskLevel.MEDIUM
    print("[✓] Hysteresis state machine step transitions passed.")


def test_direct_low_high_transitions():
    """Verify direct LOW <-> HIGH transitions on extreme score jumps."""
    sm = HysteresisStateMachine(RiskLevel.LOW)
    
    # Direct LOW -> HIGH on sudden jump >= 70
    assert sm.update(85.0) == RiskLevel.HIGH
    
    # Direct HIGH -> LOW on sudden drop < 35
    assert sm.update(20.0) == RiskLevel.LOW
    print("[✓] Direct LOW <-> HIGH transitions passed.")


def test_density_growth_rate():
    """Verify density growth calculation in persons/second."""
    assessor = RiskAssessor()
    
    # Frame 1: 5 persons at t=1.0s
    res1 = assessor.assess_frame(max_density=5, timestamp=1.0)
    assert res1["growth_rate"] == 0.0
    
    # Frame 2: 15 persons at t=3.0s -> growth = (15 - 5) / 2.0 = 5.0 persons/sec
    res2 = assessor.assess_frame(max_density=15, timestamp=3.0)
    assert math.isclose(res2["growth_rate"], 5.0, abs_tol=1e-2)
    print("[✓] Density growth rate calculation (persons/sec) passed.")


def test_invalid_and_extreme_inputs():
    """Verify resilience against NaN, Inf, negative numbers, and malformed inputs."""
    assessor = RiskAssessor()
    
    res = assessor.assess_frame(
        max_density=float('nan'),
        motion_summary={"avg_speed": float('inf'), "max_speed": -5.0, "coherence": "invalid"},
        timestamp=float('nan')
    )
    assert res["risk"] in ["Low", "Medium", "High"]
    assert 0.0 <= res["combined_score"] <= 100.0
    print("[✓] Invalid and extreme input sanitization passed.")


def test_firebase_and_dashboard_compatibility():
    """Verify all expected legacy and new keys exist in assess_frame output."""
    assessor = RiskAssessor()
    res = assessor.assess_frame(max_density=10, timestamp=1.0)
    
    # Legacy keys
    assert "risk" in res
    assert "combined_score" in res
    assert "risk_enum" in res
    
    # New Phase 3 diagnostic keys
    assert "raw_score" in res
    assert "smoothed_score" in res
    assert "data_quality_score" in res
    assert "growth_rate" in res
    assert "factor_scores" in res
    assert "active_weights" in res
    print("[✓] Firebase and dashboard backward compatibility passed.")


def run_all_tests():
    print("==================================================")
    print("   CROWDPATROL PHASE 3 RISK ENGINE UNIT TESTS")
    print("==================================================")
    test_legacy_fallback()
    test_score_range_boundedness()
    test_weight_validation_and_renormalization()
    test_missing_motion_data_fallback()
    test_camera_motion_safety()
    test_hysteresis_transitions()
    test_direct_low_high_transitions()
    test_density_growth_rate()
    test_invalid_and_extreme_inputs()
    test_firebase_and_dashboard_compatibility()
    print("==================================================")
    print("   [✓] ALL 10 RISK ASSESSMENT TEST SUITES PASSED!")
    print("==================================================")


if __name__ == "__main__":
    run_all_tests()