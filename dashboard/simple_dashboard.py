"""
CrowdPatrol Live Dashboard - Phase 4 Integrated Streamlit Client
Supports 19-key telemetry payload (16 primary + 3 aliases), staleness detection,
offline local CSV fallback, data quality badges, motion indicators, and academic disclaimer.
"""

import streamlit as st
import pandas as pd
import time
from datetime import datetime
from collections import deque
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).parent.parent))

from dashboard.dashboard_utils import (
    normalize_telemetry_payload,
    evaluate_telemetry_staleness,
    load_offline_csv_fallback,
    determine_connection_status
)

# ========== CONNECT TO FIREBASE ==========
import firebase_admin
from firebase_admin import credentials, db

@st.cache_resource
def init_firebase():
    """Initialize Firebase once with fail-safe error handling"""
    try:
        firebase_admin.get_app()
        return True
    except ValueError:
        try:
            cred_path = Path(__file__).parent.parent / 'firebase-credentials.json'
            if not cred_path.exists():
                return False
            cred = credentials.Certificate(str(cred_path))
            firebase_admin.initialize_app(cred, {
                'databaseURL': 'https://crowdpatrol-default-rtdb.asia-southeast1.firebasedatabase.app'
            })
            return True
        except Exception:
            return False

# ========== PAGE SETUP ==========
st.set_page_config(page_title="CrowdPatrol", page_icon="🚨", layout="wide")
st.title("🚨 CrowdPatrol - Live Monitoring Dashboard")

# Academic Prototype Disclaimer Notice
st.caption("ℹ️ **Academic Prototype Notice**: CrowdPatrol is an experimental prototype for automated crowd density and motion-anomaly monitoring. System output represents relative metric indications for tested benchmark scenarios.")

# Initialize Firebase connection
fb_initialized = init_firebase()

# Sidebar Configuration
st.sidebar.header("📡 Connection & Settings")
status_placeholder = st.sidebar.empty()
refresh_interval = st.sidebar.slider("Auto-Refresh Rate (seconds)", 1, 10, 3)

# ========== CREATE PLACEHOLDERS ==========
col_left, col_right = st.columns([2, 1])

with col_left:
    st.subheader("📹 System & Motion Status")
    status_box = st.empty()

with col_right:
    st.subheader("📊 Real-time Metrics")
    risk_placeholder = st.empty()
    
    col1, col2 = st.columns(2)
    with col1:
        person_metric = st.empty()
    with col2:
        density_metric = st.empty()
    
    quality_bar = st.empty()
    fps_metric = st.empty()

st.subheader("📈 Live Trend Analysis")
chart_col1, chart_col2 = st.columns(2)
with chart_col1:
    risk_chart = st.empty()
with chart_col2:
    person_chart = st.empty()

st.subheader("🚨 Recent Alerts Log")
alerts_placeholder = st.empty()

# ========== SESSION STATE STORAGE ==========
if 'risk_history' not in st.session_state:
    st.session_state.risk_history = deque(maxlen=30)
if 'person_history' not in st.session_state:
    st.session_state.person_history = deque(maxlen=30)
if 'density_history' not in st.session_state:
    st.session_state.density_history = deque(maxlen=30)
if 'time_history' not in st.session_state:
    st.session_state.time_history = deque(maxlen=30)

# ========== DATA FETCHING FUNCTIONS ==========
def fetch_telemetry_data():
    """Reads telemetry with offline CSV fallback and staleness check."""
    raw_data = None
    is_csv_fallback = False
    source_desc = "Firebase RTDB"
    
    if fb_initialized:
        try:
            dashboard_ref = db.reference('dashboard')
            raw_data = dashboard_ref.get()
        except Exception:
            raw_data = None

    if not raw_data:
        raw_data, source_desc = load_offline_csv_fallback()
        is_csv_fallback = (raw_data is not None)

    if not raw_data:
        return None, "UNAVAILABLE", True, "No Data Source Available"

    normalized = normalize_telemetry_payload(raw_data)
    is_stale, age_sec = evaluate_telemetry_staleness(normalized.get("last_frame_time"))
    status = determine_connection_status(fb_initialized, normalized, is_stale, is_csv_fallback)
    
    return normalized, status, is_stale, source_desc


def read_recent_alerts(limit=5):
    """Read recent alerts from Firebase"""
    if not fb_initialized:
        return []
    try:
        alerts_ref = db.reference('alerts')
        alerts = alerts_ref.order_by_key().limit_to_last(limit).get()
        if alerts:
            return [v for v in alerts.values()][::-1]
        return []
    except Exception:
        return []

# Refresh Button
if st.button("🔄 Manual Refresh"):
    pass

# Read telemetry data
data, conn_status, is_stale, source_desc = fetch_telemetry_data()
alerts = read_recent_alerts(5)

# Render Sidebar Status
if conn_status == "CONNECTED":
    status_placeholder.success(f"🟢 Connected ({source_desc})")
elif conn_status == "STALE":
    status_placeholder.warning(f"🟡 Telemetry Stale (Pipeline Paused)")
elif conn_status == "OFFLINE_FALLBACK":
    status_placeholder.info(f"🟠 Offline Mode ({source_desc})")
else:
    status_placeholder.error("🔴 System Disconnected / Unavailable")

if data:
    # 19 Normalized Keys Extraction
    person_count = data["person_count"]
    max_density = data["max_density"]
    risk_level = data["risk_level"]
    combined_score = data["combined_score"]
    raw_score = data["raw_score"]
    smoothed_score = data["smoothed_score"]
    growth_rate = data["growth_rate"]
    data_quality_score = data["data_quality_score"]
    avg_speed = data["avg_speed"]
    max_speed = data["max_speed"]
    dominant_dir = data["dominant_direction"]
    cam_motion = data["camera_motion_detected"]
    sudden_count = data["sudden_movement_count"]
    fps = data["fps"]
    last_update = data["last_frame_time"][:19]

    # Update session history
    current_time = datetime.now().strftime("%H:%M:%S")
    st.session_state.risk_history.append(combined_score)
    st.session_state.person_history.append(person_count)
    st.session_state.density_history.append(max_density)
    st.session_state.time_history.append(current_time)

    # Status Box Banner
    with status_box.container():
        cam_text = "🎥 Camera Pan Active (Motion Excluded)" if cam_motion else "📷 Static Camera"
        if conn_status == "STALE":
            st.warning(f"🟡 STALE DATA (Last frame: {last_update}) | Score: {combined_score:.1f} | {cam_text}")
        elif risk_level == "High":
            st.error(f"🔴 HIGH RISK! Score: {combined_score:.1f} (Raw: {raw_score:.1f}) | {cam_text}")
        elif risk_level == "Medium":
            st.warning(f"🟡 Medium Risk - Score: {combined_score:.1f} (Raw: {raw_score:.1f}) | {cam_text}")
        else:
            st.success(f"🟢 Normal - Score: {combined_score:.1f} | Speed: {avg_speed:.2f} px/f | Heading: {dominant_dir} | {cam_text}")

        st.caption(f"Source: {source_desc} | Last Frame: {last_update} | Quality: {data_quality_score*100:.0f}% | Spikes: {sudden_count}")

    # Risk Meter Widget
    risk_colors = {"Low": "#00ff88", "Medium": "#ffaa00", "High": "#ff0000", "No Data": "#666"}
    color = risk_colors.get(risk_level, "#666")

    risk_placeholder.markdown(f"""
    <div style="background:#1a1a2e; padding:15px; border-radius:10px; 
                text-align:center; border:3px solid {color}; margin-bottom:10px;">
        <h3 style="color:{color}; margin:0;">{risk_level.upper()}</h3>
        <h1 style="color:{color}; margin:5px 0;">{combined_score:.1f}</h1>
        <p style="margin:0; font-size:0.9em;">Influx: {growth_rate:.1f} p/s | Speed: {avg_speed:.1f} px/f ({dominant_dir})</p>
    </div>
    """, unsafe_allow_html=True)

    # Metrics Row
    person_metric.metric("👥 Tracked Persons", person_count)
    density_metric.metric("📊 Max Density", f"{max_density} p/cell")
    quality_bar.progress(min(max(0.0, data_quality_score), 1.0), text=f"Data Quality ({data_quality_score*100:.0f}%)")
    fps_metric.metric("⚡ Pipeline FPS", f"{fps:.1f}")

    # Trend Charts
    if len(st.session_state.time_history) > 1:
        df1 = pd.DataFrame({
            "Time": list(st.session_state.time_history),
            "Smoothed Score": list(st.session_state.risk_history)
        })
        risk_chart.line_chart(df1.set_index("Time"), height=220)

        df2 = pd.DataFrame({
            "Time": list(st.session_state.time_history),
            "Persons": list(st.session_state.person_history),
            "Density": list(st.session_state.density_history)
        })
        person_chart.line_chart(df2.set_index("Time"), height=220)
    else:
        risk_chart.info("📈 Accumulating trend points...")
        person_chart.info("📈 Accumulating trend points...")

else:
    status_box.error("🔴 No Telemetry Available. Run `python main.py --source 0 --alerts` in terminal.")
    risk_placeholder.info("Waiting for pipeline data...")

# Alerts table
if alerts:
    simplified = []
    for a in alerts:
        simplified.append({
            "Time": a.get("timestamp", "")[:19],
            "Risk": a.get("risk_level", a.get("risk", "")),
            "Score": a.get("combined_score", 0),
            "Persons": a.get("person_count", 0)
        })
    alerts_placeholder.dataframe(pd.DataFrame(simplified), use_container_width=True)
else:
    alerts_placeholder.info("✅ No active high-risk alerts logged.")