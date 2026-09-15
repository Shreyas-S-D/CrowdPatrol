"""
CrowdPatrol Phase 2 - Optical Flow Crowd Movement Analyzer
Computes spatial crowd motion vectors, speed magnitude, cardinal directions,
directional coherence, global camera motion subtraction, and sudden movement detection.
"""

import cv2
import numpy as np
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional


@dataclass
class GridMotionCell:
    row: int
    col: int
    vx: float
    vy: float
    magnitude: float
    direction_deg: float
    cardinal_dir: str
    coherence: float
    sudden_movement: bool


class CrowdMotionAnalyzer:
    """
    Downscaled Dense Farneback Optical Flow Analyzer with global camera motion subtraction.
    """
    
    CARDINAL_DIRECTIONS = [
        ("E", 0, 22.5),
        ("NE", 22.5, 67.5),
        ("N", 67.5, 112.5),
        ("NW", 112.5, 157.5),
        ("W", 157.5, 202.5),
        ("SW", 202.5, 247.5),
        ("S", 247.5, 292.5),
        ("SE", 292.5, 337.5),
        ("E", 337.5, 360.0)
    ]
    
    def __init__(
        self, 
        grid_size: Tuple[int, int] = (4, 4),
        downscale_size: Tuple[int, int] = (320, 180),
        accel_threshold: float = 3.0,
        min_motion_threshold: float = 0.5
    ):
        self.grid_size = grid_size
        self.downscale_size = downscale_size
        self.accel_threshold = accel_threshold
        self.min_motion_threshold = min_motion_threshold
        
        self.prev_gray: Optional[np.ndarray] = None
        self.prev_cell_magnitudes: Optional[np.ndarray] = None
        
        # Farneback parameters tuned for fast execution
        self.farneback_params = dict(
            pyr_scale=0.5,
            levels=3,
            winsize=15,
            iterations=3,
            poly_n=5,
            poly_sigma=1.2,
            flags=0
        )
        
    @staticmethod
    def _deg_to_cardinal(deg: float, magnitude: float, threshold: float = 0.5) -> str:
        if magnitude < threshold:
            return "STATIONARY"
        deg = deg % 360.0
        for name, low, high in CrowdMotionAnalyzer.CARDINAL_DIRECTIONS:
            if low <= deg < high:
                return name
        return "E"

    def analyze_frame(self, frame: np.ndarray) -> Tuple[List[List[GridMotionCell]], Dict]:
        """
        Analyze current video frame against previous frame using optical flow.
        
        Returns:
            grid_matrix: 2D list of GridMotionCell objects for each grid cell.
            summary: Dictionary containing global motion metrics.
        """
        h, w = frame.shape[:2]
        
        # Convert to downscaled grayscale
        gray = cv2.resize(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), self.downscale_size)
        
        if self.prev_gray is None or self.prev_gray.shape != gray.shape:
            self.prev_gray = gray
            self.prev_cell_magnitudes = np.zeros(self.grid_size, dtype=np.float32)
            
            # Default empty result for first frame
            grid_matrix = []
            for r in range(self.grid_size[0]):
                row_cells = []
                for c in range(self.grid_size[1]):
                    row_cells.append(GridMotionCell(
                        row=r, col=c, vx=0.0, vy=0.0, magnitude=0.0,
                        direction_deg=0.0, cardinal_dir="STATIONARY",
                        coherence=1.0, sudden_movement=False
                    ))
                grid_matrix.append(row_cells)
                
            summary = {
                "avg_speed": 0.0,
                "max_speed": 0.0,
                "dominant_direction": "STATIONARY",
                "sudden_movement_count": 0,
                "camera_motion_detected": False
            }
            return grid_matrix, summary

        # 1. Compute Dense Farneback Optical Flow on downscaled frame
        flow = cv2.calcOpticalFlowFarneback(
            self.prev_gray, gray, None, **self.farneback_params
        )
        self.prev_gray = gray
        
        flow_x = flow[..., 0]
        flow_y = flow[..., 1]
        
        # Scale flow vectors back to original image coordinate scale
        scale_x = w / self.downscale_size[0]
        scale_y = h / self.downscale_size[1]
        flow_x = flow_x * scale_x
        flow_y = flow_y * scale_y
        
        # 2. Global Camera Motion Subtraction via Spatial Median
        bg_vx = float(np.median(flow_x))
        bg_vy = float(np.median(flow_y))
        camera_motion_detected = (np.sqrt(bg_vx**2 + bg_vy**2) > 1.5)
        
        # Subtract background camera motion to isolate crowd motion
        flow_x_corrected = flow_x - bg_vx
        flow_y_corrected = flow_y - bg_vy
        
        # 3. Aggregate Motion across Grid Cells
        dh, dw = flow_x.shape[:2]
        cell_h = max(1, dh // self.grid_size[0])
        cell_w = max(1, dw // self.grid_size[1])
        
        grid_matrix = []
        cell_magnitudes = np.zeros(self.grid_size, dtype=np.float32)
        all_cardinals = []
        sudden_count = 0
        
        for r in range(self.grid_size[0]):
            row_cells = []
            for c in range(self.grid_size[1]):
                y1, y2 = r * cell_h, min((r + 1) * cell_h, dh)
                x1, x2 = c * cell_w, min((c + 1) * cell_w, dw)
                
                cell_fx = flow_x_corrected[y1:y2, x1:x2]
                cell_fy = flow_y_corrected[y1:y2, x1:x2]
                
                if cell_fx.size == 0:
                    avg_vx, avg_vy = 0.0, 0.0
                    coherence = 1.0
                else:
                    avg_vx = float(np.mean(cell_fx))
                    avg_vy = float(np.mean(cell_fy))
                    
                    # Coherence = |sum(vector)| / sum(|vector|)
                    mags = np.sqrt(cell_fx**2 + cell_fy**2)
                    sum_mag = np.sum(mags)
                    if sum_mag > 1e-5:
                        coherence = float(np.sqrt(np.sum(cell_fx)**2 + np.sum(cell_fy)**2) / sum_mag)
                    else:
                        coherence = 1.0
                
                mag = float(np.sqrt(avg_vx**2 + avg_vy**2))
                cell_magnitudes[r, c] = mag
                
                # Math angle conversion: atan2(vy, vx) convert to degrees
                # In OpenCV pixel coords, y points DOWN, x points RIGHT
                deg = float(np.degrees(np.arctan2(avg_vy, avg_vx))) % 360.0
                cardinal = self._deg_to_cardinal(deg, mag, self.min_motion_threshold)
                if cardinal != "STATIONARY":
                    all_cardinals.append(cardinal)
                
                # Detect acceleration spike
                prev_mag = self.prev_cell_magnitudes[r, c]
                sudden_movement = bool((mag - prev_mag) > self.accel_threshold and mag > self.min_motion_threshold)
                if sudden_movement:
                    sudden_count += 1
                
                cell_obj = GridMotionCell(
                    row=r, col=c, vx=avg_vx, vy=avg_vy,
                    magnitude=mag, direction_deg=deg,
                    cardinal_dir=cardinal, coherence=coherence,
                    sudden_movement=sudden_movement
                )
                row_cells.append(cell_obj)
            grid_matrix.append(row_cells)
            
        self.prev_cell_magnitudes = cell_magnitudes
        
        # Calculate summary metrics
        avg_speed = float(np.mean(cell_magnitudes))
        max_speed = float(np.max(cell_magnitudes))
        
        if all_cardinals:
            # Dominant cardinal direction by mode frequency
            vals, counts = np.unique(all_cardinals, return_counts=True)
            dominant_direction = str(vals[np.argmax(counts)])
        else:
            dominant_direction = "STATIONARY"
            
        summary = {
            "avg_speed": round(avg_speed, 2),
            "max_speed": round(max_speed, 2),
            "dominant_direction": dominant_direction,
            "sudden_movement_count": sudden_count,
            "camera_motion_detected": camera_motion_detected
        }
        
        return grid_matrix, summary
