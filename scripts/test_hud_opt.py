import time
import cv2
import numpy as np

frame = np.random.randint(0, 255, (1080, 1920, 3), dtype=np.uint8)
w, h = 1920, 1080
hud_h = 65

# 1. Full frame copy and addWeighted
t0 = time.perf_counter()
for _ in range(20):
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, hud_h), (12, 16, 24), -1)
    f_res = cv2.addWeighted(overlay, 0.85, frame, 0.15, 0)
t_full = (time.perf_counter() - t0) / 20 * 1000

# 2. ROI-only blend
t0 = time.perf_counter()
for _ in range(20):
    f_res = frame.copy()
    roi = f_res[:hud_h, :]
    overlay_roi = roi.copy()
    cv2.rectangle(overlay_roi, (0, 0), (w, hud_h), (12, 16, 24), -1)
    f_res[:hud_h, :] = cv2.addWeighted(overlay_roi, 0.85, roi, 0.15, 0)
t_roi = (time.perf_counter() - t0) / 20 * 1000

print(f"Full-frame blend: {t_full:6.2f} ms")
print(f"ROI-only blend:   {t_roi:6.2f} ms")
print(f"Speedup: {t_full / t_roi:.1f}x")
