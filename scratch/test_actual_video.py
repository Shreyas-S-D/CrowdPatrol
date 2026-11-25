import cv2
import numpy as np
from ultralytics import YOLO
import os

def test_yolo_on_actual_video():
    video_path = "data/videos/youtube_crowd_test.mp4"
    if not os.path.exists(video_path):
        print(f"[!] File not found: {video_path}")
        return

    cap = cv2.VideoCapture(video_path)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)

    print(f"[*] Video: {video_path}")
    print(f"[*] Resolution: {width}x{height}, Total Frames: {total_frames}, FPS: {fps:.2f}")

    model = YOLO("yolov8n.pt")

    # Sample frames across the video: 10, 50, 100, 300, 500, 1000, 1500, 2000
    sample_indices = [10, 50, 100, 300, 500, 1000, 1500, 2000]

    for idx in sample_indices:
        if idx >= total_frames:
            continue
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ret, frame = cap.read()
        if not ret or frame is None:
            print(f"[!] Frame {idx} could not be read.")
            continue

        # Save raw frame image to inspect visually if needed
        os.makedirs("scratch/frame_samples", exist_ok=True)
        sample_img_path = f"scratch/frame_samples/frame_{idx:04d}.jpg"
        cv2.imwrite(sample_img_path, frame)

        # Test YOLO at different confidence thresholds: 0.10, 0.20, 0.35, 0.50
        results_010 = model(frame, conf=0.10, verbose=False)[0]
        results_020 = model(frame, conf=0.20, verbose=False)[0]
        results_035 = model(frame, conf=0.35, verbose=False)[0]
        results_050 = model(frame, conf=0.50, verbose=False)[0]

        persons_010 = [b for b in results_010.boxes if int(b.cls) == 0]
        persons_020 = [b for b in results_020.boxes if int(b.cls) == 0]
        persons_035 = [b for b in results_035.boxes if int(b.cls) == 0]
        persons_050 = [b for b in results_050.boxes if int(b.cls) == 0]

        # Also get all detected classes at conf=0.10
        all_classes_010 = [model.names[int(b.cls)] for b in results_010.boxes]

        print(f"\n--- Frame #{idx} ---")
        print(f"  All objects detected (conf>=0.10): {all_classes_010[:10]}... (Total: {len(all_classes_010)})")
        print(f"  Person count at conf>=0.10: {len(persons_010)}")
        print(f"  Person count at conf>=0.20: {len(persons_020)}")
        print(f"  Person count at conf>=0.35: {len(persons_035)}")
        print(f"  Person count at conf>=0.50: {len(persons_050)}")

        if len(persons_010) > 0:
            top_confs = [round(float(b.conf), 2) for b in persons_010[:5]]
            print(f"  Top 5 person confidence scores: {top_confs}")

        # Draw detections at conf=0.20 on diagnostic frame
        diag_frame = frame.copy()
        for b in persons_020:
            x1, y1, x2, y2 = map(int, b.xyxy[0].tolist())
            conf_val = float(b.conf)
            cv2.rectangle(diag_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(diag_frame, f"person {conf_val:.2f}", (x1, max(15, y1 - 5)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        cv2.imwrite(f"scratch/frame_samples/frame_{idx:04d}_detected.jpg", diag_frame)

    cap.release()

if __name__ == "__main__":
    test_yolo_on_actual_video()
