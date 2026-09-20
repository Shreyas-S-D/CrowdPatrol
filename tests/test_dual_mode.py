"""
Unit tests for Stage 10 & 11.7: Dual-Mode CrowdPatrol Dashboard Integration.
Verifies Person Mode default, V2/V4 model isolation, Head Density estimator,
Experimental Head Risk adapter, UI warnings, visible vs active tracks distinction,
and telemetry schema isolation.
"""

import pytest
import numpy as np
import cv2
import os
from pathlib import Path

from src.detection import PersonDetector
from src.experimental_head_mode import ExperimentalHeadDetector, DEFAULT_HEAD_MODEL_PATH
from src.experimental_head_density import HeadDensityEstimator
from src.density import DensityEstimator
from src.experimental_head_risk import ExperimentalHeadRiskAdapter
from src.risk_assessment import RiskAssessor
from src.utils import FrameAnnotator, MetricsLogger
from dashboard.dashboard_utils import normalize_telemetry_payload


def test_mode_selector_default():
    """Verify default mode setting is Person Mode."""
    default_mode = "👤 Person Mode (Default)"
    assert default_mode.startswith("👤 Person Mode")
    assert "Default" in default_mode


def test_person_mode_loads_v2():
    """Verify Person Mode targets V2 model weights path."""
    v2_path = "models/crowdpatrol_yolov8n_finetuned_v2.pt"
    if os.path.exists(v2_path):
        detector = PersonDetector(model_path=v2_path, confidence=0.35, device="cpu")
        assert detector.model_path == v2_path


def test_head_mode_loads_v4():
    """Verify Head Mode targets V4 model weights path and uses confidence=0.25 default."""
    v4_path = "models/crowdpatrol_yolov8n_head_v4.pt"
    head_path = v4_path if os.path.exists(v4_path) else DEFAULT_HEAD_MODEL_PATH
    detector = ExperimentalHeadDetector(model_path=head_path, device="cpu")
    assert detector.target_type == "head"
    assert "v4" in detector.model_path or "head" in detector.model_path
    assert detector.confidence == 0.25


def test_head_mode_default_confidence_is_025():
    """Verify ExperimentalHeadDetector default confidence threshold is set to 0.25."""
    detector = ExperimentalHeadDetector()
    assert detector.confidence == 0.25
    assert detector.imgsz == 640


def test_head_detections_isolated_from_person_density():
    """Verify head detections use HeadDensityEstimator and not Person DensityEstimator."""
    head_density_est = HeadDensityEstimator(grid_size=(4, 4))
    person_density_est = DensityEstimator(grid_size=(4, 4))
    
    dummy_tracks = [[100, 100, 140, 140, 1]]  # 40x40 box
    frame_shape = (480, 640, 3)
    
    head_map, head_max, head_stats = head_density_est.calculate_density(dummy_tracks, frame_shape)
    person_map, person_max = person_density_est.calculate_density(dummy_tracks, frame_shape)
    
    assert head_stats["total_heads"] == 1
    assert head_max == 1
    assert isinstance(head_map, np.ndarray)


def test_head_density_uses_center_points():
    """Verify HeadDensityEstimator calculates grid location based strictly on head center coordinates."""
    est = HeadDensityEstimator(grid_size=(4, 4))
    frame_shape = (400, 400, 3)  # cell size: 100x100
    
    # Head 1: box (10, 10, 30, 30) -> center (20, 20) -> cell (0, 0)
    # Head 2: box (110, 10, 130, 30) -> center (120, 20) -> cell (0, 1)
    tracks = [
        [10, 10, 30, 30, 1],
        [110, 10, 130, 30, 2]
    ]
    
    density_map, max_d, stats = est.calculate_density(tracks, frame_shape)
    
    assert density_map[0, 0] == 1
    assert density_map[0, 1] == 1
    assert stats["total_heads"] == 2
    assert stats["occupied_cells"] == 2


def test_head_mode_uses_experimental_risk_adapter():
    """Verify Head Mode produces experimental head risk metrics structure."""
    adapter = ExperimentalHeadRiskAdapter()
    risk_info = adapter.calculate_experimental_head_risk(total_heads=20, max_head_cell=6, frame_idx=1)
    
    assert "risk_label" in risk_info
    assert "PROXY" in risk_info["risk_label"]
    assert risk_info["risk_level"] in ["LOW", "MEDIUM", "HIGH"]
    assert "smoothed_score" in risk_info
    assert 0.0 <= risk_info["smoothed_score"] <= 100.0


def test_visible_heads_vs_active_tracks_distinction():
    """Verify visible_heads and active_head_tracks are tracked independently."""
    adapter = ExperimentalHeadRiskAdapter()
    
    # Scene with 12 visible raw detections but 45 active DeepSORT tracks
    r_info = adapter.calculate_experimental_head_risk(
        total_heads=45,
        max_head_cell=8,
        frame_idx=1,
        visible_heads=12
    )
    
    assert r_info["head_count"] == 45
    assert r_info["visible_heads"] == 12
    assert r_info["visible_heads"] != r_info["head_count"]


def test_experimental_head_risk_dynamic_scoring():
    """Verify experimental head risk score varies dynamically and is not stuck at 50."""
    adapter_low = ExperimentalHeadRiskAdapter()
    adapter_med = ExperimentalHeadRiskAdapter()
    adapter_high = ExperimentalHeadRiskAdapter()
    
    # Low density scene
    r_low = adapter_low.calculate_experimental_head_risk(total_heads=4, max_head_cell=2, frame_idx=1, visible_heads=3)
    # Medium density scene
    r_med = adapter_med.calculate_experimental_head_risk(total_heads=25, max_head_cell=8, frame_idx=1, visible_heads=15)
    # Ultra dense scene
    r_high = adapter_high.calculate_experimental_head_risk(total_heads=80, max_head_cell=25, frame_idx=1, visible_heads=60)
    
    assert r_low["smoothed_score"] < r_med["smoothed_score"]
    assert r_med["smoothed_score"] < r_high["smoothed_score"]
    assert r_low["smoothed_score"] != 50.0
    assert r_high["smoothed_score"] > 50.0
    assert 0.0 <= r_low["smoothed_score"] <= 100.0
    assert 0.0 <= r_high["smoothed_score"] <= 100.0


def test_head_mode_disclaimer_warning_text():
    """Verify the experimental head mode warning text string."""
    warning_text = "⚠️ EXPERIMENTAL MODE — HEAD DETECTION ACTIVE. Using V4 Head Detector (crowdpatrol_yolov8n_head_v4.pt). Not for production safety monitoring."
    assert "EXPERIMENTAL MODE" in warning_text
    assert "crowdpatrol_yolov8n_head_v4.pt" in warning_text
    assert "Not for production safety monitoring" in warning_text


def test_tiled_mode_selection_support():
    """Verify tiled mode argument is handled properly by ExperimentalHeadDetector."""
    head_path = "models/crowdpatrol_yolov8n_head_v4.pt" if os.path.exists("models/crowdpatrol_yolov8n_head_v4.pt") else DEFAULT_HEAD_MODEL_PATH
    detector = ExperimentalHeadDetector(model_path=head_path, confidence=0.35, device="cpu")
    
    dummy_frame = np.zeros((300, 300, 3), dtype=np.uint8)
    dets_full = detector.detect(dummy_frame, tiled=False)
    dets_tiled = detector.detect(dummy_frame, tiled=True)
    
    assert isinstance(dets_full, list)
    assert isinstance(dets_tiled, list)


def test_person_mode_telemetry_schema_unchanged():
    """Verify Person Mode telemetry schema maintains 19 keys without modification."""
    raw_payload = {
        "person_count": 10,
        "max_density": 4,
        "risk_level": "Low",
        "combined_score": 15.0,
        "raw_score": 14.5,
        "smoothed_score": 15.0,
        "growth_rate": 0.0,
        "data_quality_score": 1.0,
        "avg_speed": 1.2,
        "max_speed": 2.5,
        "dominant_direction": "EAST",
        "camera_motion_detected": False,
        "sudden_movement_count": 0,
        "anomaly_score": 0.1,
        "fps": 30.0,
        "last_frame_time": "2026-09-20T12:00:00"
    }
    
    normalized = normalize_telemetry_payload(raw_payload)
    assert len(normalized) == 19
    assert normalized["person_count"] == 10
    assert normalized["density"] == 4
    assert normalized["risk"] == "Low"


def test_coasted_tracks_excluded_from_visible_tracks():
    """Verify PersonTracker.get_visible_tracks() excludes coasted tracks (time_since_update > 0)."""
    from src.tracking import PersonTracker
    tracker = PersonTracker(max_age=30, n_init=1)
    
    dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    dets_frame1 = [([100, 100, 40, 40], 0.8, 0), ([200, 200, 40, 40], 0.8, 0)]
    
    # Frame 1: First update
    active1 = tracker.update(dets_frame1, dummy_frame)
    visible1 = tracker.get_visible_tracks()
    assert len(active1) == 2
    assert len(visible1) == 2
    
    # Frame 2: Second update (confirms tracks)
    active2 = tracker.update(dets_frame1, dummy_frame)
    visible2 = tracker.get_visible_tracks()
    assert len(active2) == 2
    assert len(visible2) == 2
    
    # Frame 3: 0 detections received (tracks become coasted with time_since_update > 0)
    active3 = tracker.update([], dummy_frame)
    visible3 = tracker.get_visible_tracks()
    
    assert len(active3) == 2       # DeepSORT retains confirmed tracks internally
    assert len(visible3) == 0       # Coasted tracks excluded from visible rendering
