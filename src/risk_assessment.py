"""
CrowdPatrol - Risk Assessment Engine (Phase 3 Enhanced)
Multi-factor, configurable, transparent risk scoring engine with temporal EMA smoothing,
hysteresis state machine, camera-motion safety isolation, and estimated data-quality indicators.
"""

import numpy as np
import math
import time
from enum import Enum
from typing import Dict, Tuple, Optional, Any


class RiskLevel(Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


class ScoreEMA:
    """
    Exponential Moving Average for continuous score smoothing.
    Initialized on first frame so smoothed score equals raw score initially.
    """
    def __init__(self, alpha: float = 0.25):
        self.alpha = float(np.clip(alpha, 0.01, 1.0))
        self.smoothed_score: Optional[float] = None

    def update(self, raw_score: float) -> float:
        raw_score = float(np.clip(raw_score, 0.0, 100.0))
        if self.smoothed_score is None:
            self.smoothed_score = raw_score
        else:
            self.smoothed_score = self.alpha * raw_score + (1.0 - self.alpha) * self.smoothed_score
        return float(self.smoothed_score)

    def reset(self):
        self.smoothed_score = None


class HysteresisStateMachine:
    """
    Explicit Hysteresis State Machine preventing label flickering at score thresholds.
    Thresholds:
      - LOW -> MEDIUM at >= 40.0
      - MEDIUM -> LOW below 35.0
      - MEDIUM -> HIGH at >= 70.0
      - HIGH -> MEDIUM below 65.0
      - Direct LOW -> HIGH at >= 70.0
      - Direct HIGH -> LOW below 35.0
    """
    def __init__(self, initial_state: RiskLevel = RiskLevel.LOW):
        self.current_state = initial_state

    def update(self, score: float) -> RiskLevel:
        score = float(np.clip(score, 0.0, 100.0))
        
        if self.current_state == RiskLevel.LOW:
            if score >= 70.0:
                self.current_state = RiskLevel.HIGH
            elif score >= 40.0:
                self.current_state = RiskLevel.MEDIUM
                
        elif self.current_state == RiskLevel.MEDIUM:
            if score >= 70.0:
                self.current_state = RiskLevel.HIGH
            elif score < 35.0:
                self.current_state = RiskLevel.LOW
                
        elif self.current_state == RiskLevel.HIGH:
            if score < 35.0:
                self.current_state = RiskLevel.LOW
            elif score < 65.0:
                self.current_state = RiskLevel.MEDIUM
                
        return self.current_state

    def reset(self, initial_state: RiskLevel = RiskLevel.LOW):
        self.current_state = initial_state


class RiskAssessor:
    """
    Risk Assessment Engine supporting legacy mode and Phase 3 Multi-Factor Enhanced mode.
    """
    DEFAULT_WEIGHTS = {
        "density": 0.35,
        "density_growth": 0.15,
        "motion_speed": 0.15,
        "flow_conflict": 0.15,
        "accel_spikes": 0.10,
        "local_anomaly": 0.10
    }

    DEFAULT_CAPS = {
        "density_cap": 30.0,          # persons per cell
        "density_growth_cap": 10.0,   # persons / second
        "motion_speed_cap": 3.0,      # px/f average magnitude
        "local_anomaly_cap": 3.0,     # px/f max-avg difference
        "accel_spike_cap": 4.0        # spike cell count (out of 16)
    }

    def __init__(
        self,
        density_thresholds: Optional[Dict[str, int]] = None,
        use_enhanced_scoring: bool = True,
        weights: Optional[Dict[str, float]] = None,
        caps: Optional[Dict[str, float]] = None,
        ema_alpha: float = 0.25
    ):
        self.thresholds = density_thresholds or {"low": 5, "medium": 15, "high": 30}
        self.use_enhanced_scoring = use_enhanced_scoring
        
        # Merge custom weights / caps with defaults
        self.weights = {**self.DEFAULT_WEIGHTS, **(weights or {})}
        self.caps = {**self.DEFAULT_CAPS, **(caps or {})}
        
        # Validate weights sum to 1.0
        total_w = sum(self.weights.values())
        if not math.isclose(total_w, 1.0, rel_tol=1e-3):
            # Normalize user weights if invalid
            self.weights = {k: v / total_w for k, v in self.weights.items()}

        # Temporal components
        self.ema = ScoreEMA(alpha=ema_alpha)
        self.state_machine = HysteresisStateMachine(RiskLevel.LOW)
        
        # Rate calculation state
        self.prev_max_density: Optional[float] = None
        self.prev_timestamp: Optional[float] = None
        
        # Legacy centroid state
        self.previous_centroids = {}
        self.anomaly_threshold = 10  # pixels/frame

    def reset_temporal_state(self):
        """Reset EMA, hysteresis state machine, and growth rate tracking."""
        self.ema.reset()
        self.state_machine.reset(RiskLevel.LOW)
        self.prev_max_density = None
        self.prev_timestamp = None
        self.previous_centroids = {}

    def calculate_movement_anomaly(self, tracks, frame_shape) -> float:
        """Legacy track centroid movement anomaly score."""
        current_centroids = {}
        anomaly_score = 0
        
        for track in tracks:
            x1, y1, x2, y2, track_id = track
            centroid = np.array([(x1 + x2) / 2, (y1 + y2) / 2])
            current_centroids[track_id] = centroid
            
            if track_id in self.previous_centroids:
                velocity = np.linalg.norm(centroid - self.previous_centroids[track_id])
                if velocity > self.anomaly_threshold:
                    anomaly_score += 1
        
        self.previous_centroids = current_centroids
        return min(anomaly_score / max(len(tracks), 1), 1.0)

    def assess_risk(self, max_density: int, anomaly_score: float) -> Tuple[RiskLevel, float]:
        """
        Legacy risk assessment method. Preserved for 100% backward compatibility.
        """
        density_risk = 0
        if max_density >= self.thresholds["high"]:
            density_risk = 3
        elif max_density >= self.thresholds["medium"]:
            density_risk = 2
        elif max_density >= self.thresholds["low"]:
            density_risk = 1
        
        combined_score = (density_risk / 3) * 70 + anomaly_score * 30
        
        if combined_score >= 70:
            return RiskLevel.HIGH, combined_score
        elif combined_score >= 40:
            return RiskLevel.MEDIUM, combined_score
        else:
            return RiskLevel.LOW, combined_score

    def _sanitize_input(self, val: Any, default: float = 0.0) -> float:
        """Sanitize inputs against NaN, Inf, and negative values."""
        try:
            fval = float(val)
            if math.isnan(fval) or math.isinf(fval):
                return default
            return fval
        except (ValueError, TypeError):
            return default

    def assess_frame(
        self,
        max_density: float,
        motion_summary: Optional[Dict] = None,
        tracks: Optional[list] = None,
        timestamp: Optional[float] = None,
        anomaly_score: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Phase 3 Enhanced Risk Assessment pipeline.
        Calculates normalized sub-scores, handles camera motion safety,
        re-normalizes weights, applies EMA smoothing & hysteresis.
        """
        # If enhanced mode disabled, fallback cleanly to legacy
        if not self.use_enhanced_scoring:
            if anomaly_score is None:
                anomaly_score = self.calculate_movement_anomaly(tracks or [], (720, 1280))
            level, score = self.assess_risk(int(max_density), anomaly_score)
            return {
                "risk": level.value,
                "combined_score": float(score),
                "raw_score": float(score),
                "smoothed_score": float(score),
                "data_quality_score": 1.0,
                "growth_rate": 0.0,
                "factor_scores": {"density": (level.value == "High") * 100.0, "legacy_anomaly": anomaly_score * 100.0},
                "active_weights": {"density": 0.7, "legacy_anomaly": 0.3},
                "risk_enum": level
            }

        # 1. Sanitize density & timestamp
        max_density = max(0.0, self._sanitize_input(max_density))
        curr_time = timestamp if timestamp is not None else time.time()
        
        # 2. Compute Density Growth Rate (persons/second)
        growth_rate = 0.0
        if self.prev_max_density is not None and self.prev_timestamp is not None:
            dt = curr_time - self.prev_timestamp
            if dt > 1e-4:
                delta_d = max_density - self.prev_max_density
                growth_rate = max(0.0, delta_d / dt)  # Only positive influx adds risk
        
        self.prev_max_density = max_density
        self.prev_timestamp = curr_time

        # 3. Calculate Raw Sub-scores [0.0, 100.0]
        density_sub = float(np.clip((max_density / self.caps["density_cap"]) * 100.0, 0.0, 100.0))
        growth_sub = float(np.clip((growth_rate / self.caps["density_growth_cap"]) * 100.0, 0.0, 100.0))
        
        factor_scores = {
            "density": density_sub,
            "density_growth": growth_sub,
            "motion_speed": 0.0,
            "flow_conflict": 0.0,
            "accel_spikes": 0.0,
            "local_anomaly": 0.0
        }

        # Determine motion validity & camera motion status
        has_valid_motion = (
            motion_summary is not None 
            and isinstance(motion_summary, dict) 
            and "avg_speed" in motion_summary
        )
        camera_moving = has_valid_motion and bool(motion_summary.get("camera_motion_detected", False))

        # 4. Active Factors & Weight Re-Normalization
        active_weights = {}
        data_quality_score = 1.0

        if not has_valid_motion:
            # Case A: Missing or invalid motion data -> Exclude motion factors
            active_factors = ["density", "density_growth"]
            data_quality_score = 0.50
        elif camera_moving:
            # Case B: Camera motion detected -> EXCLUDE motion-derived factors for 100% safety
            # Motion vectors contain ego-motion noise. Rely only on density & growth.
            active_factors = ["density", "density_growth"]
            data_quality_score = 0.75
        else:
            # Case C: Valid static camera motion data -> Use all 6 factors
            active_factors = ["density", "density_growth", "motion_speed", "flow_conflict", "accel_spikes", "local_anomaly"]
            data_quality_score = 1.00
            
            # Extract optical flow motion metrics safely
            avg_speed = max(0.0, self._sanitize_input(motion_summary.get("avg_speed", 0.0)))
            max_speed = max(0.0, self._sanitize_input(motion_summary.get("max_speed", 0.0)))
            coherence = float(np.clip(self._sanitize_input(motion_summary.get("coherence", 1.0), 1.0), 0.0, 1.0))
            sudden_count = max(0.0, self._sanitize_input(motion_summary.get("sudden_movement_count", 0)))
            
            # Compute motion sub-scores
            factor_scores["motion_speed"] = float(np.clip((avg_speed / self.caps["motion_speed_cap"]) * 100.0, 0.0, 100.0))
            factor_scores["flow_conflict"] = float(np.clip((1.0 - coherence) * 100.0, 0.0, 100.0))
            factor_scores["accel_spikes"] = float(np.clip((sudden_count / self.caps["accel_spike_cap"]) * 100.0, 0.0, 100.0))
            factor_scores["local_anomaly"] = float(np.clip(((max_speed - avg_speed) / self.caps["local_anomaly_cap"]) * 100.0, 0.0, 100.0))

        # Re-normalize active weights so they sum to exactly 1.0
        sum_active_weights = sum(self.weights[k] for k in active_factors)
        if sum_active_weights > 0:
            for k in active_factors:
                active_weights[k] = self.weights[k] / sum_active_weights
        else:
            active_weights["density"] = 1.0

        # Zero out inactive factors in weights dict
        for k in self.DEFAULT_WEIGHTS:
            if k not in active_weights:
                active_weights[k] = 0.0

        # 5. Compute Raw Score
        raw_score = sum(active_weights[k] * factor_scores[k] for k in active_factors)
        raw_score = float(np.clip(raw_score, 0.0, 100.0))

        # 6. Apply Temporal EMA & Hysteresis State Machine
        smoothed_score = self.ema.update(raw_score)
        risk_level = self.state_machine.update(smoothed_score)

        return {
            "risk": risk_level.value,
            "combined_score": float(round(smoothed_score, 2)),  # Backward compatibility key
            "raw_score": float(round(raw_score, 2)),
            "smoothed_score": float(round(smoothed_score, 2)),
            "data_quality_score": float(round(data_quality_score, 2)),
            "growth_rate": float(round(growth_rate, 2)),
            "factor_scores": {k: float(round(v, 2)) for k, v in factor_scores.items()},
            "active_weights": {k: float(round(v, 4)) for k, v in active_weights.items()},
            "risk_enum": risk_level
        }