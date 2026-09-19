"""
CrowdPatrol Live Interactive Dashboard - Fast High-FPS Web Client
Optimized with JPEG stream compression, downsampled web preview, and throttled chart rendering for smooth 30 FPS playback.
"""

import streamlit as st
import pandas as pd
import numpy as np
import cv2
import time
from datetime import datetime
from collections import deque
import sys
import os
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).parent.parent))

from src.detection import PersonDetector
from src.tracking import PersonTracker
from src.density import DensityEstimator
from src.motion_analysis import CrowdMotionAnalyzer
from src.risk_assessment import RiskAssessor
from src.heatmap import generate_heatmap
from src.alerts import FirebaseAlertManager
from src.utils import VideoProcessor, MetricsLogger, FrameAnnotator

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
st.set_page_config(page_title="CrowdPatrol High-FPS Dashboard", page_icon="🚨", layout="wide")
st.title("🚨 CrowdPatrol - Autonomous Crowd Monitoring Dashboard")

st.caption("ℹ️ **Academic Prototype Notice**: CrowdPatrol is an experimental prototype for automated crowd density and motion-anomaly monitoring. System output represents relative metric indications for tested benchmark scenarios.")

fb_initialized = init_firebase()

# ========== SESSION STATE STORAGE ==========
if 'risk_history' not in st.session_state:
    st.session_state.risk_history = deque(maxlen=30)
if 'person_history' not in st.session_state:
    st.session_state.person_history = deque(maxlen=30)
if 'density_history' not in st.session_state:
    st.session_state.density_history = deque(maxlen=30)
if 'time_history' not in st.session_state:
    st.session_state.time_history = deque(maxlen=30)
if 'is_monitoring' not in st.session_state:
    st.session_state.is_monitoring = False

# ========== SIDEBAR MODE & CONFIGURATION ==========
st.sidebar.header("🧭 Operation Mode & Input Selection")

mode = st.sidebar.radio(
    "Select Operating Mode:",
    ["🎥 Interactive Web Pipeline (Direct Stream)", "📡 Remote Telemetry Stream (Firebase/CSV)"]
)

DEFAULT_MODEL_PATH = "models/crowdpatrol_yolov8n_finetuned_v2.pt" if os.path.exists("models/crowdpatrol_yolov8n_finetuned_v2.pt") else "yolov8n.pt"
video_source = "data/videos/youtube_crowd_test.mp4"
model_type = DEFAULT_MODEL_PATH
confidence = 0.35
detect_interval = 3
device = "cpu"
enable_alerts = False
jpeg_quality = 80
preview_resolution = (854, 480)

if mode == "🎥 Interactive Web Pipeline (Direct Stream)":
    input_type = st.sidebar.selectbox(
        "Select Input Source:",
        ["📷 Live Webcam", "📁 Upload Video File", "🎥 Benchmark Sample Video", "🔗 Video Path / RTSP URL"]
    )
    
    if input_type == "📷 Live Webcam":
        webcam_idx = st.sidebar.number_input("Webcam Device Index", min_value=0, max_value=10, value=0)
        video_source = webcam_idx
    elif input_type == "📁 Upload Video File":
        uploaded_file = st.sidebar.file_uploader("Upload Video File", type=["mp4", "avi", "mov", "mkv"])
        if uploaded_file is not None:
            temp_dir = Path("data/videos/temp")
            temp_dir.mkdir(parents=True, exist_ok=True)
            temp_path = temp_dir / uploaded_file.name
            with open(temp_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            video_source = str(temp_path)
            st.sidebar.success(f"Loaded: {uploaded_file.name}")
        else:
            video_source = "data/videos/youtube_crowd_test.mp4"
    elif input_type == "🎥 Benchmark Sample Video":
        sample_choice = st.sidebar.selectbox(
            "Select Sample Video:",
            ["youtube_crowd_test.mp4", "crowd_sample.mp4"]
        )
        video_source = f"data/videos/{sample_choice}"
    elif input_type == "🔗 Video Path / RTSP URL":
        video_source = st.sidebar.text_input("Enter Path or URL:", "data/videos/youtube_crowd_test.mp4")
    
    st.sidebar.divider()
    st.sidebar.header("⚙️ Performance Settings")
    model_choice = st.sidebar.selectbox("YOLOv8 Model Weight:", ["models/crowdpatrol_yolov8n_finetuned_v2.pt", "yolov8n.pt", "yolov8s.pt"])
    model_type = model_choice
    confidence = st.sidebar.slider("Confidence Threshold", 0.10, 1.00, 0.35, 0.05)
    detect_interval = st.sidebar.slider("Detection Interval (Frames)", 1, 10, 3)
    res_choice = st.sidebar.selectbox("Web Preview Resolution:", ["854x480 (Recommended)", "640x360 (Ultra Fast)", "1280x720 (Full HD)"])
    if "640x360" in res_choice:
        preview_resolution = (640, 360)
    elif "1280x720" in res_choice:
        preview_resolution = (1280, 720)
    else:
        preview_resolution = (854, 480)
        
    device = st.sidebar.radio("Execution Device:", ["cpu", "cuda"], horizontal=True)
    enable_alerts = st.sidebar.checkbox("Sync Firebase Alerts", value=False)
    
    st.sidebar.divider()
    col_start, col_stop = st.sidebar.columns(2)
    with col_start:
        if st.button("▶️ Start Monitoring", use_container_width=True):
            st.session_state.is_monitoring = True
    with col_stop:
        if st.button("⏹️ Stop", use_container_width=True):
            st.session_state.is_monitoring = False

else:
    st.sidebar.divider()
    st.sidebar.header("📡 Remote Stream Settings")
    status_placeholder = st.sidebar.empty()
    refresh_interval = st.sidebar.slider("Auto-Refresh Rate (seconds)", 1, 10, 3)
    if st.sidebar.button("🔄 Manual Refresh", use_container_width=True):
        pass

# ========== LAYOUT PLACEHOLDERS ==========
col_left, col_right = st.columns([2, 1])

with col_left:
    st.subheader("📹 Live Video Stream & Overlay")
    video_placeholder = st.empty()
    status_box = st.empty()

with col_right:
    st.subheader("📊 Real-Time Telemetry")
    risk_placeholder = st.empty()
    
    col1, col2 = st.columns(2)
    with col1:
        person_metric = st.empty()
    with col2:
        density_metric = st.empty()
    
    col3, col4 = st.columns(2)
    with col3:
        speed_metric = st.empty()
    with col4:
        anomaly_metric = st.empty()
    
    quality_bar = st.empty()
    fps_metric = st.empty()

st.subheader("📈 Real-Time Trend Analysis")
chart_col1, chart_col2 = st.columns(2)
with chart_col1:
    risk_chart = st.empty()
with chart_col2:
    person_chart = st.empty()

st.subheader("🚨 Alerts & Event Log")
alerts_placeholder = st.empty()

# ========== DATA FETCHING FOR REMOTE STREAM MODE ==========
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


# ========== MODE 1: INTERACTIVE WEB PIPELINE EXECUTION ==========
if mode == "🎥 Interactive Web Pipeline (Direct Stream)":
    if st.session_state.is_monitoring:
        status_box.info(f"⏳ Initializing CrowdPatrol Core Modules... Source: `{video_source}`")
        
        cap = VideoProcessor.get_video_source(video_source)
        if not cap.isOpened():
            status_box.error(f"🔴 Error: Unable to open video source `{video_source}`.")
            st.session_state.is_monitoring = False
        else:
            detector = PersonDetector(model_path=model_type, confidence=confidence, device=device)
            tracker = PersonTracker(max_age=30)
            density_estimator = DensityEstimator(grid_size=(4, 4))
            motion_analyzer = CrowdMotionAnalyzer(grid_size=(4, 4))
            risk_assessor = RiskAssessor()
            metrics_logger = MetricsLogger()
            
            alert_manager = None
            if enable_alerts and fb_initialized:
                try:
                    alert_manager = FirebaseAlertManager()
                except Exception:
                    pass
            
            frame_count = 0
            fps_deque = deque(maxlen=30)
            current_tracks = []
            last_firebase_update = 0
            
            try:
                while st.session_state.is_monitoring:
                    t_start = time.perf_counter()
                    ret, frame = cap.read()
                    if not ret:
                        status_box.success("✅ Video stream completed.")
                        st.session_state.is_monitoring = False
                        break
                    
                    frame_count += 1
                    
                    # Detection & DeepSORT tracking
                    if frame_count == 1 or (frame_count % detect_interval == 0):
                        detections = detector.detect(frame)
                        current_tracks = tracker.update(detections, frame)
                    else:
                        current_tracks = tracker.predict()
                    
                    # Optical flow crowd motion analysis
                    grid_matrix, motion_summary = motion_analyzer.analyze_frame(frame)
                    
                    # Density & risk calculation
                    density_map, max_density = density_estimator.calculate_density(current_tracks, frame.shape)
                    anomaly_score = risk_assessor.calculate_movement_anomaly(current_tracks, frame.shape)
                    
                    risk_res = risk_assessor.assess_frame(
                        max_density=max_density,
                        motion_summary=motion_summary,
                        tracks=current_tracks,
                        timestamp=time.time(),
                        anomaly_score=anomaly_score
                    )
                    
                    risk_level_str = risk_res["risk"]
                    combined_score = risk_res["combined_score"]
                    person_count = len(current_tracks)
                    avg_speed = motion_summary.get("avg_speed", 0.0)
                    dominant_dir = motion_summary.get("dominant_direction", "STATIONARY")
                    cam_motion = motion_summary.get("camera_motion_detected", False)
                    data_quality_score = risk_res.get("data_quality_score", 1.0)
                    growth_rate = risk_res.get("growth_rate", 0.0)
                    
                    # Thermal heatmap background layer
                    heatmap_base, _ = generate_heatmap(frame, current_tracks, draw_grid=False)
                    
                    # Annotations & Visualization Overlay
                    annotated_frame = FrameAnnotator.create_dashboard_frame(
                        heatmap_base,
                        {
                            "person_count": person_count,
                            "density": max_density,
                            "anomaly": anomaly_score,
                            "avg_speed": avg_speed,
                            "dominant_direction": dominant_dir,
                            "risk": risk_level_str,
                            "combined_score": combined_score
                        },
                        density_map,
                        grid_size=(4, 4),
                        grid_matrix=grid_matrix,
                        tracks=current_tracks
                    )
                    
                    t_end = time.perf_counter()
                    frame_ms = (t_end - t_start) * 1000.0
                    current_fps = 1000.0 / frame_ms if frame_ms > 0 else 0.0
                    fps_deque.append(current_fps)
                    avg_fps = float(np.mean(fps_deque))
                    
                    # Draw FPS overlay
                    cv2.putText(annotated_frame, f"FPS: {avg_fps:.1f}", (20, frame.shape[0] - 20),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                    
                    # Log to CSV
                    metrics_payload = {
                        "person_count": person_count,
                        "density": max_density,
                        "max_density": max_density,
                        "anomaly": anomaly_score,
                        "anomaly_score": anomaly_score,
                        "risk": risk_level_str,
                        "risk_level": risk_level_str,
                        "combined_score": combined_score,
                        "raw_score": risk_res["raw_score"],
                        "smoothed_score": risk_res["smoothed_score"],
                        "data_quality_score": data_quality_score,
                        "growth_rate": growth_rate,
                        "avg_speed": avg_speed,
                        "max_speed": motion_summary.get("max_speed", 0.0),
                        "dominant_direction": dominant_dir,
                        "camera_motion_detected": cam_motion,
                        "sudden_movement_count": motion_summary.get("sudden_movement_count", 0),
                        "fps": avg_fps,
                        "last_frame_time": datetime.now().isoformat()
                    }
                    metrics_logger.log(metrics_payload, frame_count)
                    
                    if alert_manager and (time.time() - last_firebase_update > 1.0):
                        alert_manager.update_dashboard_data(metrics_payload)
                        last_firebase_update = time.time()
                    
                    # OPTIMIZATION 1: High-Speed Web JPEG Stream Compression
                    display_frame = cv2.resize(annotated_frame, preview_resolution)
                    _, jpeg_buffer = cv2.imencode('.jpg', display_frame, [int(cv2.IMWRITE_JPEG_QUALITY), jpeg_quality])
                    video_placeholder.image(jpeg_buffer.tobytes(), use_container_width=True)
                    
                    # Update Session State History for Real-Time Charts
                    current_time = datetime.now().strftime("%H:%M:%S")
                    st.session_state.risk_history.append(combined_score)
                    st.session_state.person_history.append(person_count)
                    st.session_state.density_history.append(max_density)
                    st.session_state.time_history.append(current_time)
                    
                    # Render Live Metrics Widgets (Throttled to every 2 frames for smooth web playback)
                    if frame_count % 2 == 0:
                        cam_text = "🎥 Camera Pan Active (Motion Excluded)" if cam_motion else "📷 Static Camera"
                        if risk_level_str == "High":
                            status_box.error(f"🔴 HIGH RISK! Score: {combined_score:.1f} | Influx: {growth_rate:.1f} p/s | {cam_text}")
                        elif risk_level_str == "Medium":
                            status_box.warning(f"🟡 Medium Risk - Score: {combined_score:.1f} | Speed: {avg_speed:.1f} px/f | {cam_text}")
                        else:
                            status_box.success(f"🟢 Normal - Score: {combined_score:.1f} | Speed: {avg_speed:.1f} px/f | Heading: {dominant_dir} | {cam_text}")
                        
                        risk_colors = {"Low": "#00ff88", "Medium": "#ffaa00", "High": "#ff0000"}
                        color = risk_colors.get(risk_level_str, "#666")
                        
                        risk_placeholder.markdown(f"""
                        <div style="background:#1a1a2e; padding:15px; border-radius:10px; 
                                    text-align:center; border:3px solid {color}; margin-bottom:10px;">
                            <h3 style="color:{color}; margin:0;">{risk_level_str.upper()}</h3>
                            <h1 style="color:{color}; margin:5px 0;">{combined_score:.1f}</h1>
                            <p style="margin:0; font-size:0.9em;">Influx: {growth_rate:.1f} p/s | Speed: {avg_speed:.1f} px/f ({dominant_dir})</p>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        person_metric.metric("👥 Tracked Persons", person_count)
                        density_metric.metric("📊 Max Density", f"{max_density} p/cell")
                        speed_metric.metric("🏃 Avg Speed", f"{avg_speed:.1f} px/f ({dominant_dir})")
                        anomaly_metric.metric("⚠️ Anomaly Score", f"{anomaly_score:.2f}")
                        quality_bar.progress(min(max(0.0, data_quality_score), 1.0), text=f"Data Quality ({data_quality_score*100:.0f}%)")
                        fps_metric.metric("⚡ Pipeline FPS", f"{avg_fps:.1f}")
                    
                    # OPTIMIZATION 2: Throttled Chart Updates (Every 10 Frames) to Prevent Browser UI Freeze
                    if frame_count % 10 == 0 and len(st.session_state.time_history) > 1:
                        df1 = pd.DataFrame({
                            "Time": list(st.session_state.time_history),
                            "Risk Score": list(st.session_state.risk_history)
                        })
                        risk_chart.line_chart(df1.set_index("Time"), height=200)
                        
                        df2 = pd.DataFrame({
                            "Time": list(st.session_state.time_history),
                            "Persons": list(st.session_state.person_history),
                            "Max Density": list(st.session_state.density_history)
                        })
                        person_chart.line_chart(df2.set_index("Time"), height=200)
                    
                    # Yield slightly for Streamlit GUI thread responsiveness
                    time.sleep(0.001)
                    
            finally:
                cap.release()
                cv2.destroyAllWindows()
                status_box.info("⏹️ Pipeline stopped cleanly.")
    else:
        status_box.info("👉 Click **▶️ Start Monitoring** in the sidebar to run the live interactive pipeline.")

# ========== MODE 2: REMOTE TELEMETRY STREAM ==========
else:
    data, conn_status, is_stale, source_desc = fetch_telemetry_data()
    alerts = read_recent_alerts(5)
    
    if conn_status == "CONNECTED":
        status_placeholder.success(f"🟢 Connected ({source_desc})")
    elif conn_status == "STALE":
        status_placeholder.warning(f"🟡 Telemetry Stale (Pipeline Paused)")
    elif conn_status == "OFFLINE_FALLBACK":
        status_placeholder.info(f"🟠 Offline Mode ({source_desc})")
    else:
        status_placeholder.error("🔴 System Disconnected / Unavailable")
    
    if data:
        person_count = data["person_count"]
        max_density = data["max_density"]
        risk_level = data["risk_level"]
        combined_score = data["combined_score"]
        raw_score = data["raw_score"]
        growth_rate = data["growth_rate"]
        data_quality_score = data["data_quality_score"]
        avg_speed = data["avg_speed"]
        dominant_dir = data["dominant_direction"]
        cam_motion = data["camera_motion_detected"]
        sudden_count = data["sudden_movement_count"]
        fps = data["fps"]
        last_update = data["last_frame_time"][:19]
        anomaly_score = data["anomaly_score"]
        
        current_time = datetime.now().strftime("%H:%M:%S")
        st.session_state.risk_history.append(combined_score)
        st.session_state.person_history.append(person_count)
        st.session_state.density_history.append(max_density)
        st.session_state.time_history.append(current_time)
        
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
        
        person_metric.metric("👥 Tracked Persons", person_count)
        density_metric.metric("📊 Max Density", f"{max_density} p/cell")
        speed_metric.metric("🏃 Avg Speed", f"{avg_speed:.1f} px/f ({dominant_dir})")
        anomaly_metric.metric("⚠️ Anomaly Score", f"{anomaly_score:.2f}")
        quality_bar.progress(min(max(0.0, data_quality_score), 1.0), text=f"Data Quality ({data_quality_score*100:.0f}%)")
        fps_metric.metric("⚡ Pipeline FPS", f"{fps:.1f}")
        
        if len(st.session_state.time_history) > 1:
            df1 = pd.DataFrame({
                "Time": list(st.session_state.time_history),
                "Smoothed Score": list(st.session_state.risk_history)
            })
            risk_chart.line_chart(df1.set_index("Time"), height=200)
            
            df2 = pd.DataFrame({
                "Time": list(st.session_state.time_history),
                "Persons": list(st.session_state.person_history),
                "Max Density": list(st.session_state.density_history)
            })
            person_chart.line_chart(df2.set_index("Time"), height=200)
    else:
        status_box.error("🔴 No Telemetry Available. Run `python main.py --source 0 --alerts` or switch to Interactive Web Pipeline mode.")
        risk_placeholder.info("Waiting for pipeline data...")

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