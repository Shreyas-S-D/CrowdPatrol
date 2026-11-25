import time
import cv2
import numpy as np

frame = np.random.randint(0, 255, (720, 1280, 3), dtype=np.uint8)
density_grid = np.zeros((6, 8), dtype=np.float32)
density_grid[2, 3] = 5
density_grid[3, 4] = 8

# Original implementation
def orig_heatmap(frame, density_grid, w=1280, h=720):
    max_val = np.max(density_grid)
    overlay = frame.copy()
    if max_val > 0:
        density_grid_norm = (density_grid / max_val * 255).astype(np.uint8)
        heatmap = cv2.resize(density_grid_norm, (w, h), interpolation=cv2.INTER_LINEAR).astype(np.uint8)
        heatmap_color = cv2.applyColorMap(heatmap, cv2.COLORMAP_JET)
        mask = cv2.resize((density_grid > 0).astype(np.uint8), (w, h), interpolation=cv2.INTER_NEAREST)
        mask_3d = cv2.merge([mask, mask, mask])
        blended = cv2.addWeighted(frame, 0.82, heatmap_color, 0.18, 0)
        np.copyto(overlay, blended, where=(mask_3d > 0))
    return overlay

# Optimized implementation
def opt_heatmap(frame, density_grid, w=1280, h=720):
    max_val = np.max(density_grid)
    if max_val == 0:
        return frame.copy()
    
    density_norm = (density_grid / max_val * 255).astype(np.uint8)
    # Apply colormap on small grid first (8x6)
    color_small = cv2.applyColorMap(density_norm, cv2.COLORMAP_JET)
    # Resize colorized heatmap to target size
    heatmap_color = cv2.resize(color_small, (w, h), interpolation=cv2.INTER_LINEAR)
    
    # Binary mask
    mask = cv2.resize((density_grid > 0).astype(np.uint8), (w, h), interpolation=cv2.INTER_NEAREST)
    
    overlay = frame.copy()
    # Blend only where mask is active
    nonzero_idx = np.where(mask > 0)
    if nonzero_idx[0].size > 0:
        f_sub = frame[nonzero_idx]
        h_sub = heatmap_color[nonzero_idx]
        overlay[nonzero_idx] = (f_sub * 0.82 + h_sub * 0.18).astype(np.uint8)
    return overlay

# Test timings
t0 = time.perf_counter()
for _ in range(20):
    o1 = orig_heatmap(frame, density_grid)
t_orig = (time.perf_counter() - t0) / 20 * 1000

t0 = time.perf_counter()
for _ in range(20):
    o2 = opt_heatmap(frame, density_grid)
t_opt = (time.perf_counter() - t0) / 20 * 1000

print(f"Original Heatmap:  {t_orig:6.2f} ms")
print(f"Optimized Heatmap: {t_opt:6.2f} ms")
print(f"Speedup: {t_orig / t_opt:.1f}x")
