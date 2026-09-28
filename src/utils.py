import cv2
import numpy as np
from datetime import datetime
import os
import json
import csv
from pathlib import Path

class VideoProcessor:
    """Utility class for video I/O operations"""
    
    @staticmethod
    def get_video_source(source):
        """
        Determine video source type and return cv2.VideoCapture object.
        source: 0 for webcam, 'video.mp4' for file, 'rtsp://...' for IP camera
        """
        if isinstance(source, int):
            return cv2.VideoCapture(source)
        elif isinstance(source, str):
            if source.isdigit():
                return cv2.VideoCapture(int(source))
            return cv2.VideoCapture(source)
        else:
            try:
                return cv2.VideoCapture(int(source))
            except Exception:
                return cv2.VideoCapture(str(source))
    
    @staticmethod
    def get_video_info(cap):
        """Get video metadata"""
        return {
            "fps": int(cap.get(cv2.CAP_PROP_FPS)),
            "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            "total_frames": int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        }
    
    @staticmethod
    def create_video_writer(output_path, fps, width, height):
        """Create VideoWriter for saving output"""
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        return cv2.VideoWriter(output_path, fourcc, fps, (width, height))


class MetricsLogger:
    """Log detection, density, and risk metrics for analysis"""
    
    def __init__(self, log_dir="logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.csv_file = self.log_dir / f"metrics_{self.session_id}.csv"
        self._init_csv()
    
    def _init_csv(self):
        """Initialize CSV with headers"""
        with open(self.csv_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                "timestamp", "camera_id", "camera_name", "person_count", "max_density", 
                "anomaly_score", "risk_level", "combined_score", "frame_number"
            ])
    
    def log(self, metrics, frame_number):
        """Log metrics for current frame"""
        with open(self.csv_file, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                datetime.now().isoformat(),
                metrics.get("camera_id", "CAM-00"),
                metrics.get("camera_name", "Single Stream"),
                metrics.get("person_count", 0),
                metrics.get("density", metrics.get("max_density", 0)),
                metrics.get("anomaly", metrics.get("anomaly_score", 0)),
                metrics.get("risk", metrics.get("risk_level", "Low")),
                metrics.get("combined_score", 0),
                frame_number
            ])
    
    def save_alert_event(self, metrics):
        """Save high-risk events separately"""
        alert_file = self.log_dir / f"alerts_{self.session_id}.json"
        alert_data = {
            "timestamp": datetime.now().isoformat(),
            "risk_level": metrics.get("risk"),
            "person_count": metrics.get("person_count"),
            "max_density": metrics.get("density"),
            "anomaly_score": metrics.get("anomaly"),
            "combined_score": metrics.get("combined_score")
        }
        
        events = []
        if alert_file.exists():
            with open(alert_file, 'r') as f:
                events = json.load(f)
        
        events.append(alert_data)
        
        with open(alert_file, 'w') as f:
            json.dump(events, f, indent=2)


class FrameAnnotator:
    """Advanced visualization utilities with high-readability HUD and clean overlays"""
    
    @staticmethod
    def draw_risk_banner(frame, risk_level, combined_score):
        """Draw top status banner on frame"""
        h, w = frame.shape[:2]
        banner_height = 45
        
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (w, banner_height), (15, 20, 28), -1)
        frame = cv2.addWeighted(overlay, 0.85, frame, 0.15, 0)
        
        text = f"CROWDPATROL | RISK: {str(risk_level).upper()} | SCORE: {combined_score:.1f}"
        cv2.putText(frame, text, (15, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2, cv2.LINE_AA)
        return frame
    
    @staticmethod
    def draw_density_zones(frame, density_map, grid_size=(4, 4), risk_level="LOW"):
        """Draw subtle grid lines, cell counts, and highlight primary risk zone."""
        from src.alert_manager import extract_spatial_risk_info
        h, w = frame.shape[:2]
        cell_h, cell_w = max(1, h // grid_size[0]), max(1, w // grid_size[1])
        ROW_LETTERS = ['A', 'B', 'C', 'D']
        
        spatial_info = extract_spatial_risk_info(density_map)
        primary_zone = spatial_info["primary_risk_zone"]
        primary_val = spatial_info["primary_zone_density"]
        
        for i in range(min(grid_size[0], len(ROW_LETTERS))):
            for j in range(grid_size[1]):
                x1, y1 = j * cell_w, i * cell_h
                x2, y2 = (j + 1) * cell_w, (i + 1) * cell_h
                cell_id = f"{ROW_LETTERS[i]}{j + 1}"
                
                is_primary = (cell_id == primary_zone and primary_val > 0)
                
                if is_primary and str(risk_level).upper() == "HIGH":
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 240), 3)
                    badge_str = f"RISK ZONE: {cell_id}"
                    (tw, th), _ = cv2.getTextSize(badge_str, cv2.FONT_HERSHEY_SIMPLEX, 0.42, 1)
                    cv2.rectangle(frame, (x1 + 4, y1 + 4), (x1 + tw + 10, y1 + th + 10), (0, 0, 240), -1)
                    cv2.putText(frame, badge_str, (x1 + 7, y1 + th + 5),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 255, 255), 1, cv2.LINE_AA)
                elif is_primary and str(risk_level).upper() == "MEDIUM":
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 140, 240), 2)
                    badge_str = f"ZONE: {cell_id}"
                    (tw, th), _ = cv2.getTextSize(badge_str, cv2.FONT_HERSHEY_SIMPLEX, 0.42, 1)
                    cv2.rectangle(frame, (x1 + 4, y1 + 4), (x1 + tw + 10, y1 + th + 10), (0, 140, 220), -1)
                    cv2.putText(frame, badge_str, (x1 + 7, y1 + th + 5),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 255, 255), 1, cv2.LINE_AA)
                else:
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (100, 100, 100), 1)
                
                count = density_map[i, j] if hasattr(density_map, '__getitem__') else 0
                if count > 0:
                    text = str(count)
                    text_pos = (x1 + cell_w // 2 - 8, y1 + cell_h // 2 + 6)
                    cv2.putText(frame, text, text_pos,
                               cv2.FONT_HERSHEY_SIMPLEX, 0.45, (220, 220, 220), 1, cv2.LINE_AA)
        
        return frame
    
    @staticmethod
    def draw_motion_vectors(frame, tracks, previous_centroids):
        """Draw motion arrows showing movement direction"""
        for track in tracks:
            x1, y1, x2, y2, track_id = track[:5]
            centroid = np.array([(x1+x2)/2, (y1+y2)/2], dtype=np.int32)
            
            if track_id in previous_centroids:
                prev = previous_centroids[track_id].astype(np.int32)
                cv2.arrowedLine(frame, tuple(prev), tuple(centroid),
                              (0, 255, 255), 1, line_type=cv2.LINE_AA, tipLength=0.3)
        return frame
    
    @staticmethod
    def draw_optical_flow_grid(frame, grid_matrix, grid_size=(4, 4)):
        """Draw motion direction arrows and sudden movement highlights on grid cells"""
        h, w = frame.shape[:2]
        cell_h, cell_w = max(1, h // grid_size[0]), max(1, w // grid_size[1])
        
        for r in range(min(len(grid_matrix), grid_size[0])):
            for c in range(min(len(grid_matrix[r]), grid_size[1])):
                cell = grid_matrix[r][c]
                cx = c * cell_w + cell_w // 2
                cy = r * cell_h + cell_h // 2
                
                if cell.sudden_movement:
                    x1, y1 = c * cell_w, r * cell_h
                    x2, y2 = (c + 1) * cell_w, (r + 1) * cell_h
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 240), 2)
                    cv2.putText(frame, "SPIKE", (x1 + 5, y1 + 18),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 240), 1, cv2.LINE_AA)
                
                if cell.magnitude > 0.5:
                    arrow_len = min(max(8, int(cell.magnitude * 4)), min(cell_w, cell_h) // 3)
                    end_x = int(cx + (cell.vx / max(cell.magnitude, 1e-5)) * arrow_len)
                    end_y = int(cy + (cell.vy / max(cell.magnitude, 1e-5)) * arrow_len)
                    
                    arrow_color = (0, 220, 255) if not cell.sudden_movement else (0, 0, 240)
                    cv2.arrowedLine(frame, (cx, cy), (end_x, end_y), arrow_color, 1, line_type=cv2.LINE_AA, tipLength=0.3)
        return frame

    @staticmethod
    def draw_tracks(frame, tracks):
        """Draw thin green bounding boxes and compact 'P23' track labels"""
        for track in tracks:
            x1, y1, x2, y2, track_id = track[:5]
            x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
            
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 230, 80), 1)
            
            label = f"P{track_id}"
            (lw, lh), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.38, 1)
            cv2.rectangle(frame, (x1, max(0, y1 - 15)), (x1 + lw + 4, max(15, y1)), (0, 180, 60), -1)
            cv2.putText(frame, label, (x1 + 2, max(12, y1 - 3)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.38, (0, 0, 0), 1, cv2.LINE_AA)
        return frame

    @staticmethod
    def draw_telemetry_hud(frame, metrics, camera_id="CAM-01"):
        """Draw high-readability semi-transparent telemetry HUD at top of frame."""
        from src.alert_manager import extract_spatial_risk_info
        h, w = frame.shape[:2]
        
        person_cnt = metrics.get("person_count", 0)
        risk_str = str(metrics.get("risk", "LOW")).upper()
        risk_score = metrics.get("combined_score", 0.0)
        fps_val = metrics.get("fps", 0.0)
        cam_id = metrics.get("camera_id", camera_id)
        
        spatial_info = extract_spatial_risk_info(metrics.get("density_map")) if "density_map" in metrics else {"primary_risk_zone": metrics.get("risk_zone", "--")}
        risk_zone = spatial_info.get("primary_risk_zone", "--")

        if risk_str == "HIGH":
            badge_bg = (0, 0, 220)
            risk_text = f"● HIGH ({risk_score:.1f})"
        elif risk_str == "MEDIUM":
            badge_bg = (0, 140, 240)
            risk_text = f"● MEDIUM ({risk_score:.1f})"
        else:
            badge_bg = (30, 160, 50)
            risk_text = f"● LOW ({risk_score:.1f})"

        overlay = frame.copy()
        
        if w >= 500:
            hud_h = 65
            cv2.rectangle(overlay, (0, 0), (w, hud_h), (12, 16, 24), -1)
            frame = cv2.addWeighted(overlay, 0.85, frame, 0.15, 0)
            
            cv2.putText(frame, "CROWDPATROL", (15, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2, cv2.LINE_AA)
            cv2.putText(frame, "● MONITORING", (160, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 230, 80), 1, cv2.LINE_AA)
            cv2.putText(frame, f"CAM: {cam_id}", (w - 180, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1, cv2.LINE_AA)

            cv2.putText(frame, f"PERSONS: {person_cnt}", (15, 52), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (255, 255, 255), 2, cv2.LINE_AA)
            
            (rw, rh), _ = cv2.getTextSize(risk_text, cv2.FONT_HERSHEY_SIMPLEX, 0.48, 2)
            rx = 180
            cv2.rectangle(frame, (rx - 4, 36), (rx + rw + 8, 56), badge_bg, -1)
            cv2.putText(frame, risk_text, (rx, 51), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (255, 255, 255), 2, cv2.LINE_AA)

            cv2.putText(frame, f"ZONE: {risk_zone}", (rx + rw + 25, 52), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 220, 255), 2, cv2.LINE_AA)
            cv2.putText(frame, f"FPS: {fps_val:.1f}", (w - 180, 52), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 180), 2, cv2.LINE_AA)
        else:
            hud_h = 40
            cv2.rectangle(overlay, (0, 0), (w, hud_h), (12, 16, 24), -1)
            frame = cv2.addWeighted(overlay, 0.85, frame, 0.15, 0)

            title_str = f"{cam_id} | 👥 {person_cnt} | "
            cv2.putText(frame, title_str, (8, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 255, 255), 1, cv2.LINE_AA)
            
            (tw, _), _ = cv2.getTextSize(title_str, cv2.FONT_HERSHEY_SIMPLEX, 0.42, 1)
            (rw, rh), _ = cv2.getTextSize(risk_str, cv2.FONT_HERSHEY_SIMPLEX, 0.42, 2)
            cv2.rectangle(frame, (8 + tw, 10), (8 + tw + rw + 6, 30), badge_bg, -1)
            cv2.putText(frame, risk_str, (8 + tw + 3, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 255, 255), 2, cv2.LINE_AA)
            
            cv2.putText(frame, f"Z:{risk_zone} | {fps_val:.1f} FPS", (8 + tw + rw + 15, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (0, 220, 255), 1, cv2.LINE_AA)

        return frame

    @staticmethod
    def create_dashboard_frame(frame, metrics, density_map, grid_size=(4, 4), grid_matrix=None, tracks=None):
        """Create complete high-readability dashboard view with clean overlays and HUD"""
        from src.alert_manager import extract_spatial_risk_info
        frame = frame.copy()
        h, w = frame.shape[:2]
        
        spatial_info = extract_spatial_risk_info(density_map)
        metrics["density_map"] = density_map
        metrics["risk_zone"] = spatial_info["primary_risk_zone"]
        
        if tracks is not None and len(tracks) > 0:
            frame = FrameAnnotator.draw_tracks(frame, tracks)
        
        frame = FrameAnnotator.draw_density_zones(frame, density_map, grid_size, risk_level=metrics.get("risk", "Low"))
        
        if grid_matrix is not None:
            frame = FrameAnnotator.draw_optical_flow_grid(frame, grid_matrix, grid_size)
            
        frame = FrameAnnotator.draw_telemetry_hud(frame, metrics, camera_id=metrics.get("camera_id", "CAM-01"))

        if w >= 640:
            panel_w = 210
            panel_x = w - panel_w
            overlay = frame.copy()
            cv2.rectangle(overlay, (panel_x, 65), (w, h - 10), (15, 22, 32), -1)
            frame = cv2.addWeighted(overlay, 0.85, frame, 0.15, 0)
            cv2.rectangle(frame, (panel_x, 65), (w, h - 10), (50, 65, 85), 1)
            
            y = 92
            risk_lvl = str(metrics.get("risk", "LOW")).upper()
            info_items = [
                ("CAMERA", metrics.get("camera_id", "CAM-01")),
                ("PERSONS", str(metrics.get("person_count", 0))),
                ("DENSITY", f"{metrics.get('density', 0)} / cell"),
                ("RISK LEVEL", risk_lvl),
                ("RISK SCORE", f"{metrics.get('combined_score', 0.0):.1f}"),
                ("AVG SPEED", f"{metrics.get('avg_speed', 0.0):.1f} px/f"),
                ("MAX SPEED", f"{metrics.get('max_speed', 0.0):.1f} px/f"),
                ("HEADING", str(metrics.get("dominant_direction", "STATIC"))),
                ("FPS", f"{metrics.get('fps', 0.0):.1f}"),
                ("RISK ZONE", f"{spatial_info['primary_risk_zone']} ({spatial_info['primary_zone_density']})"),
            ]
            
            for label, value in info_items:
                cv2.putText(frame, f"{label}:", (panel_x + 12, y),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.42, (170, 180, 195), 1, cv2.LINE_AA)
                
                val_color = (255, 255, 255)
                if label == "RISK LEVEL":
                    val_color = (0, 0, 240) if risk_lvl == "HIGH" else ((0, 140, 240) if risk_lvl == "MEDIUM" else (40, 200, 60))
                elif label == "RISK ZONE":
                    val_color = (0, 220, 255)
                    
                cv2.putText(frame, str(value), (panel_x + 105, y),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.45, val_color, 2 if label in ["PERSONS", "RISK LEVEL", "RISK SCORE"] else 1, cv2.LINE_AA)
                y += 26

        return frame

    @staticmethod
    def draw_head_tracks(frame, tracks):
        """Draw thin cyan bounding boxes and compact 'H23' head track labels"""
        for track in tracks:
            if len(track) >= 5:
                x1, y1, x2, y2, track_id = track[:5]
            else:
                continue
            x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
            
            cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 230, 0), 1)
            
            label = f"H{track_id}"
            (lw, lh), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.38, 1)
            cv2.rectangle(frame, (x1, max(0, y1 - 15)), (x1 + lw + 4, max(15, y1)), (255, 200, 0), -1)
            cv2.putText(frame, label, (x1 + 2, max(12, y1 - 3)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.38, (0, 0, 0), 1)
        return frame

    @staticmethod
    def draw_head_density_zones(frame, density_map, grid_size=(4, 4), risk_level="LOW"):
        """Draw yellow grid lines, head density numbers on zones, and highlight primary risk zone."""
        from src.alert_manager import extract_spatial_risk_info
        h, w = frame.shape[:2]
        cell_h, cell_w = max(1, h // grid_size[0]), max(1, w // grid_size[1])
        ROW_LETTERS = ['A', 'B', 'C', 'D']
        
        spatial_info = extract_spatial_risk_info(density_map)
        primary_zone = spatial_info["primary_risk_zone"]
        primary_val = spatial_info["primary_zone_density"]
        
        for i in range(min(grid_size[0], len(ROW_LETTERS))):
            for j in range(grid_size[1]):
                x1, y1 = j * cell_w, i * cell_h
                x2, y2 = (j + 1) * cell_w, (i + 1) * cell_h
                cell_id = f"{ROW_LETTERS[i]}{j + 1}"
                
                is_primary = (cell_id == primary_zone and primary_val > 0)
                
                if is_primary and str(risk_level).upper() == "HIGH":
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 240), 3)
                    badge_str = f"RISK ZONE: {cell_id}"
                    (tw, th), _ = cv2.getTextSize(badge_str, cv2.FONT_HERSHEY_SIMPLEX, 0.42, 1)
                    cv2.rectangle(frame, (x1 + 4, y1 + 4), (x1 + tw + 10, y1 + th + 10), (0, 0, 240), -1)
                    cv2.putText(frame, badge_str, (x1 + 7, y1 + th + 5),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 255, 255), 1)
                elif is_primary and str(risk_level).upper() == "MEDIUM":
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 140, 240), 2)
                    badge_str = f"ZONE: {cell_id}"
                    (tw, th), _ = cv2.getTextSize(badge_str, cv2.FONT_HERSHEY_SIMPLEX, 0.42, 1)
                    cv2.rectangle(frame, (x1 + 4, y1 + 4), (x1 + tw + 10, y1 + th + 10), (0, 140, 220), -1)
                    cv2.putText(frame, badge_str, (x1 + 7, y1 + th + 5),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 255, 255), 1)
                else:
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 220, 220), 1)
                
                count = density_map[i, j] if hasattr(density_map, '__getitem__') else 0
                if count > 0:
                    text = f"H:{count}"
                    text_pos = (x1 + 10, y1 + 25)
                    cv2.putText(frame, text, text_pos,
                               cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 220, 220), 1)
        return frame

    @staticmethod
    def create_head_dashboard_frame(frame, metrics, density_map, grid_size=(4, 4), grid_matrix=None, tracks=None):
        """Create head mode dashboard view with cyan boxes and experimental HUD"""
        from src.alert_manager import extract_spatial_risk_info
        frame = frame.copy()
        h, w = frame.shape[:2]
        
        spatial_info = extract_spatial_risk_info(density_map)
        metrics["density_map"] = density_map
        metrics["risk_zone"] = spatial_info["primary_risk_zone"]
        
        if tracks is not None and len(tracks) > 0:
            frame = FrameAnnotator.draw_head_tracks(frame, tracks)
            
        frame = FrameAnnotator.draw_head_density_zones(frame, density_map, grid_size, risk_level=metrics.get("risk", "Low"))
        
        if grid_matrix is not None:
            frame = FrameAnnotator.draw_optical_flow_grid(frame, grid_matrix, grid_size)
            
        frame = FrameAnnotator.draw_telemetry_hud(frame, metrics, camera_id=metrics.get("camera_id", "HEAD-01"))

        if w >= 640:
            panel_w = 210
            panel_x = w - panel_w
            overlay = frame.copy()
            cv2.rectangle(overlay, (panel_x, 65), (w, h - 10), (15, 22, 32), -1)
            frame = cv2.addWeighted(overlay, 0.85, frame, 0.15, 0)
            cv2.rectangle(frame, (panel_x, 65), (w, h - 10), (50, 65, 85), 1)
            
            y = 92
            risk_lvl = str(metrics.get("risk", "LOW")).upper()
            info_items = [
                ("MODE", "HEAD EXP"),
                ("VISIBLE HEADS", str(metrics.get("visible_heads", 0))),
                ("ACTIVE TRACKS", str(metrics.get("person_count", 0))),
                ("MAX HEAD DENS", str(metrics.get("density", 0))),
                ("RISK LEVEL", risk_lvl),
                ("HEAD RISK", f"{metrics.get('combined_score', 0.0):.1f}"),
                ("AVG SPEED", f"{metrics.get('avg_speed', 0.0):.1f} px/f"),
                ("HEADING", str(metrics.get("dominant_direction", "STATIC"))),
                ("FPS", f"{metrics.get('fps', 0.0):.1f}"),
                ("RISK ZONE", f"{spatial_info['primary_risk_zone']} ({spatial_info['primary_zone_density']})"),
            ]
            
            for label, value in info_items:
                cv2.putText(frame, f"{label}:", (panel_x + 10, y),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.40, (170, 180, 195), 1)
                val_color = (0, 255, 255)
                cv2.putText(frame, str(value), (panel_x + 115, y),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.42, val_color, 1)
                y += 26
            
        return frame


class ConfigLoader:
    """Load and validate configuration"""
    
    @staticmethod
    def load_from_file(config_path):
        """Load config from JSON file"""
        with open(config_path, 'r') as f:
            return json.load(f)
    
    @staticmethod
    def create_default_config():
        """Generate default configuration"""
        default_config = {
            "detection": {
                "model": "yolov8n.pt",
                "confidence": 0.5,
                "device": "cpu"
            },
            "tracking": {
                "max_age": 30
            },
            "density": {
                "grid_size": [4, 4],
                "thresholds": {
                    "low": 5,
                    "medium": 15,
                    "high": 30
                }
            },
            "risk": {
                "anomaly_threshold": 10,
                "density_weight": 0.7,
                "anomaly_weight": 0.3
            },
            "alerts": {
                "enabled": False,
                "cooldown_seconds": 60,
                "email": {"enabled": False},
                "sms": {"enabled": False}
            },
            "output": {
                "save_video": False,
                "log_metrics": True,
                "show_dashboard": True
            }
        }
        return default_config


def preprocess_frame(frame, target_size=(1280, 720)):
    """Resize and normalize frame"""
    frame = cv2.resize(frame, target_size)
    return frame


def calculate_optical_flow(prev_frame, current_frame):
    """Calculate sparse optical flow for movement analysis"""
    # Convert to grayscale
    prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
    curr_gray = cv2.cvtColor(current_frame, cv2.COLOR_BGR2GRAY)
    
    # Detect good features
    feature_params = dict(maxCorners=100, qualityLevel=0.3, minDistance=7, blockSize=7)
    p0 = cv2.goodFeaturesToTrack(prev_gray, mask=None, **feature_params)
    
    if p0 is None:
        return None, None
    
    # Calculate optical flow
    lk_params = dict(winSize=(15, 15), maxLevel=2,
                    criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 10, 0.03))
    p1, status, _ = cv2.calcOpticalFlowPyrLK(prev_gray, curr_gray, p0, None, **lk_params)
    
    if p1 is None:
        return None, None
    
    return p0[status == 1], p1[status == 1]


def format_timestamp():
    """Get formatted timestamp"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def create_directory_structure():
    """Create project directory structure"""
    dirs = [
        "logs",
        "output",
        "config",
        "models",
        "data/videos",
        "data/images"
    ]
    for d in dirs:
        os.makedirs(d, exist_ok=True)
    print("[✓] Directory structure created")