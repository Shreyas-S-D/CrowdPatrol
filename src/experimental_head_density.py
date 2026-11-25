"""
CrowdPatrol Phase 4 — Experimental Head-Center Density Estimator Module.
Calculates 4x4 spatial grid density using HEAD CENTER POINTS rather than full body boxes.

IMPORTANT: This is an experimental module for head-based crowd sensing research only.
Does NOT modify or replace production DensityEstimator.
"""

import numpy as np
import cv2

class HeadDensityEstimator:
    """
    Experimental Head-Center Density Estimator.
    Maps head center coordinates (center_x, center_y) to 4x4 spatial grid cells.
    """
    def __init__(self, grid_size=(4, 4)):
        self.grid_size = grid_size
        
    def calculate_density(self, tracks, frame_shape):
        """
        Input tracks: list of [x1, y1, x2, y2, track_id] or ([x1, y1, w, h], conf, cls)
        Returns:
            density_map: 4x4 numpy array of head counts
            max_density: integer peak head count in any single grid cell
            summary_stats: dictionary of head spatial distribution metrics
        """
        height, width = frame_shape[:2]
        cell_h = max(1, height // self.grid_size[0])
        cell_w = max(1, width // self.grid_size[1])
        
        density_map = np.zeros(self.grid_size, dtype=int)
        total_heads = 0
        
        for item in tracks:
            # Handle both DeepSORT tracks [x1, y1, x2, y2, id] and raw dets ([x1, y1, w, h], conf, cls)
            if isinstance(item, (list, tuple)) and len(item) >= 4 and isinstance(item[0], (int, float)):
                x1, y1, x2, y2 = map(float, item[:4])
            elif isinstance(item, tuple) and len(item) == 3 and isinstance(item[0], (list, tuple)):
                (bx1, by1, bw, bh), conf, _ = item
                x1, y1, x2, y2 = float(bx1), float(by1), float(bx1 + bw), float(by1 + bh)
            else:
                continue
                
            center_x = (x1 + x2) / 2.0
            center_y = (y1 + y2) / 2.0
            
            grid_y = max(0, min(int(center_y // cell_h), self.grid_size[0] - 1))
            grid_x = max(0, min(int(center_x // cell_w), self.grid_size[1] - 1))
            
            density_map[grid_y, grid_x] += 1
            total_heads += 1
            
        max_density = int(np.max(density_map)) if total_heads > 0 else 0
        occupied_cells = int(np.sum(density_map > 0))
        
        summary_stats = {
            "total_heads": total_heads,
            "max_cell_heads": max_density,
            "occupied_cells": occupied_cells,
            "cell_occupancy_ratio": float(occupied_cells / (self.grid_size[0] * self.grid_size[1])),
            "avg_heads_per_occupied_cell": float(total_heads / occupied_cells) if occupied_cells > 0 else 0.0
        }
        
        return density_map, max_density, summary_stats

    def generate_heatmap(self, density_map, frame_shape):
        """Generates color-coded 4x4 spatial density heatmap overlay."""
        height, width = frame_shape[:2]
        heatmap = cv2.resize(
            density_map.astype(np.float32), 
            (width, height), 
            interpolation=cv2.INTER_NEAREST
        )
        max_val = max(int(np.max(density_map)), 1)
        heatmap_norm = (heatmap / max_val * 255.0).astype(np.uint8)
        color_map = cv2.applyColorMap(heatmap_norm, cv2.COLORMAP_JET)
        return color_map
