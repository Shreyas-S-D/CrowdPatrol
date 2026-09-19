import cv2
from pathlib import Path

SRC = Path("data/videos/youtube_crowd_test.mp4")
OUT_DIR = Path("data/videos")

clips = [
    ("real_crowd_video_1.mp4", 0, 300),
    ("real_crowd_video_2.mp4", 1000, 1300),
    ("real_crowd_video_3.mp4", 2200, 2500),
]

cap = cv2.VideoCapture(str(SRC))
w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
fps = cap.get(cv2.CAP_PROP_FPS)

for name, start, end in clips:
    out_path = OUT_DIR / name
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(str(out_path), fourcc, fps, (w, h))
    
    cap.set(cv2.CAP_PROP_POS_FRAMES, start)
    curr = start
    while curr < end:
        ret, frame = cap.read()
        if not ret:
            break
        out.write(frame)
        curr += 1
    out.release()
    print(f"[OK] Extracted real crowd video clip: {out_path} ({end-start} frames, {w}x{h})")

cap.release()
