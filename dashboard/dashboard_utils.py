"""
CrowdPatrol Phase 4 - Telemetry & Dashboard Helper Module
Decouples Streamlit rendering from telemetry processing.
Handles payload normalization (16 primary fields + 3 aliases = 19 keys),
native type coercion, robust ISO timestamp parsing, staleness evaluation,
and resilient offline CSV fallback loading.
"""

import os
import math
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Tuple, Optional
import numpy as np


def clean_native_value(val: Any, default: Any = 0.0) -> Any:
    """Coerce NumPy / scalar / invalid values to native Python types cleanly."""
    if val is None:
        return default
    
    # Handle booleans first (since np.bool_ / bool are subclasses of integer in python/numpy)
    if isinstance(val, (bool, np.bool_)):
        return bool(val)
    elif isinstance(val, (np.integer,)):
        return int(val)
    elif isinstance(val, (np.floating,)):
        fval = float(val)
        if math.isnan(fval) or math.isinf(fval):
            return default
        return fval
    elif isinstance(val, np.ndarray):
        return val.tolist()
    elif isinstance(val, float):
        if math.isnan(val) or math.isinf(val):
            return default
        return float(val)
    elif isinstance(val, int):
        return int(val)
    elif isinstance(val, str):
        return str(val)
    
    try:
        fval = float(val)
        if math.isnan(fval) or math.isinf(fval):
            return default
        return fval
    except (ValueError, TypeError):
        return str(val)


def normalize_telemetry_payload(raw_dict: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Normalizes input dictionary into a complete 19-key payload:
      - 16 Primary Telemetry Fields
      - 3 Backward-Compatibility Aliases (density, risk, anomaly)
    """
    if not isinstance(raw_dict, dict):
        raw_dict = {}

    # 1. Resolve Primary & Alias mappings safely
    max_density_val = int(clean_native_value(
        raw_dict.get("max_density", raw_dict.get("density", 0)), 0
    ))
    risk_level_val = str(clean_native_value(
        raw_dict.get("risk_level", raw_dict.get("risk", "Low")), "Low"
    ))
    anomaly_score_val = float(clean_native_value(
        raw_dict.get("anomaly_score", raw_dict.get("anomaly", 0.0)), 0.0
    ))

    # 2. Extract remaining primary fields
    person_count = int(clean_native_value(raw_dict.get("person_count", 0), 0))
    combined_score = float(clean_native_value(raw_dict.get("combined_score", 0.0), 0.0))
    raw_score = float(clean_native_value(raw_dict.get("raw_score", combined_score), 0.0))
    smoothed_score = float(clean_native_value(raw_dict.get("smoothed_score", combined_score), 0.0))
    growth_rate = float(clean_native_value(raw_dict.get("growth_rate", 0.0), 0.0))
    data_quality_score = float(clean_native_value(raw_dict.get("data_quality_score", 1.0), 1.0))
    
    avg_speed = float(clean_native_value(raw_dict.get("avg_speed", 0.0), 0.0))
    max_speed = float(clean_native_value(raw_dict.get("max_speed", 0.0), 0.0))
    dominant_direction = str(clean_native_value(raw_dict.get("dominant_direction", "STATIONARY"), "STATIONARY"))
    camera_motion_detected = bool(clean_native_value(raw_dict.get("camera_motion_detected", False), False))
    sudden_movement_count = int(clean_native_value(raw_dict.get("sudden_movement_count", 0), 0))
    
    fps = float(clean_native_value(raw_dict.get("fps", 0.0), 0.0))
    
    ts_val = raw_dict.get("last_frame_time", raw_dict.get("timestamp"))
    if not ts_val or not isinstance(ts_val, str):
        last_frame_time = datetime.now(timezone.utc).isoformat()
    else:
        last_frame_time = str(ts_val)

    # 3. Build 19-key dictionary (16 Primary + 3 Aliases)
    return {
        # 16 Primary Fields
        "person_count": person_count,
        "max_density": max_density_val,
        "risk_level": risk_level_val,
        "combined_score": combined_score,
        "raw_score": raw_score,
        "smoothed_score": smoothed_score,
        "growth_rate": growth_rate,
        "data_quality_score": data_quality_score,
        "avg_speed": avg_speed,
        "max_speed": max_speed,
        "dominant_direction": dominant_direction,
        "camera_motion_detected": camera_motion_detected,
        "sudden_movement_count": sudden_movement_count,
        "anomaly_score": anomaly_score_val,
        "fps": fps,
        "last_frame_time": last_frame_time,
        
        # 3 Compatibility Aliases
        "density": max_density_val,           # Alias for max_density
        "risk": risk_level_val,               # Alias for risk_level
        "anomaly": anomaly_score_val          # Alias for anomaly_score
    }


def parse_iso_timestamp(ts_str: Optional[str]) -> Optional[datetime]:
    """Parse ISO 8601 timestamps (handles trailing Z, timezone offsets, or naive strings)."""
    if not ts_str or not isinstance(ts_str, str):
        return None
    try:
        clean_ts = ts_str.strip()
        if clean_ts.endswith('Z'):
            clean_ts = clean_ts[:-1] + '+00:00'
        dt = datetime.fromisoformat(clean_ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def evaluate_telemetry_staleness(ts_str: Optional[str], max_age_seconds: float = 10.0) -> Tuple[bool, float]:
    """
    Evaluates if telemetry timestamp is older than max_age_seconds.
    Returns: (is_stale: bool, age_seconds: float)
    """
    dt = parse_iso_timestamp(ts_str)
    if dt is None:
        return True, float('inf')
    
    now_utc = datetime.now(timezone.utc)
    age_seconds = (now_utc - dt).total_seconds()
    
    # Handle clock skew (future timestamps)
    if age_seconds < -60.0:
        return False, age_seconds  # Future timestamp > 60s, flag clock skew
    
    is_stale = (age_seconds > max_age_seconds)
    return is_stale, max(0.0, age_seconds)


def load_offline_csv_fallback(log_dir: str = "logs", default_csv: str = "output/metrics_log.csv") -> Tuple[Optional[Dict[str, Any]], str]:
    """
    Resilient offline CSV reader. Attempts default_csv or latest file in log_dir.
    Handles missing file, 0-byte file, corrupted rows, missing columns, and NaN values.
    Returns: (normalized_payload_dict, source_description)
    """
    candidate_paths = [Path(default_csv)]
    log_path = Path(log_dir)
    if log_path.exists() and log_path.is_dir():
        csv_files = sorted(log_path.glob("metrics_*.csv"), key=os.path.getmtime, reverse=True)
        candidate_paths.extend(csv_files)
        
    for p in candidate_paths:
        if not p.exists() or p.stat().st_size == 0:
            continue
            
        try:
            with open(p, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                if not rows:
                    continue
                
                # Take last row
                last_row = rows[-1]
                
                # Convert CSV row fields to payload structure
                raw_payload = {
                    "person_count": last_row.get("person_count"),
                    "density": last_row.get("max_density", last_row.get("density")),
                    "max_density": last_row.get("max_density", last_row.get("density")),
                    "anomaly": last_row.get("anomaly_score", last_row.get("anomaly")),
                    "anomaly_score": last_row.get("anomaly_score", last_row.get("anomaly")),
                    "risk": last_row.get("risk_level", last_row.get("risk")),
                    "risk_level": last_row.get("risk_level", last_row.get("risk")),
                    "combined_score": last_row.get("combined_score"),
                    "raw_score": last_row.get("raw_score", last_row.get("combined_score")),
                    "smoothed_score": last_row.get("smoothed_score", last_row.get("combined_score")),
                    "growth_rate": last_row.get("growth_rate"),
                    "data_quality_score": last_row.get("data_quality_score"),
                    "fps": last_row.get("fps"),
                    "last_frame_time": last_row.get("timestamp")
                }
                
                normalized = normalize_telemetry_payload(raw_payload)
                return normalized, f"Local CSV ({p.name})"
        except Exception:
            continue
            
    return None, "No CSV Data Available"


def determine_connection_status(
    firebase_connected: bool,
    data: Optional[Dict[str, Any]],
    is_stale: bool,
    is_csv_fallback: bool = False
) -> str:
    """
    Classifies dashboard connection state into one of 4 explicit states:
      - 'CONNECTED': Firebase connected, live stream (age <= 10s)
      - 'STALE': Telemetry present, but age > 10s (monitoring paused)
      - 'OFFLINE_FALLBACK': Reading local CSV metrics log
      - 'UNAVAILABLE': Neither Firebase nor CSV metrics available
    """
    if not data or not isinstance(data, dict):
        return "UNAVAILABLE"
        
    if is_csv_fallback:
        if is_stale:
            return "STALE"
        return "OFFLINE_FALLBACK"
        
    if firebase_connected:
        if is_stale:
            return "STALE"
        return "CONNECTED"
        
    return "UNAVAILABLE"
