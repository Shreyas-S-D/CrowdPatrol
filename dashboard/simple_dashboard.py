"""
CrowdPatrol Live Dashboard - No flicker version
"""

import streamlit as st
import pandas as pd
import time
from datetime import datetime
from collections import deque

# ========== CONNECT TO FIREBASE ==========
import firebase_admin
from firebase_admin import credentials, db

@st.cache_resource
def init_firebase():
    """Initialize Firebase once"""
    try:
        firebase_admin.get_app()
    except ValueError:
        cred = credentials.Certificate('firebase-credentials.json')
        firebase_admin.initialize_app(cred, {
            'databaseURL': 'https://crowdpatrol-default-rtdb.asia-southeast1.firebasedatabase.app'
        })
    return True

# ========== PAGE SETUP ==========
st.set_page_config(page_title="CrowdPatrol", page_icon="🚨", layout="wide")
st.title("🚨 CrowdPatrol - Live Monitoring Dashboard")

# Initialize Firebase
init_firebase()

# Sidebar
st.sidebar.header("📡 Connection")
refresh_interval = st.sidebar.slider("Refresh (seconds)", 1, 10, 3)
status_placeholder = st.sidebar.empty()

# ========== CREATE PLACEHOLDERS ==========
col_left, col_right = st.columns([2, 1])

with col_left:
    st.subheader("📹 System Status")
    status_box = st.empty()

with col_right:
    st.subheader("📊 Real-time Metrics")
    risk_placeholder = st.empty()
    
    col1, col2 = st.columns(2)
    with col1:
        person_metric = st.empty()
    with col2:
        density_metric = st.empty()
    
    anomaly_bar = st.empty()
    fps_metric = st.empty()

st.subheader("📈 Live Trend")
chart_col1, chart_col2 = st.columns(2)
with chart_col1:
    risk_chart = st.empty()
with chart_col2:
    person_chart = st.empty()

st.subheader("🚨 Recent Alerts")
alerts_placeholder = st.empty()

# ========== DATA STORAGE (in session state - survives reruns) ==========
if 'risk_history' not in st.session_state:
    st.session_state.risk_history = deque(maxlen=30)
if 'person_history' not in st.session_state:
    st.session_state.person_history = deque(maxlen=30)
if 'density_history' not in st.session_state:
    st.session_state.density_history = deque(maxlen=30)
if 'time_history' not in st.session_state:
    st.session_state.time_history = deque(maxlen=30)

# ========== FUNCTIONS ==========
def read_firebase_data():
    """Read current dashboard data from Firebase"""
    try:
        dashboard_ref = db.reference('dashboard')
        data = dashboard_ref.get()
        return data if data else {}
    except:
        return {}

def read_recent_alerts(limit=5):
    """Read recent alerts from Firebase"""
    try:
        alerts_ref = db.reference('alerts')
        alerts = alerts_ref.order_by_key().limit_to_last(limit).get()
        if alerts:
            return [v for v in alerts.values()][::-1]
        return []
    except:
        return []

# ========== MAIN DISPLAY (runs once per manual refresh or button click) ==========

# Manual refresh button
if st.button("🔄 Refresh Now"):
    pass  # Streamlit reruns on button click

# Read data
data = read_firebase_data()
alerts = read_recent_alerts(5)

# Update sidebar
if data:
    status_placeholder.success("🟢 Connected to CrowdPatrol")
else:
    status_placeholder.warning("🟡 Waiting for system data...")
    st.info("💡 Run in another terminal: python run.py --source 1 --alerts")

# Get values
risk_level = data.get("risk_level", "No Data")
combined_score = float(data.get("combined_score", 0))
person_count = int(data.get("person_count", 0))
max_density = int(data.get("max_density", 0))
anomaly_score = float(data.get("anomaly_score", 0))
growth_rate = float(data.get("growth_rate", 0.0))
data_quality_score = float(data.get("data_quality_score", 1.0))
fps = int(data.get("fps", 0))
last_update = data.get("last_frame_time", "Never")

# Update history
current_time = datetime.now().strftime("%H:%M:%S")
st.session_state.risk_history.append(combined_score)
st.session_state.person_history.append(person_count)
st.session_state.density_history.append(max_density)
st.session_state.time_history.append(current_time)

# ========== DISPLAY ==========

# Status Box
with status_box.container():
    if risk_level == "High":
        st.error(f"🔴 HIGH RISK! Score: {combined_score:.1f} | Data Quality: {data_quality_score*100:.0f}%")
    elif risk_level == "Medium":
        st.warning(f"🟡 Medium Risk - Score: {combined_score:.1f} | Data Quality: {data_quality_score*100:.0f}%")
    elif risk_level == "Low":
        st.success(f"🟢 Normal - Score: {combined_score:.1f} | Data Quality: {data_quality_score*100:.0f}%")
    else:
        st.info("⏳ Waiting for data...")
    
    st.caption(f"Last update: {last_update} | Source: Firebase Realtime DB")

# Risk Meter
risk_colors = {"Low": "#00ff88", "Medium": "#ffaa00", "High": "#ff0000", "No Data": "#666"}
color = risk_colors.get(risk_level, "#666")

risk_placeholder.markdown(f"""
<div style="background:#1a1a2e; padding:20px; border-radius:10px; 
            text-align:center; border:3px solid {color}; margin-bottom:10px;">
    <h3 style="color:{color};">{risk_level.upper()}</h3>
    <h1 style="color:{color};">{combined_score:.1f}</h1>
    <p>Risk Score | Influx: {growth_rate:.1f} p/s | Quality: {data_quality_score*100:.0f}%</p>
</div>
""", unsafe_allow_html=True)

# Metrics
person_metric.metric("👥 Persons", person_count)
density_metric.metric("📊 Max Density", max_density)
anomaly_bar.progress(min(max(0.0, data_quality_score), 1.0), text=f"Data Quality Score: {data_quality_score*100:.0f}%")
fps_metric.metric("⚡ FPS", fps)

# Charts
if len(st.session_state.time_history) > 1:
    df = pd.DataFrame({
        "Time": list(st.session_state.time_history),
        "Risk Score": list(st.session_state.risk_history)
    })
    risk_chart.line_chart(df.set_index("Time"), height=250)
    
    df2 = pd.DataFrame({
        "Time": list(st.session_state.time_history),
        "Persons": list(st.session_state.person_history),
        "Density": list(st.session_state.density_history)
    })
    person_chart.line_chart(df2.set_index("Time"), height=250)
else:
    risk_chart.info("📈 Waiting for data points...")
    person_chart.info("📈 Waiting for data points...")

# Alerts table
if alerts:
    # Show only important columns
    simplified = []
    for a in alerts:
        simplified.append({
            "Time": a.get("timestamp", "")[:19],
            "Risk": a.get("risk_level", ""),
            "Score": a.get("combined_score", 0),
            "Persons": a.get("person_count", 0)
        })
    alerts_placeholder.dataframe(pd.DataFrame(simplified), use_container_width=True)
else:
    alerts_placeholder.info("✅ No alerts triggered yet")

# Auto-refresh info
st.caption(f"⏱️ Click 'Refresh Now' to update | Data refreshes every {refresh_interval}s in real scenario")