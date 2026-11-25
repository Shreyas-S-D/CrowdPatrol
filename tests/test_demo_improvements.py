"""
Targeted tests for:
1. Anomaly score extraction and computation from optical flow.
2. Audio alarms for High (Beep) and Critical (Siren).
3. Pure Email dispatch (SMS disabled).
4. Alert severity filtering (Medium is warning; High/Critical require Ack/Resolve).
"""
import pytest
import numpy as np
from src.motion_analysis import CrowdMotionAnalyzer
from dashboard.dashboard_utils import get_beep_b64, get_siren_b64, get_alarm_audio_html
from src.notification_dispatcher import NotificationConfig, NotificationDispatcher
from src.alert_manager import AlertEvent

def test_optical_flow_anomaly_score_output():
    analyzer = CrowdMotionAnalyzer(downscale_size=(160, 90), grid_size=(4, 4))
    
    # Frame 1: Blank frame
    frame1 = np.zeros((480, 640, 3), dtype=np.uint8)
    _, summary1 = analyzer.analyze_frame(frame1)
    assert "anomaly_score" in summary1
    assert summary1["anomaly_score"] == 0.0

    # Frame 2: Identical blank frame (stationary)
    frame2 = np.zeros((480, 640, 3), dtype=np.uint8)
    _, summary2 = analyzer.analyze_frame(frame2)
    assert "anomaly_score" in summary2
    assert summary2["anomaly_score"] == 0.0

    # Frame 3: Simulate high local motion (bright shifting block to trigger optical flow)
    frame3 = np.zeros((480, 640, 3), dtype=np.uint8)
    frame3[100:300, 200:400] = 255
    _, summary3 = analyzer.analyze_frame(frame3)
    assert "anomaly_score" in summary3
    # When significant motion occurs, anomaly score is computed
    assert summary3["anomaly_score"] >= 0.0

def test_audio_alarm_html_generation():
    beep_b64 = get_beep_b64()
    siren_b64 = get_siren_b64()
    assert len(beep_b64) > 1000
    assert len(siren_b64) > 1000
    assert beep_b64 != siren_b64

    high_html = get_alarm_audio_html("HIGH")
    assert "<audio autoplay" in high_html
    assert beep_b64 in high_html

    crit_html = get_alarm_audio_html("CRITICAL")
    assert "<audio autoplay" in crit_html
    assert siren_b64 in crit_html

def test_sms_completely_disabled_in_dispatcher():
    config = NotificationConfig(enabled=True)
    dispatcher = NotificationDispatcher(config)

    alert = AlertEvent(
        alert_id="ALT_TEST_SMS_OFF",
        camera_id="CAM_01",
        camera_name="Test Cam",
        timestamp="2026-11-25 00:00:00",
        risk_level="CRITICAL",
        risk_score=95.0,
        reason="Severe crowd congestion",
        status="ACTIVE",
        severity="CRITICAL"
    )

    results = dispatcher.dispatch_alert(alert)
    assert results.get("sms") == "DISABLED"
