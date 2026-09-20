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
import json
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
from src.camera_devices import discover_camera_devices, test_camera_source, get_camera_display_name

from dashboard.dashboard_utils import (
    normalize_telemetry_payload,
    evaluate_telemetry_staleness,
    load_offline_csv_fallback,
    determine_connection_status
)

@st.cache_data(ttl=30)
def cached_discover_camera_devices():
    try:
        return discover_camera_devices()
    except Exception:
        return []

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
    ["🎥 Interactive Web Pipeline (Direct Stream)", "🖥️ Multi-Camera Command Center (CCTV Grid)", "📡 Remote Telemetry Stream (Firebase/CSV)"]
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
        discovered_devs = cached_discover_camera_devices()
        if discovered_devs:
            options_labels = [d.display_name for d in discovered_devs]
            selected_label = st.sidebar.selectbox("📷 Camera Device", options_labels, index=0)
            selected_dev = next((d for d in discovered_devs if d.display_name == selected_label), discovered_devs[0])
            webcam_idx = selected_dev.index
            st.sidebar.caption(f"Index: `{webcam_idx}` | Resolution: `{selected_dev.resolution}` | Status: `{selected_dev.status}`")
        else:
            webcam_idx = st.sidebar.number_input("Manual Device Index", min_value=0, max_value=10, value=0)
            
        if st.sidebar.button("🔍 Test Camera", key="test_mode1_cam", use_container_width=True):
            ok, msg, res = test_camera_source(webcam_idx)
            if ok:
                st.sidebar.success(f"🟢 {msg}")
            else:
                st.sidebar.error(f"🔴 {msg}")
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
    st.sidebar.header("🎯 Target & Model Selection")
    detection_mode = st.sidebar.radio(
        "Select Detection Mode:",
        ["👤 Person Mode (Default)", "🗣️ Head Mode — Experimental"]
    )
    
    tiled_mode = False
    if detection_mode == "🗣️ Head Mode — Experimental":
        st.sidebar.warning("⚠️ EXPERIMENTAL MODE ACTIVE\nUsing V4 Head Detector (crowdpatrol_yolov8n_head_v4.pt).\nNot for production safety monitoring.")
        head_strategy = st.sidebar.selectbox(
            "Inference Strategy:",
            ["Full-Frame (640x640)", "2x2 Spatial Tiling"]
        )
        tiled_mode = (head_strategy == "2x2 Spatial Tiling")
        model_type = "models/crowdpatrol_yolov8n_head_v4.pt" if os.path.exists("models/crowdpatrol_yolov8n_head_v4.pt") else "models/crowdpatrol_yolov8n_finetuned_v2.pt"
    else:
        model_choice = st.sidebar.selectbox("YOLOv8 Model Weight:", ["models/crowdpatrol_yolov8n_finetuned_v2.pt", "yolov8n.pt", "yolov8s.pt"])
        model_type = model_choice

    st.sidebar.divider()
    st.sidebar.header("⚙️ Performance Settings")
    default_conf = 0.25 if detection_mode == "🗣️ Head Mode — Experimental" else 0.35
    confidence = st.sidebar.slider("Confidence Threshold", 0.10, 1.00, default_conf, 0.05)
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

elif mode == "🖥️ Multi-Camera Command Center (CCTV Grid)":
    st.sidebar.divider()
    st.sidebar.header("📹 Camera Source Configuration")
    
    config_path = Path("config/cameras.json")
    if config_path.exists():
        with open(config_path, "r") as f:
            cam_json_cfg = json.load(f)
    else:
        cam_json_cfg = {"cameras": []}
        
    updated_cameras = []
    
    for cam_item in cam_json_cfg.get("cameras", []):
        cam_id = cam_item["id"]
        with st.sidebar.expander(f"⚙️ {cam_id}: {cam_item.get('name', 'Camera')}", expanded=False):
            cam_enabled = st.checkbox("Enable Camera Feed", value=cam_item.get("enabled", True), key=f"en_{cam_id}")
            cam_name = st.text_input("Camera Name", value=cam_item.get("name", cam_id), key=f"name_{cam_id}")
            
            src_type_options = ["📁 Recorded Video", "📷 Webcam", "🌐 IP Camera / RTSP"]
            curr_type = cam_item.get("source_type", "video")
            type_idx = 0 if curr_type == "video" else (1 if curr_type == "webcam" else 2)
            
            sel_type_str = st.selectbox("Source Type", src_type_options, index=type_idx, key=f"stype_{cam_id}")
            
            if "Recorded Video" in sel_type_str:
                new_src_type = "video"
                new_source = st.text_input("Video File Path", value=str(cam_item.get("source", "data/videos/youtube_crowd_test.mp4")), key=f"src_vid_{cam_id}")
                new_dev_name = None
            elif "Webcam" in sel_type_str:
                new_src_type = "webcam"
                discovered_devs = cached_discover_camera_devices()
                default_idx = int(cam_item.get("source")) if str(cam_item.get("source")).isdigit() else 0
                
                if discovered_devs:
                    dev_options = [d.display_name for d in discovered_devs]
                    matched_opt_idx = 0
                    for o_i, d_item in enumerate(discovered_devs):
                        if d_item.index == default_idx:
                            matched_opt_idx = o_i
                            break
                    
                    sel_dev_label = st.selectbox("📷 Camera Device", dev_options, index=matched_opt_idx, key=f"src_web_sel_{cam_id}")
                    sel_dev_obj = next((d for d in discovered_devs if d.display_name == sel_dev_label), discovered_devs[0])
                    new_source = sel_dev_obj.index
                    new_dev_name = sel_dev_obj.name
                    st.caption(f"Selected: `{sel_dev_obj.name}` (Device `{new_source}`) | Status: `{sel_dev_obj.status}`")
                else:
                    new_source = st.number_input("Manual Device Index", min_value=0, max_value=10, value=default_idx, key=f"src_web_num_{cam_id}")
                    new_dev_name = f"Webcam (Device {new_source})"
                
                if st.button(f"🔍 Test Camera ({cam_id})", key=f"test_cam_{cam_id}", use_container_width=True):
                    ok, msg, res = test_camera_source(new_source)
                    if ok:
                        st.success(f"🟢 {msg}")
                    else:
                        st.error(f"🔴 {msg}")
            else:
                new_src_type = "rtsp"
                new_source = st.text_input("RTSP Stream URL", value=str(cam_item.get("source", "rtsp://192.168.1.100:554/live")), key=f"src_rtsp_{cam_id}")
                new_dev_name = None
                
            updated_cameras.append({
                "id": cam_id,
                "name": cam_name,
                "source_type": new_src_type,
                "source": new_source,
                "device_name": new_dev_name,
                "enabled": cam_enabled
            })
            
    st.session_state.current_ui_cameras = updated_cameras
            
    if updated_cameras and st.sidebar.button("💾 Save Camera Config", use_container_width=True):
        with open(config_path, "w") as f:
            json.dump({"cameras": updated_cameras}, f, indent=2)
        if "multi_cam" in st.session_state and st.session_state.multi_cam is not None:
            for cam_item in updated_cameras:
                st.session_state.multi_cam.reconfigure_camera(
                    cam_item["id"],
                    cam_item["source"],
                    source_type=cam_item["source_type"],
                    name=cam_item["name"],
                    device_name=cam_item.get("device_name"),
                    enabled=cam_item["enabled"]
                )
        st.sidebar.success("Saved camera configuration!")
        st.rerun()

    st.sidebar.divider()
    st.sidebar.header("🎯 Target & Model Selection")
    detection_mode = st.sidebar.radio(
        "Select Detection Mode:",
        ["👤 Person Mode (Default)", "🗣️ Head Mode — Experimental"]
    )
    
    tiled_mode = False
    if detection_mode == "🗣️ Head Mode — Experimental":
        st.sidebar.warning("⚠️ EXPERIMENTAL MODE ACTIVE\nUsing V4 Head Detector across all streams.\nNot for production safety monitoring.")
        head_strategy = st.sidebar.selectbox(
            "Inference Strategy:",
            ["Full-Frame (640x640)", "2x2 Spatial Tiling"]
        )
        tiled_mode = (head_strategy == "2x2 Spatial Tiling")
        
    st.sidebar.divider()
    st.sidebar.header("⚙️ Performance Settings")
    detect_interval = st.sidebar.slider("Detection Interval (Frames)", 1, 10, 3)
    device = st.sidebar.radio("Execution Device:", ["cpu", "cuda"], horizontal=True)
    enable_alerts = st.sidebar.checkbox("Sync Firebase Alerts", value=False)
    
    st.sidebar.divider()
    col_start, col_stop = st.sidebar.columns(2)
    with col_start:
        if st.button("▶️ Start Command Center", use_container_width=True):
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
        if detection_mode == "🗣️ Head Mode — Experimental":
            st.warning("⚠️ EXPERIMENTAL MODE — HEAD DETECTION ACTIVE. Using V4 Head Detector (crowdpatrol_yolov8n_head_v4.pt). Not for production safety monitoring.")
            
        status_box.info(f"⏳ Initializing CrowdPatrol Core Modules... Source: `{video_source}` | Mode: `{detection_mode}`")
        
        cap = VideoProcessor.get_video_source(video_source)
        if not cap.isOpened():
            status_box.error(f"🔴 Error: Unable to open video source `{video_source}`.")
            st.session_state.is_monitoring = False
        else:
            if detection_mode == "🗣️ Head Mode — Experimental":
                from src.experimental_head_mode import ExperimentalHeadDetector, DEFAULT_HEAD_MODEL_PATH
                from src.experimental_head_density import HeadDensityEstimator
                from src.experimental_head_risk import ExperimentalHeadRiskAdapter
                
                head_model_path = "models/crowdpatrol_yolov8n_head_v4.pt" if os.path.exists("models/crowdpatrol_yolov8n_head_v4.pt") else DEFAULT_HEAD_MODEL_PATH
                detector = ExperimentalHeadDetector(model_path=head_model_path, confidence=confidence, device=device)
                tracker = PersonTracker(max_age=30)
                density_estimator = HeadDensityEstimator(grid_size=(4, 4))
                motion_analyzer = CrowdMotionAnalyzer(grid_size=(4, 4))
                risk_adapter = ExperimentalHeadRiskAdapter()
                risk_assessor = None
            else:
                detector = PersonDetector(model_path=model_type, confidence=confidence, device=device)
                tracker = PersonTracker(max_age=30)
                density_estimator = DensityEstimator(grid_size=(4, 4))
                motion_analyzer = CrowdMotionAnalyzer(grid_size=(4, 4))
                risk_assessor = RiskAssessor()
                risk_adapter = None
                
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
                    
                    if detection_mode == "🗣️ Head Mode — Experimental":
                        # Detection & DeepSORT head tracking
                        if frame_count == 1 or (frame_count % detect_interval == 0):
                            detections = detector.detect(frame, tiled=tiled_mode)
                            current_tracks = tracker.update(detections, frame)
                        else:
                            current_tracks = tracker.predict()
                        
                        visible_tracks = tracker.get_visible_tracks()
                        visible_heads = len(visible_tracks) if len(visible_tracks) > 0 else len(detections)
                        active_head_tracks = len(current_tracks)
                        
                        # Optical flow crowd motion analysis
                        grid_matrix, motion_summary = motion_analyzer.analyze_frame(frame)
                        
                        # Head-center 4x4 density & experimental risk calculation (using visible heads)
                        density_map, max_density, summary_stats = density_estimator.calculate_density(visible_tracks, frame.shape)
                        anomaly_score = motion_summary.get("anomaly_score", 0.0)
                        
                        risk_info = risk_adapter.calculate_experimental_head_risk(
                            total_heads=active_head_tracks,
                            max_head_cell=max_density,
                            frame_idx=frame_count,
                            anomaly_score=anomaly_score,
                            visible_heads=visible_heads
                        )
                        
                        risk_level_str = risk_info["risk_level"]
                        combined_score = risk_info["smoothed_score"]
                        person_count = active_head_tracks
                        avg_speed = motion_summary.get("avg_speed", 0.0)
                        dominant_dir = motion_summary.get("dominant_direction", "STATIONARY")
                        cam_motion = motion_summary.get("camera_motion_detected", False)
                        data_quality_score = 1.0
                        growth_rate = 0.0
                        raw_risk_score = risk_info.get("raw_score", combined_score)
                        
                        # Thermal heatmap background layer (from visible heads)
                        heatmap_base, _ = generate_heatmap(frame, visible_tracks, draw_grid=False)
                        
                        # Head Mode HUD Annotations (drawing visible tracks only)
                        annotated_frame = FrameAnnotator.create_head_dashboard_frame(
                            heatmap_base,
                            {
                                "visible_heads": visible_heads,
                                "person_count": active_head_tracks,
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
                            tracks=visible_tracks
                        )
                    else:
                        # Detection & DeepSORT person tracking
                        if frame_count == 1 or (frame_count % detect_interval == 0):
                            detections = detector.detect(frame)
                            current_tracks = tracker.update(detections, frame)
                        else:
                            current_tracks = tracker.predict()
                        
                        visible_heads = 0
                        active_head_tracks = 0
                        
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
                        raw_risk_score = risk_res.get("raw_score", combined_score)
                        
                        # Thermal heatmap background layer
                        heatmap_base, _ = generate_heatmap(frame, current_tracks, draw_grid=False)
                        
                        # Standard Person Mode Annotations
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
                    if detection_mode == "🗣️ Head Mode — Experimental":
                        metrics_payload = {
                            "mode": "HEAD_EXPERIMENTAL",
                            "visible_heads": visible_heads,
                            "active_head_tracks": active_head_tracks,
                            "max_head_density": max_density,
                            "head_risk_level": risk_level_str,
                            "head_smoothed_score": combined_score,
                            "head_raw_score": raw_risk_score,
                            "person_count": 0,
                            "density": max_density,
                            "max_density": max_density,
                            "anomaly": anomaly_score,
                            "anomaly_score": anomaly_score,
                            "risk": risk_level_str,
                            "risk_level": risk_level_str,
                            "combined_score": combined_score,
                            "raw_score": raw_risk_score,
                            "smoothed_score": combined_score,
                            "data_quality_score": 1.0,
                            "growth_rate": 0.0,
                            "avg_speed": avg_speed,
                            "max_speed": motion_summary.get("max_speed", 0.0),
                            "dominant_direction": dominant_dir,
                            "camera_motion_detected": cam_motion,
                            "sudden_movement_count": 0,
                            "fps": avg_fps,
                            "last_frame_time": datetime.now().isoformat()
                        }
                    else:
                        metrics_payload = {
                            "person_count": person_count,
                            "density": max_density,
                            "max_density": max_density,
                            "anomaly": anomaly_score,
                            "anomaly_score": anomaly_score,
                            "risk": risk_level_str,
                            "risk_level": risk_level_str,
                            "combined_score": combined_score,
                            "raw_score": raw_risk_score,
                            "smoothed_score": risk_res.get("smoothed_score", combined_score),
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
                        if detection_mode == "🗣️ Head Mode — Experimental":
                            status_box.warning(f"🗣️ EXPERIMENTAL HEAD RISK: {risk_level_str} | Score: {combined_score:.1f} | Visible Heads: {visible_heads} | Active Tracks: {active_head_tracks} | {cam_text}")
                        else:
                            if risk_level_str == "High":
                                status_box.error(f"🔴 HIGH RISK! Score: {combined_score:.1f} | Influx: {growth_rate:.1f} p/s | {cam_text}")
                            elif risk_level_str == "Medium":
                                status_box.warning(f"🟡 Medium Risk - Score: {combined_score:.1f} | Speed: {avg_speed:.1f} px/f | {cam_text}")
                            else:
                                status_box.success(f"🟢 Normal - Score: {combined_score:.1f} | Speed: {avg_speed:.1f} px/f | Heading: {dominant_dir} | {cam_text}")
                        
                        risk_colors = {"Low": "#00ff88", "LOW": "#00ff88", "Medium": "#ffaa00", "MEDIUM": "#ffaa00", "High": "#ff0000", "HIGH": "#ff0000"}
                        color = risk_colors.get(risk_level_str, "#666")
                        
                        card_title = "EXPERIMENTAL HEAD RISK PROXY" if detection_mode == "🗣️ Head Mode — Experimental" else risk_level_str.upper()
                        risk_placeholder.markdown(f"""
                        <div style="background:#1a1a2e; padding:15px; border-radius:10px; 
                                    text-align:center; border:3px solid {color}; margin-bottom:10px;">
                            <h3 style="color:{color}; margin:0;">{card_title}</h3>
                            <h1 style="color:{color}; margin:5px 0;">{combined_score:.1f}</h1>
                            <p style="margin:0; font-size:0.9em;">Speed: {avg_speed:.1f} px/f ({dominant_dir})</p>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        if detection_mode == "🗣️ Head Mode — Experimental":
                            person_metric.metric("🗣️ Visible Heads", visible_heads, delta=f"{active_head_tracks} active tracks", delta_color="off")
                            density_metric.metric("📊 Max Head Density", f"{max_density} heads/cell")
                        else:
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
                        
                        count_chart_label = "Heads" if detection_mode == "🗣️ Head Mode — Experimental" else "Persons"
                        df2 = pd.DataFrame({
                            "Time": list(st.session_state.time_history),
                            count_chart_label: list(st.session_state.person_history),
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

# ========== MODE 2: MULTI-CAMERA COMMAND CENTER ==========
elif mode == "🖥️ Multi-Camera Command Center (CCTV Grid)":
    from src.multi_camera_manager import MultiCameraManager

    if st.session_state.is_monitoring:
        st.subheader("🖥️ Multi-Camera CCTV Command Center Grid")
        system_banner = st.empty()
        alert_center_ph = st.empty()
        
        mode_key = "HEAD" if detection_mode == "🗣️ Head Mode — Experimental" else "PERSON"
        if mode_key == "HEAD":
            st.warning("⚠️ EXPERIMENTAL MODE — HEAD DETECTION ACTIVE across multi-camera streams.")
            
        multi_cam = MultiCameraManager(
            detection_mode=mode_key,
            device=device,
            detect_interval=detect_interval,
            tiled_mode=tiled_mode
        )
        st.session_state.multi_cam = multi_cam
        
        # Synchronize UI sidebar camera selections with MultiCameraManager before starting
        ui_cams = st.session_state.get("current_ui_cameras", updated_cameras)
        if ui_cams:
            with open(config_path, "w") as f:
                json.dump({"cameras": ui_cams}, f, indent=2)
            for cam_item in ui_cams:
                multi_cam.reconfigure_camera(
                    cam_item["id"],
                    cam_item["source"],
                    source_type=cam_item["source_type"],
                    name=cam_item["name"],
                    device_name=cam_item.get("device_name"),
                    enabled=cam_item["enabled"]
                )
        
        online_count = multi_cam.start_all_cameras()
        
        # Temporary Runtime Debug Output (Requirement 3)
        with st.expander("🔍 CCTV Grid Runtime Camera Diagnostics", expanded=True):
            for cam in multi_cam.cameras.values():
                dbg_info = cam.get_debug_info()
                st.write(
                    f"**{cam.id}** ({cam.name}) | "
                    f"UI Source Type: `{cam.source_type}` | UI Source: `{cam.source}` | "
                    f"Manager Source Type: `{dbg_info['configured_source_type']}` | Manager Source: `{dbg_info['configured_source']}` | "
                    f"Capture Open: `{dbg_info['capture_opened']}` | Status: `{cam.status}`"
                )
        
        if online_count == 0:
            st.error("🔴 Error: No camera sources could be opened.")
            st.session_state.is_monitoring = False
        else:
            metrics_logger = MetricsLogger()
            alert_manager = None
            if enable_alerts and fb_initialized:
                try:
                    alert_manager = FirebaseAlertManager()
                    if multi_cam.alert_manager:
                        multi_cam.alert_manager.fb_manager = alert_manager
                except Exception:
                    pass
            
            # Setup 2x2 grid layout
            cam_list = list(multi_cam.cameras.values())
            
            row1_cams = cam_list[:2]
            row2_cams = cam_list[2:4]
            
            grid_video_ph = {}
            grid_metric_ph = {}
            
            # Row 1
            col1, col2 = st.columns(2)
            for i, cam in enumerate(row1_cams):
                target_col = col1 if i == 0 else col2
                with target_col:
                    st.markdown(f"### 🎥 `{cam.id}`: {cam.name}")
                    grid_video_ph[cam.id] = st.empty()
                    grid_metric_ph[cam.id] = st.empty()
                    
            # Row 2
            if row2_cams:
                col3, col4 = st.columns(2)
                for i, cam in enumerate(row2_cams):
                    target_col = col3 if i == 0 else col4
                    with target_col:
                        st.markdown(f"### 🎥 `{cam.id}`: {cam.name}")
                        grid_video_ph[cam.id] = st.empty()
                        grid_metric_ph[cam.id] = st.empty()
            
            last_firebase_update = 0
            
            try:
                while st.session_state.is_monitoring:
                    frames_dict = multi_cam.step_all()
                    if not frames_dict:
                        st.warning("All camera streams completed or disconnected.")
                        st.session_state.is_monitoring = False
                        break
                        
                    # 1. Update overall risk banner
                    sys_risk = multi_cam.get_overall_system_risk()
                    overall_level = sys_risk["overall_risk_level"]
                    highest_id = sys_risk["highest_risk_camera_id"]
                    highest_name = sys_risk["highest_risk_camera_name"]
                    highest_score = sys_risk["highest_risk_score"]
                    active_cams = sys_risk["active_camera_count"]
                    
                    if overall_level == "HIGH":
                        system_banner.error(f"🔴 **COMMAND CENTER OVERALL STATUS: HIGH RISK** | Highest Risk Stream: **{highest_id} ({highest_name})** | Risk Score: **{highest_score:.1f}** | Active CCTV Feeds: **{active_cams}**")
                    elif overall_level == "MEDIUM":
                        system_banner.warning(f"🟡 **COMMAND CENTER OVERALL STATUS: MEDIUM RISK** | Highest Risk Stream: **{highest_id} ({highest_name})** | Risk Score: **{highest_score:.1f}** | Active CCTV Feeds: **{active_cams}**")
                    else:
                        system_banner.success(f"🟢 **COMMAND CENTER OVERALL STATUS: NORMAL / LOW RISK** | Active CCTV Feeds: **{active_cams}**")
                    
                    # 1b. Render Alert Center Panel
                    active_alts = multi_cam.get_active_alerts()
                    if active_alts:
                        alt_htmls = []
                        for alt in active_alts:
                            b_col = "#ffaa00" if alt.risk_level == "MEDIUM" else "#ff0000"
                            bg_col = "#2a2000" if alt.risk_level == "MEDIUM" else "#3a0000"
                            badge_lbl = f"🟡 MEDIUM ({alt.risk_score:.1f})" if alt.risk_level == "MEDIUM" else f"🔴 HIGH ({alt.risk_score:.1f})"
                            if alt.status == "ESCALATED":
                                badge_lbl = f"🚨 ESCALATED HIGH ({alt.risk_score:.1f})"
                            alt_htmls.append(f"""
                            <div style="background:{bg_col}; border:1px solid {b_col}; padding:6px 10px; border-radius:6px; margin-bottom:4px; font-size:0.85em;">
                                <b>{alt.camera_id}</b> ({alt.camera_name}) &nbsp;|&nbsp;
                                <span style="color:{b_col}; font-weight:bold;">{badge_lbl}</span> &nbsp;|&nbsp;
                                <span style="color:#eee;">Reason: {alt.reason}</span> &nbsp;|&nbsp;
                                <span style="color:#aaa;">Status: {alt.status}</span>
                            </div>
                            """)
                        alert_center_ph.markdown(
                            f"**🚨 Active CCTV Alert Events ({len(active_alts)}):**\n" + "".join(alt_htmls),
                            unsafe_allow_html=True
                        )
                    else:
                        alert_center_ph.markdown("🟢 *No Active Risk Alerts Across CCTV Streams*", unsafe_allow_html=True)
                    
                    # 2. Update per-camera display and telemetry across all cameras
                    for cam_id, cam in multi_cam.cameras.items():
                        if cam.source_type == "webcam":
                            src_badge_str = f"📷 WEBCAM: {get_camera_display_name(cam.source, cam.device_name)}"
                        elif cam.source_type == "rtsp":
                            src_badge_str = "🌐 IP CAMERA (RTSP)"
                        else:
                            src_badge_str = "📁 RECORDED VIDEO"
                        dbg_info = cam.get_debug_info()
                        
                        if cam.status == "ONLINE" and cam_id in frames_dict:
                            frame_out = frames_dict[cam_id]
                            
                            # High-Speed Web JPEG Stream Compression
                            display_frame = cv2.resize(frame_out, (640, 360))
                            _, jpeg_buffer = cv2.imencode('.jpg', display_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 75])
                            grid_video_ph[cam_id].image(jpeg_buffer.tobytes(), use_container_width=True)
                            
                            risk_colors = {"LOW": "#00ff88", "MEDIUM": "#ffaa00", "HIGH": "#ff0000", "UNKNOWN": "#666"}
                            badge_color = risk_colors.get(cam.risk_level, "#666")
                            
                            count_label = "Visible Heads" if mode_key == "HEAD" else "Tracked Persons"
                            count_val = cam.visible_count if mode_key == "HEAD" else cam.active_count
                            
                            grid_metric_ph[cam_id].markdown(f"""
                            <div style="background:#1a1a2e; padding:10px; border-radius:8px; border:2px solid {badge_color}; margin-bottom:15px;">
                                <div style="display:flex; justify-content:space-between; align-items:center;">
                                    <span style="color:{badge_color}; font-weight:bold; font-size:1.0em;">RISK: {cam.risk_level} ({cam.risk_score:.1f})</span>
                                    <span style="color:#aaa; font-size:0.85em;">{src_badge_str} | FPS: {cam.fps:.1f}</span>
                                </div>
                                <div style="margin-top:5px; font-size:0.88em; color:#ddd;">
                                    👥 {count_label}: <b>{count_val}</b> | 📊 Density: <b>{cam.max_density}</b> | 🏃 Speed: <b>{cam.avg_speed:.1f} px/f</b> ({cam.dominant_direction})
                                </div>
                                <div style="margin-top:4px; font-size:0.75em; color:#888; border-top:1px solid #333; padding-top:3px;">
                                    🔍 Active Src: <b>{dbg_info['active_source_type'].upper()}</b> ({dbg_info['active_source']}) | Capture Open: <b>{dbg_info['capture_opened']}</b>
                                </div>
                            </div>
                            """, unsafe_allow_html=True)
                            
                            # Log telemetry
                            cam_payload = multi_cam.get_camera_telemetry_payload(cam_id)
                            metrics_logger.log(cam_payload, cam.frame_count)
                            
                            if alert_manager and (time.time() - last_firebase_update > 1.0):
                                alert_manager.update_camera_telemetry(cam_id, cam_payload)
                                
                        elif cam.status == "CONNECTION FAILED":
                            grid_metric_ph[cam_id].markdown(f"""
                            <div style="background:#2a1a1a; padding:10px; border-radius:8px; border:2px solid #ff4444; margin-bottom:15px;">
                                <div style="display:flex; justify-content:space-between; align-items:center;">
                                    <span style="color:#ff4444; font-weight:bold;">🔴 CONNECTION FAILED</span>
                                    <span style="color:#aaa; font-size:0.85em;">{src_badge_str}</span>
                                </div>
                                <div style="margin-top:5px; font-size:0.88em; color:#ffaaaa;">
                                    ⚠️ {cam.error_message or 'Unable to open camera stream.'}
                                </div>
                                <div style="margin-top:4px; font-size:0.75em; color:#888; border-top:1px solid #442222; padding-top:3px;">
                                    🔍 Configured: <b>{dbg_info['configured_source_type'].upper()}</b> ({dbg_info['configured_source']}) | Capture Open: <b>{dbg_info['capture_opened']}</b>
                                </div>
                            </div>
                            """, unsafe_allow_html=True)
                            
                        elif cam.status == "DISABLED":
                            grid_metric_ph[cam_id].markdown(f"""
                            <div style="background:#1a1a1a; padding:10px; border-radius:8px; border:1px solid #555; margin-bottom:15px;">
                                <span style="color:#888; font-weight:bold;">⚪ CAMERA DISABLED</span>
                            </div>
                            """, unsafe_allow_html=True)
                            
                    if alert_manager and (time.time() - last_firebase_update > 1.0):
                        last_firebase_update = time.time()
                        
                    time.sleep(0.001)
                    
            finally:
                multi_cam.stop_all_cameras()
                st.info("⏹️ Command Center stopped cleanly.")
    else:
        st.info("👉 Click **▶️ Start Command Center** in the sidebar to initiate multi-camera monitoring grid.")

# ========== MODE 3: REMOTE TELEMETRY STREAM ==========
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