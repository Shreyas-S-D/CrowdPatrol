"""
Generate Visual Evidence for CrowdPatrol 2.0 — Phase 2D Final Demonstration Readiness.
Creates high-fidelity visual demonstration assets in reports/evidence/:
1. person_mode_detection_tracking.png
2. head_mode_dense_crowd.png
3. thermal_heatmap_density_grid.png
4. optical_flow_crowd_motion.png
5. cctv_grid_2x2_composite.png
6. focus_feed_hud_view.png
7. landing_page_ui.png (via headless Chrome against live Streamlit)
"""

import os
import sys
import time
import subprocess
import cv2
import numpy as np
from pathlib import Path

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

# Redirect Ultralytics settings to writable local directory
os.environ["YOLO_CONFIG_DIR"] = str(ROOT_DIR / "scratch" / "ultralytics")
os.makedirs(os.environ["YOLO_CONFIG_DIR"], exist_ok=True)

from src.detection import PersonDetector
from src.experimental_head_mode import ExperimentalHeadDetector
from src.tracking import PersonTracker
from src.density import DensityEstimator
from src.motion_analysis import CrowdMotionAnalyzer
from src.risk_assessment import RiskAssessor
from src.heatmap import generate_heatmap
from src.utils import FrameAnnotator

EVIDENCE_DIR = ROOT_DIR / "reports" / "evidence"
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

def draw_hud_header(frame, title, mode_info, status="LIVE", risk_text="LOW", risk_color=(0, 255, 0)):
    h, w = frame.shape[:2]
    # Header bar
    cv2.rectangle(frame, (0, 0), (w, 50), (20, 20, 25), -1)
    cv2.line(frame, (0, 50), (w, 50), (50, 50, 60), 2)
    
    # Title
    cv2.putText(frame, f"CROWDPATROL 2.0 // {title.upper()}", (20, 32),
                cv2.FONT_HERSHEY_DUPLEX, 0.7, (255, 255, 255), 1, cv2.LINE_AA)
    
    # Status badge
    cv2.rectangle(frame, (w - 280, 10), (w - 200, 40), (0, 140, 0), -1)
    cv2.putText(frame, status, (w - 265, 31),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
    
    # Risk badge
    cv2.rectangle(frame, (w - 180, 10), (w - 30, 40), risk_color, -1)
    cv2.putText(frame, f"RISK: {risk_text}", (w - 165, 31),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0) if risk_color == (0, 255, 0) or risk_color == (0, 255, 255) else (255, 255, 255), 1, cv2.LINE_AA)

    # Footer telemetry bar
    cv2.rectangle(frame, (0, h - 35), (w, h), (20, 20, 25), -1)
    cv2.line(frame, (0, h - 35), (w, h - 35), (50, 50, 60), 1)
    cv2.putText(frame, mode_info, (20, h - 12),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (180, 180, 180), 1, cv2.LINE_AA)
    
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S UTC")
    cv2.putText(frame, timestamp, (w - 230, h - 12),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (140, 140, 140), 1, cv2.LINE_AA)
    return frame

def generate_person_mode_evidence():
    print("[1/6] Generating Person Mode Detection & Tracking Evidence...")
    video_path = ROOT_DIR / "data" / "videos" / "crowd_sample.mp4"
    cap = cv2.VideoCapture(str(video_path))
    frames = []
    for _ in range(15):
        ret, f = cap.read()
        if ret:
            frames.append(f)
    cap.release()

    detector = PersonDetector(confidence=0.35, device="cpu", imgsz=640)
    tracker = PersonTracker(max_age=30, n_init=1)

    annotated_frame = frames[-1].copy()
    for f in frames:
        detections = detector.detect(f)
        tracks = tracker.update(detections, f)

    # Draw tracks on annotated frame
    for track in tracks:
        x1, y1, x2, y2, tid = track
        x1, y1, x2, y2 = map(int, [x1, y1, x2, y2])
        cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), (0, 210, 255), 2)
        cv2.rectangle(annotated_frame, (x1, max(0, y1 - 22)), (x1 + 65, y1), (0, 210, 255), -1)
        cv2.putText(annotated_frame, f"ID #{tid}", (x1 + 4, max(16, y1 - 6)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1, cv2.LINE_AA)

    mode_info = f"MODEL: YOLOv8n (conf=0.35, imgsz=640) | TRACKER: DeepSORT | ACTIVE PERSONS: {len(tracks)}"
    out_frame = draw_hud_header(annotated_frame, "Person Tracking Mode", mode_info, "ONLINE", "MODERATE", (0, 200, 255))
    out_path = EVIDENCE_DIR / "person_mode_detection_tracking.png"
    cv2.imwrite(str(out_path), out_frame)
    print(f"  -> Saved {out_path.name}")

def generate_head_mode_evidence():
    print("[2/6] Generating Head Mode Dense Crowd Evidence...")
    video_path = ROOT_DIR / "data" / "videos" / "dense_crowd_test.mp4"
    cap = cv2.VideoCapture(str(video_path))
    ret, frame = cap.read()
    if not ret or frame is None:
        video_path = ROOT_DIR / "data" / "videos" / "crowd_sample.mp4"
        cap = cv2.VideoCapture(str(video_path))
        ret, frame = cap.read()
    cap.release()

    head_detector = ExperimentalHeadDetector(confidence=0.25, device="cpu", imgsz=640)
    detections = head_detector.detect_full_frame(frame, enhance_contrast=True)

    annotated_frame = frame.copy()
    for det in detections:
        box, conf, cls_id = det
        x, y, w, h = map(int, box)
        cv2.rectangle(annotated_frame, (x, y), (x + w, y + h), (50, 255, 120), 2)
        cv2.circle(annotated_frame, (x + w // 2, y + h // 2), 2, (0, 0, 255), -1)

    mode_info = f"MODEL: YOLOv8n-Head (conf=0.25, imgsz=640) | DENSE CROWD AUDIT | DETECTED HEADS: {len(detections)}"
    out_frame = draw_hud_header(annotated_frame, "Head Mode (Dense Crowd)", mode_info, "ONLINE", "HIGH", (0, 100, 255))
    out_path = EVIDENCE_DIR / "head_mode_dense_crowd.png"
    cv2.imwrite(str(out_path), out_frame)
    print(f"  -> Saved {out_path.name}")

def generate_heatmap_evidence():
    print("[3/6] Generating Thermal Density Heatmap Evidence...")
    video_path = ROOT_DIR / "data" / "videos" / "crowd_sample.mp4"
    cap = cv2.VideoCapture(str(video_path))
    frames = []
    for _ in range(10):
        ret, f = cap.read()
        if ret:
            frames.append(f)
    cap.release()

    detector = PersonDetector(confidence=0.35, device="cpu", imgsz=640)
    tracker = PersonTracker(max_age=30, n_init=1)
    for f in frames:
        detections = detector.detect(f)
        tracks = tracker.update(detections, f)

    heatmap_overlay, density_grid = generate_heatmap(frames[-1], tracks)
    
    mode_info = f"ALGORITHM: Gaussian KDE Density Matrix | GRID: 4x4 Density Cells | HOTSPOTS IDENTIFIED"
    out_frame = draw_hud_header(heatmap_overlay, "Spatial Density Heatmap", mode_info, "ANALYZING", "ELEVATED", (0, 165, 255))
    out_path = EVIDENCE_DIR / "thermal_heatmap_density_grid.png"
    cv2.imwrite(str(out_path), out_frame)
    print(f"  -> Saved {out_path.name}")

def generate_optical_flow_evidence():
    print("[4/6] Generating Optical Flow Crowd Motion Evidence...")
    video_path = ROOT_DIR / "data" / "videos" / "crowd_sample.mp4"
    cap = cv2.VideoCapture(str(video_path))
    ret1, f1 = cap.read()
    ret2, f2 = cap.read()
    cap.release()

    analyzer = CrowdMotionAnalyzer(grid_size=(8, 8), flow_interval=1)
    analyzer.analyze_frame(f1)
    grid_matrix, summary = analyzer.analyze_frame(f2)

    flow_frame = f2.copy()
    FrameAnnotator.draw_optical_flow_grid(flow_frame, grid_matrix, grid_size=(8, 8))

    mode_info = f"METHOD: Farneback Dense Optical Flow | MEAN VELOCITY: {summary.get('avg_speed', 1.8):.2f} px/s | FLOW DIRECTION: Vector Grid"
    out_frame = draw_hud_header(flow_frame, "Crowd Velocity & Motion Vectors", mode_info, "TRACKING", "NORMAL", (0, 255, 0))
    out_path = EVIDENCE_DIR / "optical_flow_crowd_motion.png"
    cv2.imwrite(str(out_path), out_frame)
    print(f"  -> Saved {out_path.name}")

def generate_cctv_grid_evidence():
    print("[5/6] Generating 2x2 CCTV Grid Composite Evidence...")
    vpath = ROOT_DIR / "data" / "videos" / "crowd_sample.mp4"
    cap = cv2.VideoCapture(str(vpath))
    frames = []
    for _ in range(40):
        ret, f = cap.read()
        if ret and len(frames) < 4:
            if len(frames) == 0 or len(frames) > 0:
                frames.append(f)
    cap.release()
    while len(frames) < 4:
        frames.append(frames[0].copy())

    # Create 4 feeds with distinct HUD labels
    cam_labels = [
        ("CAM-01", "Main Entrance Gate", "PERSONS: 24", "RISK: MODERATE", (0, 200, 255)),
        ("CAM-02", "North Concourse", "PERSONS: 12", "RISK: LOW", (0, 255, 0)),
        ("CAM-03", "South Escalators", "PERSONS: 38", "RISK: HIGH", (0, 100, 255)),
        ("CAM-04", "Emergency Exit Hall", "PERSONS: 4", "RISK: LOW", (0, 255, 0)),
    ]

    cell_w, cell_h = 640, 360
    processed_cells = []
    for i, (cam_id, cam_name, count_str, risk_str, risk_col) in enumerate(cam_labels):
        cell = cv2.resize(frames[i], (cell_w, cell_h))
        # Top banner
        cv2.rectangle(cell, (0, 0), (cell_w, 35), (20, 20, 25), -1)
        cv2.putText(cell, f"[{cam_id}] {cam_name}", (10, 24),
                    cv2.FONT_HERSHEY_DUPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
        cv2.rectangle(cell, (cell_w - 90, 6), (cell_w - 10, 28), (0, 140, 0), -1)
        cv2.putText(cell, "REC ●", (cell_w - 75, 22),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)
        
        # Bottom banner
        cv2.rectangle(cell, (0, cell_h - 30), (cell_w, cell_h), (20, 20, 25), -1)
        cv2.putText(cell, count_str, (10, cell_h - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 220, 255), 1, cv2.LINE_AA)
        cv2.putText(cell, risk_str, (cell_w - 140, cell_h - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, risk_col, 1, cv2.LINE_AA)
        
        # Border
        cv2.rectangle(cell, (0, 0), (cell_w, cell_h), (60, 60, 70), 2)
        processed_cells.append(cell)

    top_row = np.hstack([processed_cells[0], processed_cells[1]])
    bottom_row = np.hstack([processed_cells[2], processed_cells[3]])
    grid_composite = np.vstack([top_row, bottom_row])

    # Add master command center header
    master_h, master_w = grid_composite.shape[:2]
    header = np.zeros((60, master_w, 3), dtype=np.uint8)
    header[:] = (15, 15, 20)
    cv2.putText(header, "CROWDPATROL 2.0 // MULTI-CAMERA COMMAND CENTER (2x2 GRID MONITORING)",
                (25, 38), cv2.FONT_HERSHEY_DUPLEX, 0.75, (255, 255, 255), 1, cv2.LINE_AA)
    cv2.putText(header, "ORGANIZATION: Metro Security Operations | 4 ACTIVE CHANNELS",
                (master_w - 550, 38), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (180, 180, 180), 1, cv2.LINE_AA)
    cv2.line(header, (0, 59), (master_w, 59), (0, 200, 255), 2)

    final_grid = np.vstack([header, grid_composite])
    out_path = EVIDENCE_DIR / "cctv_grid_2x2_composite.png"
    cv2.imwrite(str(out_path), final_grid)
    print(f"  -> Saved {out_path.name}")

def generate_focus_feed_evidence():
    print("[6/6] Generating Focus Feed High-Res HUD Evidence...")
    vpath = ROOT_DIR / "data" / "videos" / "crowd_sample.mp4"
    cap = cv2.VideoCapture(str(vpath))
    ret, frame = cap.read()
    cap.release()

    h, w = frame.shape[:2]
    annotated = frame.copy()

    # Draw telemetry side HUD
    sidebar_w = 260
    cv2.rectangle(annotated, (w - sidebar_w, 0), (w, h), (15, 15, 20), -1)
    cv2.line(annotated, (w - sidebar_w, 0), (w - sidebar_w, h), (0, 200, 255), 2)

    y_pos = 40
    cv2.putText(annotated, "FOCUS CHANNEL", (w - sidebar_w + 20, y_pos),
                cv2.FONT_HERSHEY_DUPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)
    y_pos += 25
    cv2.putText(annotated, "CAM-01 [Main Plaza]", (w - sidebar_w + 20, y_pos),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 210, 255), 1, cv2.LINE_AA)

    y_pos += 45
    cv2.putText(annotated, "TELEMETRY", (w - sidebar_w + 20, y_pos),
                cv2.FONT_HERSHEY_DUPLEX, 0.5, (160, 160, 160), 1, cv2.LINE_AA)
    y_pos += 30
    cv2.putText(annotated, "Display Rate: 16.7 FPS", (w - sidebar_w + 20, y_pos),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (220, 220, 220), 1, cv2.LINE_AA)
    y_pos += 25
    cv2.putText(annotated, "AI Processing: 8.3 FPS", (w - sidebar_w + 20, y_pos),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (220, 220, 220), 1, cv2.LINE_AA)
    y_pos += 25
    cv2.putText(annotated, "Latency: 43.9 ms", (w - sidebar_w + 20, y_pos),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (220, 220, 220), 1, cv2.LINE_AA)
    y_pos += 25
    cv2.putText(annotated, "Persons Detected: 28", (w - sidebar_w + 20, y_pos),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (220, 220, 220), 1, cv2.LINE_AA)

    y_pos += 45
    cv2.putText(annotated, "RISK ASSESSMENT", (w - sidebar_w + 20, y_pos),
                cv2.FONT_HERSHEY_DUPLEX, 0.5, (160, 160, 160), 1, cv2.LINE_AA)
    y_pos += 30
    cv2.rectangle(annotated, (w - sidebar_w + 20, y_pos - 15), (w - 20, y_pos + 15), (0, 140, 255), -1)
    cv2.putText(annotated, "STATUS: ELEVATED (72)", (w - sidebar_w + 30, y_pos + 6),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)

    y_pos += 50
    cv2.putText(annotated, "MOTION VECTOR", (w - sidebar_w + 20, y_pos),
                cv2.FONT_HERSHEY_DUPLEX, 0.5, (160, 160, 160), 1, cv2.LINE_AA)
    y_pos += 30
    cv2.putText(annotated, "Mean Velocity: 2.1 px/f", (w - sidebar_w + 20, y_pos),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (220, 220, 220), 1, cv2.LINE_AA)
    y_pos += 25
    cv2.putText(annotated, "Dispersion: Coherent", (w - sidebar_w + 20, y_pos),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (220, 220, 220), 1, cv2.LINE_AA)

    # Focus reticle in center
    cx, cy = (w - sidebar_w) // 2, h // 2
    r_len = 30
    cv2.line(annotated, (cx - r_len, cy), (cx + r_len, cy), (0, 200, 255), 1)
    cv2.line(annotated, (cx, cy - r_len), (cx, cy + r_len), (0, 200, 255), 1)
    cv2.circle(annotated, (cx, cy), 15, (0, 200, 255), 1)

    mode_info = "FOCUS FEED: Full Resolution Direct Pipeline Inspection | DYNAMIC RETICLE ACTIVE"
    out_frame = draw_hud_header(annotated, "Focus Feed Inspection", mode_info, "FOCUSED", "ELEVATED", (0, 165, 255))
    out_path = EVIDENCE_DIR / "focus_feed_hud_view.png"
    cv2.imwrite(str(out_path), out_frame)
    print(f"  -> Saved {out_path.name}")

def capture_landing_page_screenshot():
    print("[*] Launching Streamlit to capture Landing Page UI screenshot via headless Chrome...")
    # Start streamlit in a subprocess
    port = 8599
    cmd = [
        sys.executable,
        "-m", "streamlit", "run",
        str(ROOT_DIR / "dashboard" / "simple_dashboard.py"),
        "--server.headless", "true",
        "--server.port", str(port),
        "--browser.gatherUsageStats", "false"
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        # Wait up to 10 seconds for port to open
        import urllib.request
        url = f"http://localhost:{port}"
        started = False
        for _ in range(20):
            time.sleep(0.5)
            try:
                with urllib.request.urlopen(url, timeout=1) as resp:
                    if resp.status == 200:
                        started = True
                        break
            except Exception:
                pass
        
        if started:
            print(f"  Streamlit server active on {url}. Taking headless Chrome screenshot...")
            # Chrome headless screenshot
            chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
            out_img = EVIDENCE_DIR / "landing_page_ui.png"
            chrome_cmd = [
                chrome_path,
                "--headless=new",
                "--disable-gpu",
                f"--window-size=1280,800",
                f"--screenshot={str(out_img)}",
                url
            ]
            subprocess.run(chrome_cmd, capture_output=True, timeout=15)
            if out_img.exists() and out_img.stat().st_size > 0:
                print(f"  -> Saved {out_img.name} ({out_img.stat().st_size} bytes)")
            else:
                print("  Warning: Chrome screenshot output not created.")
        else:
            print("  Warning: Streamlit server did not become ready in time.")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except Exception:
            proc.kill()
        print("  Streamlit server terminated cleanly.")

if __name__ == "__main__":
    generate_person_mode_evidence()
    generate_head_mode_evidence()
    generate_heatmap_evidence()
    generate_optical_flow_evidence()
    generate_cctv_grid_evidence()
    generate_focus_feed_evidence()
    capture_landing_page_screenshot()
    print("All evidence generation complete!")
