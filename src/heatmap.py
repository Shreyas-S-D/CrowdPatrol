"""
Simple grid-based heatmap overlay for CrowdPatrol.
Red = High density, Green = Low density.
"""

import cv2
import numpy as np


def generate_heatmap(frame, tracks, grid_cols=8, grid_rows=6, draw_grid=True):
    """
    Generate a simple heatmap overlay.
    
    Args:
        frame: Video frame
        tracks: Array of [x1,y1,x2,y2,track_id]
        grid_cols, grid_rows: Grid dimensions
        draw_grid: Whether to draw grid lines and cell numbers (default: True)
    
    Returns:
        overlay: Frame with heatmap blended
        density_grid: Raw density counts per cell
    """
    h, w = frame.shape[:2]
    cell_w = max(1, w // grid_cols)
    cell_h = max(1, h // grid_rows)
    
    # Count persons in each cell
    density_grid = np.zeros((grid_rows, grid_cols), dtype=np.float32)
    
    for track in tracks:
        x1, y1, x2, y2 = map(float, track[:4])
        center_x = (x1 + x2) / 2
        center_y = (y1 + y2) / 2
        
        col = max(0, min(int(center_x // cell_w), grid_cols - 1))
        row = max(0, min(int(center_y // cell_h), grid_rows - 1))
        
        density_grid[row, col] += 1
    
    # Normalize to 0-255
    max_val = np.max(density_grid)
    overlay = frame.copy()
    
    if max_val > 0:
        density_grid_norm = (density_grid / max_val * 255).astype(np.uint8)
        heatmap = cv2.resize(density_grid_norm, (w, h), interpolation=cv2.INTER_LINEAR).astype(np.uint8)
        heatmap_color = cv2.applyColorMap(heatmap, cv2.COLORMAP_JET)
        
        # Mask heatmap blending to density > 0 regions
        mask = cv2.resize((density_grid > 0).astype(np.uint8), (w, h), interpolation=cv2.INTER_NEAREST)
        mask_3d = cv2.merge([mask, mask, mask])
        blended = cv2.addWeighted(frame, 0.82, heatmap_color, 0.18, 0)
        np.copyto(overlay, blended, where=(mask_3d > 0))
    
    if draw_grid:
        # Draw grid lines
        for i in range(0, w, cell_w):
            cv2.line(overlay, (i, 0), (i, h), (255, 255, 255), 1)
        for j in range(0, h, cell_h):
            cv2.line(overlay, (0, j), (w, j), (255, 255, 255), 1)
        
        # Draw count in each cell
        for row in range(grid_rows):
            for col in range(grid_cols):
                count = int(density_grid[row, col])
                cx = col * cell_w + cell_w // 2 - 10
                cy = row * cell_h + cell_h // 2 + 10
                
                if count > 5:
                    color = (0, 0, 255)   # Red
                elif count > 2:
                    color = (0, 255, 255) # Yellow
                else:
                    color = (0, 255, 0)   # Green
                
                cv2.putText(overlay, str(count), (cx, cy),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
    
    return overlay, density_grid