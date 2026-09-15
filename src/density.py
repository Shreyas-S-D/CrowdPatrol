import numpy as np
import cv2

class DensityEstimator:
    def __init__(self, grid_size=(4, 4)):
        self.grid_size = grid_size
    
    def calculate_density(self, tracks, frame_shape):
        height, width = frame_shape[:2]
        cell_h = max(1, height // self.grid_size[0])
        cell_w = max(1, width // self.grid_size[1])
        
        density_map = np.zeros(self.grid_size, dtype=int)
        
        for track in tracks:
            # Expected format: [x1, y1, x2, y2, id]
            x1, y1, x2, y2 = map(float, track[:4])

            center_x = (x1 + x2) / 2
            center_y = (y1 + y2) / 2
            
            grid_y = max(0, min(int(center_y // cell_h), self.grid_size[0] - 1))
            grid_x = max(0, min(int(center_x // cell_w), self.grid_size[1] - 1))
            density_map[grid_y, grid_x] += 1
        
        return density_map, np.max(density_map)
    
    def generate_heatmap(self, density_map, frame_shape):
        height, width = frame_shape[:2]
        heatmap = cv2.resize(
            density_map.astype(np.float32), 
            (width, height), 
            interpolation=cv2.INTER_NEAREST
        )
        heatmap = (heatmap / max(np.max(heatmap), 1) * 255).astype(np.uint8)
        heatmap = cv2.applyColorMap(heatmap, cv2.COLORMAP_JET)
        return heatmap