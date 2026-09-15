# CrowdPatrol: Live Demonstration Script (5–7 Minutes)

This script provides a step-by-step guide for performing a live demonstration of CrowdPatrol for project evaluators and external examiners.

---

## DEMO OVERVIEW & TIMELINE

| Time | Stage / Topic | Demonstrated Action / Command | Key Feature Highlighted |
| :---: | :--- | :--- | :--- |
| **0:00 – 0:45** | 1. Introduction & Overview | Project statement & terminal setup | Architecture overview |
| **0:45 – 1:45** | 2. Pipeline Execution | `py -3 main.py --source 0 --detect-interval 3 --alerts` | YOLOv8 + DeepSORT + Optical Flow |
| **1:45 – 2:45** | 3. Live Feed Overlay Analysis | Inspect OpenCV preview window | Density grid, track IDs, quiver arrows |
| **2:45 – 3:45** | 4. Dashboard Launch & Metrics | `py -3 -m streamlit run dashboard/simple_dashboard.py` | 19-key telemetry payload sync |
| **3:45 – 4:45** | 5. Camera Motion Isolation | Pan camera manually in front of lens | Motion weights disengage, $C_{\text{data}} = 0.75$ |
| **4:45 – 5:30** | 6. Stale Telemetry & CSV Fallback | Terminate main script / disconnect network | `🟡 STALE DATA` & `🟠 Offline Fallback` |
| **5:30 – 6:30** | 7. Limitations & Q&A Conclusion | Wrap-up remarks & disclaimer notice | Academic prototype scope |

---

## STEP-BY-STEP DEMONSTRATION SCRIPT

### Phase 1: Preparation (Pre-Demo Terminal Check)
Ensure you are in the project root directory in PowerShell / Command Prompt:
```bash
cd "d:\Shreyas Files\AMC Engineering College\7th sem\Major Project\CrowdPatrol"
set PYTHONIOENCODING=utf-8
```

---

### Step 1: Project Introduction (0:00 – 0:45)
- **Presenter Verbal Script**:
  > *"Good morning panel. Today we are demonstrating CrowdPatrol, an experimental academic prototype for automated crowd density and motion-anomaly monitoring. Our pipeline processes live video, detects people via YOLOv8, tracks them via DeepSORT, estimates grid density, extracts optical flow vectors, and evaluates a 6-factor risk score with camera motion compensation."*

---

### Step 2: Start the Live Monitoring Pipeline (0:45 – 1:45)
Run the monitoring core from Terminal 1:
```bash
set PYTHONIOENCODING=utf-8 && py -3 main.py --source 0 --detect-interval 3 --alerts
```
*(If webcam is unavailable, demonstrate using recorded video sample)*:
```bash
set PYTHONIOENCODING=utf-8 && py -3 main.py --source data/videos/crowd_sample.mp4 --detect-interval 3
```

- **Presenter Verbal Script**:
  > *"We are launching `main.py` with detection interval set to 3. This means YOLOv8 detection runs every 3rd frame while DeepSORT steps Kalman predictions forward on intermediate frames, achieving smooth real-time execution at 20+ FPS on CPU."*

---

### Step 3: Demonstrate Live Feed Overlays (1:45 – 2:45)
Point out visual elements on the OpenCV preview window:
1. **Bounding Boxes & Track IDs**: Green boxes showing detected persons with persistent DeepSORT IDs (e.g. `ID: 1`, `ID: 2`).
2. **$4 \times 4$ Density Grid**: White grid overlay indicating person counts per cell.
3. **Optical Flow Quiver Arrows**: Cyan/red directional motion arrows displaying localized movement direction and speed.
4. **Risk Banner**: Top banner displaying `RISK LEVEL: LOW / MEDIUM / HIGH` and current smoothed score.

- **Presenter Verbal Script**:
  > *"Notice the green bounding boxes with DeepSORT track IDs that persist even when individuals move. The grid divides the screen into 16 zones to track density, while cyan vector quivers show crowd motion direction in real time."*

---

### Step 4: Launch Streamlit Live Dashboard (2:45 – 3:45)
Open Terminal 2 and launch the dashboard:
```bash
py -3 -m streamlit run dashboard/simple_dashboard.py
```

Observe browser window opening at `http://localhost:8501`:
1. **Connection Badge**: Shows `🟢 Connected (Live RTDB)`.
2. **Risk Score Meter**: Displays continuous score, Influx Rate (`p/s`), and Data Quality (`100%`).
3. **Motion Metrics**: Displays `Avg Speed` (`px/f`) and `Dominant Direction` (e.g., `NE`, `STATIONARY`).
4. **Trend Charts**: Live Plotly charts tracking Risk Score and Crowd Count history.

- **Presenter Verbal Script**:
  > *"Our Streamlit dashboard receives a 19-key telemetry snapshot synchronized every second over Firebase RTDB. Here we see real-time metrics, data quality scores, motion speed in pixels per frame, and live trend charts."*

---

### Step 5: Demonstrate Camera Motion Factor Isolation (3:45 – 4:45)
Manually pan or tilt the camera webcam:
1. Observe global camera motion detected in terminal log (`Camera Motion Detected = True`).
2. Observe dashboard status banner changing to `🎥 Camera Pan Active (Motion Factors Suppressed)`.
3. Point out that Data Quality Score drops to $75\%$ ($C_{\text{data}} = 0.75$).
4. Highlight that the risk score **does not** spike falsely due to camera movement.

- **Presenter Verbal Script**:
  > *"When a security camera pans, optical flow detects global background motion. To prevent camera movement from artificially boosting the risk score, CrowdPatrol disengages motion-derived factors and relies strictly on spatial density and growth rate. Notice how the score remains stable while Data Quality reflects 75%."*

---

### Step 6: Demonstrate Stale Data & Offline CSV Fallback (4:45 – 5:30)

#### A. Stale Data Demonstration:
Press `Ctrl+C` in Terminal 1 to stop `main.py`:
- Within 10 seconds, observe dashboard connection badge changing to `🟡 Telemetry Stale (Pipeline Paused)`.

#### B. Offline CSV Fallback Demonstration:
Disconnect network connection (or block Firebase URL):
- Observe dashboard connection badge changing to `🟠 Offline Mode (Local CSV)`.
- Point out that metrics are loaded smoothly from `output/metrics_log.csv` without throwing unhandled exceptions.

- **Presenter Verbal Script**:
  > *"If the monitoring core pauses, our heartbeat detector flags telemetry as stale after 10 seconds. If network connection drops completely, the dashboard seamlessly falls back to reading local metrics from `output/metrics_log.csv` without crashing."*

---

### Step 7: Limitations & Conclusion (5:30 – 6:30)
- **Presenter Verbal Script**:
  > *"To conclude our demonstration, CrowdPatrol is an experimental academic prototype. Velocity metrics are expressed in image-space pixels per frame, and the system provides situational indications for tested benchmark scenarios without claiming stampede prediction. Thank you, and we welcome your questions."*

---

## DEMONSTRATION TROUBLESHOOTING CHECKLIST

| Problem | Cause | Quick Fix Command |
| :--- | :--- | :--- |
| **Camera fails to open** | Webcam occupied or missing | Use recorded video: `py -3 main.py --source data/videos/crowd_sample.mp4` |
| **UnicodeEncodeError in terminal** | Windows console encoding | Run: `set PYTHONIOENCODING=utf-8` before command |
| **Streamlit does not open** | Port 8501 blocked | Run: `py -3 -m streamlit run dashboard/simple_dashboard.py --server.port 8502` |
| **Firebase connection fails** | Missing credentials JSON | Dashboard automatically uses CSV fallback; demonstration proceeds normally |
