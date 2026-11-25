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
import io
import wave
import struct
import base64
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Tuple, Optional
import numpy as np

_BEEP_WAV_B64: Optional[str] = None
_SIREN_WAV_B64: Optional[str] = None

def get_beep_b64() -> str:
    """Generates or returns cached 880 Hz beep audio in base64 WAV format."""
    global _BEEP_WAV_B64
    if _BEEP_WAV_B64 is None:
        rate = 16000
        duration = 0.25 # seconds
        freq = 880.0
        buf = io.BytesIO()
        with wave.open(buf, 'wb') as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(rate)
            n_samples = int(rate * duration)
            data = []
            for i in range(n_samples):
                t = float(i) / rate
                env = min(1.0, i / (rate * 0.02), (n_samples - i) / (rate * 0.02))
                sample = int(32767.0 * 0.8 * env * math.sin(2.0 * math.pi * freq * t))
                data.append(struct.pack('<h', sample))
            wav.writeframes(b''.join(data))
        _BEEP_WAV_B64 = base64.b64encode(buf.getvalue()).decode('ascii')
    return _BEEP_WAV_B64

def get_siren_b64() -> str:
    """Generates or returns cached dual-frequency alternating emergency siren in base64 WAV format."""
    global _SIREN_WAV_B64
    if _SIREN_WAV_B64 is None:
        rate = 16000
        duration = 0.7 # seconds
        buf = io.BytesIO()
        with wave.open(buf, 'wb') as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(rate)
            n_samples = int(rate * duration)
            data = []
            phase = 0.0
            for i in range(n_samples):
                t = float(i) / rate
                freq = 600.0 + 500.0 * (0.5 + 0.5 * math.sin(2.0 * math.pi * 3.5 * t))
                phase += 2.0 * math.pi * freq / rate
                env = min(1.0, i / (rate * 0.03), (n_samples - i) / (rate * 0.03))
                sample = int(32767.0 * 0.85 * env * math.sin(phase))
                data.append(struct.pack('<h', sample))
            wav.writeframes(b''.join(data))
        _SIREN_WAV_B64 = base64.b64encode(buf.getvalue()).decode('ascii')
    return _SIREN_WAV_B64

def get_alarm_audio_html(severity: str = "HIGH") -> str:
    """Returns HTML5 autoplay audio tag with Beep (for HIGH) or Siren (for CRITICAL)."""
    sev_upper = str(severity).upper()
    if sev_upper == "CRITICAL":
        b64_audio = get_siren_b64()
    else:
        b64_audio = get_beep_b64()
    return f'<audio autoplay style="display:none;"><source src="data:audio/wav;base64,{b64_audio}" type="audio/wav"></audio>'



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


def format_alert_card_html(alt: Any) -> str:
    """Generates styled HTML card for an active alert event."""
    sev = getattr(alt, "severity", getattr(alt, "risk_level", "LOW")).upper()
    if sev == "CRITICAL":
        b_col, bg_col = "#ff0055", "#400018"
        badge = f"🔥 CRITICAL DENSITY ALERT ({getattr(alt, 'risk_score', 0.0):.1f})"
    elif sev == "HIGH":
        b_col, bg_col = "#ff3333", "#3a0000"
        badge = f"🚨 HIGH-RISK ALERT ({getattr(alt, 'risk_score', 0.0):.1f})"
    else:
        b_col, bg_col = "#ffaa00", "#2a2000"
        badge = f"🟡 MEDIUM-RISK WARNING ({getattr(alt, 'risk_score', 0.0):.1f})"
        
    status_text = f"<b>{getattr(alt, 'status', 'ACTIVE')}</b>"
    if getattr(alt, "acknowledged", False):
        status_text += f" (Acknowledged by {getattr(alt, 'acknowledged_by', 'Operator') or 'Operator'})"

    ts = str(getattr(alt, "timestamp", ""))[:19].replace('T', ' ')
    cat = getattr(alt, "category", "CROWD_RISK")
    density = getattr(alt, "crowd_density", getattr(alt, "primary_zone_density", 0))
    zone = getattr(alt, "primary_risk_zone", "--")

    return f"""<div style="background:{bg_col}; border:2px solid {b_col}; padding:10px 14px; border-radius:8px; margin-bottom:8px;">
<div style="display:flex; justify-content:space-between; align-items:center;">
<span style="color:{b_col}; font-weight:bold; font-size:1.05em;">{badge}</span>
<span style="color:#aaa; font-size:0.85em;">{ts}</span>
</div>
<div style="color:#fff; font-size:0.95em; margin-top:4px;">
<b>{getattr(alt, 'camera_id', 'CAM')}</b> ({getattr(alt, 'camera_name', 'Camera')}) &nbsp;|&nbsp;
Category: <b>{cat}</b> &nbsp;|&nbsp;
Density: <b>{density}</b> p/cell (Zone <b>{zone}</b>)
</div>
<div style="color:#eee; font-size:0.88em; margin-top:2px;">Reason: <i>{getattr(alt, 'reason', '')}</i></div>
<div style="color:#bbb; font-size:0.82em; margin-top:4px;">Status: {status_text}</div>
</div>"""


def format_alert_history_table(history: list) -> str:
    """Formats list of AlertEvents into Markdown table."""
    if not history:
        return "No historical alerts recorded yet."
    table_md = [
        "| Time | Camera | Severity | Category | Score | Density | Status | Reason |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |"
    ]
    for h in reversed(history):
        ts = str(getattr(h, "timestamp", ""))[:19].replace("T", " ")
        cam = f"{getattr(h, 'camera_id', 'CAM')} ({getattr(h, 'camera_name', 'Camera')})"
        sev = getattr(h, "severity", getattr(h, "risk_level", "LOW"))
        cat = getattr(h, "category", "CROWD_RISK")
        score = f"{getattr(h, 'risk_score', 0.0):.1f}"
        dens = getattr(h, "crowd_density", getattr(h, "primary_zone_density", 0))
        status = getattr(h, "status", "UNKNOWN")
        reason = getattr(h, "reason", "")
        if len(reason) > 40:
            reason = reason[:37] + "..."
        table_md.append(f"| {ts} | {cam} | {sev} | {cat} | {score} | {dens} | {status} | {reason} |")
    return "\n".join(table_md)


def render_dashboard_alerts(alert_mgr, summary_ph, feed_ph, history_ph=None):
    """
    Renders standardized Alert Summary, Live Alert Feed, and Alert History in the dashboard.
    """
    if alert_mgr is None:
        feed_ph.info("Alert Manager not active.")
        return
        
    summary = alert_mgr.get_alert_summary()
    summary_html = f"""
    <div style="display:grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-bottom: 12px;">
        <div style="background:#1e293b; padding:10px; border-radius:6px; text-align:center; border:1px solid #334155;">
            <div style="font-size:0.8em; color:#94a3b8;">🚨 Active Alerts</div>
            <div style="font-size:1.4em; font-weight:bold; color:#f8fafc;">{summary.get('active', 0)}</div>
        </div>
        <div style="background:#2a0000; padding:10px; border-radius:6px; text-align:center; border:1px solid #7f1d1d;">
            <div style="font-size:0.8em; color:#fca5a5;">🔴 High / Critical</div>
            <div style="font-size:1.4em; font-weight:bold; color:#ef4444;">{summary.get('high', 0) + summary.get('critical', 0)}</div>
        </div>
        <div style="background:#2d2000; padding:10px; border-radius:6px; text-align:center; border:1px solid #78350f;">
            <div style="font-size:0.8em; color:#fde68a;">🟡 Medium Risk</div>
            <div style="font-size:1.4em; font-weight:bold; color:#f59e0b;">{summary.get('medium', 0)}</div>
        </div>
        <div style="background:#0f291e; padding:10px; border-radius:6px; text-align:center; border:1px solid #065f46;">
            <div style="font-size:0.8em; color:#a7f3d0;">✅ Resolved</div>
            <div style="font-size:1.4em; font-weight:bold; color:#10b981;">{summary.get('resolved', 0)}</div>
        </div>
    </div>
    """
    summary_ph.markdown(summary_html, unsafe_allow_html=True)

    active_alerts = alert_mgr.get_active_alerts()
    if active_alerts:
        cards = [format_alert_card_html(alt) for alt in active_alerts]
        feed_ph.markdown("".join(cards), unsafe_allow_html=True)
    else:
        feed_ph.markdown("""<div style="background:#142918; border:1px solid #00dd66; padding:10px 14px; border-radius:8px; margin-bottom:8px;">
<span style="color:#00dd66; font-weight:bold;">🟢 ALL CLEAR — NO ACTIVE ALERTS</span>
<div style="color:#bbb; font-size:0.85em; margin-top:2px;">Crowd density, velocity and risk scores are within normal operating bounds.</div>
</div>""", unsafe_allow_html=True)

    if history_ph is not None:
        history = alert_mgr.get_alert_history(limit=10)
        table_md = format_alert_history_table(history)
        history_ph.markdown(table_md)


def format_notification_history_table(history: list) -> str:
    """Formats list of NotificationRecord objects into Markdown table."""
    if not history:
        return "No notifications dispatched yet."
    table_md = [
        "| Time | Channel | Severity | Camera | Alert ID | Recipient | Status | Notes |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |"
    ]
    for r in reversed(history):
        ts = str(getattr(r, "timestamp", ""))[:19].replace("T", " ")
        ch = getattr(r, "channel", "EMAIL")
        sev = getattr(r, "severity", "INFO")
        cam = getattr(r, "camera_id", "--")
        alt = getattr(r, "alert_id", "--")
        rec = getattr(r, "recipient", "")
        # Mask email/phone in table for security
        if "@" in rec:
            parts = rec.split("@")
            rec_safe = (parts[0][:3] if len(parts[0]) >= 3 else parts[0]) + "***@" + parts[1]
        elif len(rec) > 6:
            rec_safe = rec[:3] + "***" + rec[-3:]
        else:
            rec_safe = rec
        status = getattr(r, "status", "UNKNOWN")
        err = getattr(r, "error_message", "") or ""
        if len(err) > 30:
            err = err[:27] + "..."
        table_md.append(f"| {ts} | {ch} | {sev} | {cam} | {alt} | {rec_safe} | {status} | {err} |")
    return "\n".join(table_md)


def render_dashboard_notifications(dispatcher, status_ph, history_ph=None):
    """
    Renders Notification Delivery System status and history in dashboard (Email Dispatch).
    """
    if dispatcher is None:
        return
    summary = dispatcher.get_status_summary()
    with status_ph.container():
        try:
            import streamlit as st
            n_col1, n_col2, n_col3 = st.columns(3)
            email_status = "🟢 Configured (SMTP)" if summary["is_email_configured"] else "⚪ Not Configured"
            n_col1.metric("📧 Email Dispatch", email_status)
            n_col2.metric("📤 Delivered", summary["total_sent"])
            n_col3.metric("❌ Failures", summary["total_failed"])

            last_attempt = summary.get("last_attempt_time")
            if last_attempt:
                last_ts = last_attempt[:19].replace('T', ' ')
                st.caption(f"Last Attempt: **{last_ts}** via **{summary.get('last_attempt_channel')}** — Status: **{summary.get('last_attempt_status')}**")
        except Exception:
            pass

    if history_ph is not None:
        history = dispatcher.get_history(limit=10)
        table_md = format_notification_history_table(history)
        history_ph.markdown(table_md)


