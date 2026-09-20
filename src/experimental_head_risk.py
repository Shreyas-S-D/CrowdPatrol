"""
CrowdPatrol Phase 4 — Experimental Head Risk Adapter Module.
Converts visible head count, active head tracks, head spatial concentration,
and motion anomaly metrics into a dynamic experimental head-density risk proxy (0-100 scale).

IMPORTANT: This is an experimental proxy for head-based crowd monitoring research.
Does NOT modify or replace production RiskAssessor.
Does NOT guarantee stampede prediction or official safety warnings.
"""

import numpy as np


class ExperimentalHeadRiskAdapter:
    """
    Experimental Head-Density Risk Adapter.
    Translates head spatial density, head count volume, and motion anomaly
    into a continuous experimental risk score bounded [0, 100].
    """
    def __init__(self, alpha: float = 0.25):
        self.alpha = alpha
        self.smoothed_score = None
        
    @staticmethod
    def _compute_density_subindex(max_cell_heads: int) -> float:
        """Piecewise continuous normalization of peak cell head density to [0, 100]."""
        d = float(max_cell_heads)
        if d <= 0:
            return 0.0
        elif d <= 5.0:
            return (d / 5.0) * 25.0
        elif d <= 15.0:
            return 25.0 + ((d - 5.0) / 10.0) * 40.0
        elif d <= 30.0:
            return 65.0 + ((d - 15.0) / 15.0) * 35.0
        else:
            return 100.0

    @staticmethod
    def _compute_volume_subindex(head_count: int) -> float:
        """Piecewise continuous normalization of head volume to [0, 100]."""
        v = float(head_count)
        if v <= 0:
            return 0.0
        elif v <= 10.0:
            return (v / 10.0) * 20.0
        elif v <= 40.0:
            return 20.0 + ((v - 10.0) / 30.0) * 50.0
        elif v <= 80.0:
            return 70.0 + ((v - 40.0) / 40.0) * 30.0
        else:
            return 100.0

    @staticmethod
    def _compute_motion_subindex(anomaly_score: float) -> float:
        """Normalizes motion anomaly score to [0, 100]."""
        a = float(anomaly_score)
        if a <= 0.0:
            return 0.0
        elif a <= 1.0:
            return a * 100.0
        else:
            return min(100.0, a * 10.0)

    def calculate_experimental_head_risk(
        self,
        total_heads: int,
        max_head_cell: int,
        frame_idx: int = 0,
        anomaly_score: float = 0.0,
        visible_heads: int = None
    ) -> dict:
        """
        Calculates experimental risk score based on head spatial density, head count, and motion anomaly.
        Returns dictionary exposing raw score, smoothed score, sub-indices, risk level, and component counts.
        """
        head_volume = visible_heads if visible_heads is not None else total_heads
        
        s_density = self._compute_density_subindex(max_head_cell)
        s_volume = self._compute_volume_subindex(head_volume)
        s_motion = self._compute_motion_subindex(anomaly_score)
        
        if anomaly_score > 0.001:
            w_d, w_v, w_m = 0.50, 0.35, 0.15
            raw_score = w_d * s_density + w_v * s_volume + w_m * s_motion
        else:
            w_d, w_v, w_m = 0.60, 0.40, 0.0
            raw_score = w_d * s_density + w_v * s_volume
            
        raw_score = float(np.clip(raw_score, 0.0, 100.0))
        
        if self.smoothed_score is None:
            self.smoothed_score = raw_score
        else:
            self.smoothed_score = self.alpha * raw_score + (1.0 - self.alpha) * self.smoothed_score
            
        smoothed_val = float(np.clip(self.smoothed_score, 0.0, 100.0))
        
        if smoothed_val < 30.0:
            level = "LOW"
        elif smoothed_val < 65.0:
            level = "MEDIUM"
        else:
            level = "HIGH"
            
        return {
            "risk_label": "EXPERIMENTAL HEAD-DENSITY RISK (PROXY)",
            "risk_level": level,
            "raw_score": float(raw_score),
            "smoothed_score": float(smoothed_val),
            "head_count": total_heads,
            "visible_heads": head_volume,
            "max_cell_heads": max_head_cell,
            "sub_indices": {
                "density_index": float(s_density),
                "volume_index": float(s_volume),
                "motion_index": float(s_motion)
            }
        }
