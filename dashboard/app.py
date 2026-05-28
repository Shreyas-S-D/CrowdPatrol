import streamlit as st
import cv2
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import time
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from src.detection import PersonDetector
from src.tracking import PersonTracker
from src.density import DensityEstimator
from src.risk_assessment import RiskAssessor
from src.utils import MetricsLogger, FrameAnnotator

# Page config
st.set_page_config(
    page_title="CrowdPatrol Dashboard",
    page_icon="🚨",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .risk-low { color: #00ff00; font-weight: bold; }
    .risk-medium { color: #ffaa00; font-weight: bold; }
    .risk-high { color: #ff0000; font-weight: bold; font-size: 1.2em; }
    .metric-card {
        background: #1a1a2e;
        padding: 20px;
        border-radius: 10px;
        text-align: center;
    }
    .alert-banner {
        padding: 15px;
        border-radius: 8px;
        margin: 10px 0;
        animation: pulse 2s infinite;
    }
    @keyframes pulse {
        0% { opacity: 1; }
        50% { opacity: 0.7; }
        100% { opacity: 1; }
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'system_running' not in st.session_state:
    st.session_state.system_running = False
if 'metrics_history' not in st.session_state:
    st.session_state.metrics_history = []
if 'alerts' not in st.session_state:
    st.session_state.alerts = []

class DashboardApp:
    def __init__(self):
        self.detector = None
        self.tracker = None
        self.density_estimator = None
        self.risk_assessor = None
        self.metrics_logger = None
        
    def initialize_system(self, model_path, device, confidence):
        """Initialize detection and tracking components"""
        self.detector = PersonDetector(model_path, confidence, device)
        self.tracker = PersonTracker(max_age=30)
        self.density_estimator = DensityEstimator(grid_size=(4, 4))
        self.risk_assessor = RiskAssessor()
        self.metrics_logger = MetricsLogger()
        st.session_state.system_running = True
    
    def run(self):
        """Main dashboard UI"""
        # Header
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            st.title("🚨 CrowdPatrol Dashboard")
        with col2:
            st.metric("System Status", "Active" if st.session_state.system_running else "Idle")
        with col3:
            if st.button("🛑 Emergency Stop", type="primary", use_container_width=True):
                st.session_state.system_running = False
                st.rerun()
        
        # Sidebar
        with st.sidebar:
            st.header("⚙️ Configuration")
            
            # Video source
            video_source = st.selectbox(
                "Video Source",
                ["Webcam", "IP Camera", "Video File", "Demo Video"]
            )
            
            if video_source == "IP Camera":
                rtsp_url = st.text_input("RTSP URL", "rtsp://username:password@ip:port/stream")
            elif video_source == "Video File":
                uploaded_file = st.file_uploader("Upload Video", type=["mp4", "avi", "mov"])
            
            st.divider()
            
            # Model settings
            model_type = st.selectbox("Detection Model", ["yolov8n", "yolov8s", "yolov8m"])
            confidence = st.slider("Confidence Threshold", 0.1, 1.0, 0.5, 0.05)
            device = st.radio("Device", ["cpu", "cuda"], horizontal=True)
            
            st.divider()
            
            # Density thresholds
            st.subheader("Density Thresholds")
            low_thresh = st.number_input("Low", 1, 50, 5)
            medium_thresh = st.number_input("Medium", 1, 100, 15)
            high_thresh = st.number_input("High", 1, 200, 30)
            
            st.divider()
            
            # Alert settings
            st.subheader("Alert Settings")
            alerts_enabled = st.toggle("Enable Alerts", False)
            email_alert = st.toggle("Email Alerts", False)
            sms_alert = st.toggle("SMS Alerts", False)
            
            st.divider()
            
            # Control buttons
            col_start, col_stop = st.columns(2)
            with col_start:
                if st.button("▶️ Start Monitoring", use_container_width=True):
                    self.initialize_system(f"{model_type}.pt", device, confidence)
            with col_stop:
                if st.button("⏹️ Stop", use_container_width=True):
                    st.session_state.system_running = False
        
        # Main content area
        if st.session_state.system_running:
            self.show_live_dashboard()
        else:
            self.show_placeholder()
    
    def show_live_dashboard(self):
        """Display live monitoring dashboard"""
        # Create three columns
        col_video, col_metrics = st.columns([2, 1])
        
        with col_video:
            st.subheader("📹 Live Feed")
            video_placeholder = st.empty()
        
        with col_metrics:
            st.subheader("📊 Real-time Metrics")
            metrics_placeholder = st.empty()
            alert_placeholder = st.empty()
        
        # Charts row
        st.divider()
        col_chart1, col_chart2 = st.columns(2)
        
        with col_chart1:
            density_chart = st.empty()
        with col_chart2:
            risk_chart = st.empty()
        
        # Simulate real-time updates (replace with actual video processing)
        while st.session_state.system_running:
            # This is where you'd process actual video frames
            # For now, showing the dashboard structure
            with video_placeholder.container():
                st.image("https://via.placeholder.com/640x360/1a1a2e/00ff00?text=CrowdPatrol+Live+Feed",
                        use_container_width=True)
            
            with metrics_placeholder.container():
                self.render_metrics()
            
            time.sleep(1)
    
    def render_metrics(self):
        """Render real-time metrics"""
        # Simulated metrics (replace with actual data)
        metrics = {
            "person_count": np.random.randint(10, 100),
            "max_density": np.random.randint(5, 40),
            "risk_level": np.random.choice(["Low", "Medium", "High"], p=[0.6, 0.3, 0.1]),
            "combined_score": np.random.randint(10, 90)
        }
        
        # Risk indicator
        risk_color = {"Low": "green", "Medium": "orange", "High": "red"}
        color = risk_color.get(metrics["risk_level"], "gray")
        
        st.markdown(f"""
        <div class="metric-card">
            <h3 style="color: {color};">RISK LEVEL: {metrics['risk_level'].upper()}</h3>
            <h2 style="color: {color};">{metrics['combined_score']}/100</h2>
        </div>
        """, unsafe_allow_html=True)
        
        # Person count and density
        col1, col2 = st.columns(2)
        with col1:
            st.metric("👥 Person Count", metrics["person_count"])
        with col2:
            st.metric("📊 Max Density", metrics["max_density"])
        
        # Anomaly indicator
        anomaly = np.random.random()
        st.progress(anomaly, text=f"Anomaly Score: {anomaly:.2f}")
    
    def show_placeholder(self):
        """Show placeholder when system is idle"""
        st.info("👈 Configure settings and click 'Start Monitoring' to begin")
        
        # Show demo cards
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown("""
            ### 🎯 Detection
            YOLOv8-based real-time person detection
            """)
        with col2:
            st.markdown("""
            ### 📈 Tracking
            DeepSORT multi-object tracking
            """)
        with col3:
            st.markdown("""
            ### ⚠️ Risk Assessment
            Density + anomaly scoring
            """)


class AlertDashboard:
    """Alert history and analytics view"""
    
    @staticmethod
    def show():
        st.title("📋 Alert History")
        
        # Time filter
        col1, col2 = st.columns(2)
        with col1:
            date_from = st.date_input("From", datetime.now() - timedelta(days=7))
        with col2:
            date_to = st.date_input("To", datetime.now())
        
        # Alert summary cards
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Alerts", "24")
        with col2:
            st.metric("High Risk", "3", delta="2", delta_color="inverse")
        with col3:
            st.metric("Medium Risk", "8", delta="-1", delta_color="inverse")
        with col4:
            st.metric("Avg Response", "2.3 min")
        
        # Alert timeline chart
        st.subheader("Alert Timeline")
        
        # Sample data - replace with actual alert data
        df = pd.DataFrame({
            'timestamp': pd.date_range(start='2024-01-01', periods=50, freq='H'),
            'risk_score': np.random.randint(30, 100, 50),
            'risk_level': np.random.choice(['Low', 'Medium', 'High'], 50)
        })
        
        fig = px.scatter(df, x='timestamp', y='risk_score', color='risk_level',
                        color_discrete_map={'Low': 'green', 'Medium': 'orange', 'High': 'red'},
                        title='Risk Score Over Time')
        st.plotly_chart(fig, use_container_width=True)
        
        # Alert log table
        st.subheader("Alert Log")
        st.dataframe(df.sort_values('timestamp', ascending=False), use_container_width=True)


class AnalyticsDashboard:
    """Historical analytics view"""
    
    @staticmethod
    def show():
        st.title("📊 Analytics")
        
        # Date range selector
        date_range = st.date_input(
            "Select Date Range",
            [datetime.now() - timedelta(days=7), datetime.now()]
        )
        
        # Key metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Persons Tracked", "12,450")
        with col2:
            st.metric("Peak Density", "45 persons/zone")
        with col3:
            st.metric("Avg Risk Score", "34.2")
        with col4:
            st.metric("Uptime", "99.8%")
        
        # Charts row
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Density Heatmap")
            # Sample density heatmap
            density_data = np.random.rand(10, 10) * 50
            fig = px.imshow(density_data, color_continuous_scale='hot',
                          title='Average Density Distribution')
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            st.subheader("Risk Distribution")
            risk_data = pd.DataFrame({
                'Risk Level': ['Low', 'Medium', 'High'],
                'Count': [65, 25, 10]
            })
            fig = px.pie(risk_data, values='Count', names='Risk Level',
                        color='Risk Level',
                        color_discrete_map={'Low': 'green', 'Medium': 'orange', 'High': 'red'})
            st.plotly_chart(fig, use_container_width=True)
        
        # Hourly trend
        st.subheader("Hourly Crowd Density Trend")
        hourly_data = pd.DataFrame({
            'Hour': range(24),
            'Avg Density': np.random.randint(5, 40, 24),
            'Max Density': np.random.randint(10, 60, 24)
        })
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=hourly_data['Hour'], y=hourly_data['Avg Density'],
                                name='Avg Density', line=dict(color='blue')))
        fig.add_trace(go.Scatter(x=hourly_data['Hour'], y=hourly_data['Max Density'],
                                name='Max Density', line=dict(color='red')))
        fig.update_layout(xaxis_title='Hour of Day', yaxis_title='Density')
        st.plotly_chart(fig, use_container_width=True)


# Main app
def main():
    st.sidebar.title("🧭 Navigation")
    page = st.sidebar.radio(
        "Go to",
        ["🎥 Live Monitor", "📋 Alert History", "📊 Analytics", "⚙️ Settings"],
        label_visibility="collapsed"
    )
    
    if page == "🎥 Live Monitor":
        app = DashboardApp()
        app.run()
    elif page == "📋 Alert History":
        AlertDashboard.show()
    elif page == "📊 Analytics":
        AnalyticsDashboard.show()
    elif page == "⚙️ Settings":
        st.title("⚙️ Settings")
        st.info("Configuration settings page")
        
        with st.expander("Detection Settings"):
            st.selectbox("Model", ["yolov8n", "yolov8s", "yolov8m", "yolov8l"])
            st.slider("Confidence", 0.1, 1.0, 0.5)
            st.radio("Device", ["cpu", "cuda"])
        
        with st.expander("Alert Settings"):
            st.toggle("Enable Alerts")
            st.number_input("Alert Cooldown (seconds)", 10, 600, 60)
            
            st.subheader("Notification Methods")
            st.checkbox("Email")
            st.checkbox("SMS (Twilio)")
            st.checkbox("Push Notification")
        
        with st.expander("Data Retention"):
            st.number_input("Log Retention (days)", 1, 365, 30)
            st.toggle("Save Processed Video")


if __name__ == "__main__":
    main()