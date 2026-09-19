import cv2
import numpy as np
from ultralytics import YOLO

def debug_yolo_on_video():
    video_path = "data/videos/youtube_crowd_test.mp4"
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"[!] Unable to open video: {video_path}")
        return

    print("==================================================")
    print("   YOLOV8 DIRECT DETECTION DIAGNOSTIC TEST")
    print("==================================================")
    print(f"[*] Video Path: {video_path}")
    print(f"[*] Frame Count: {int(cap.get(cv2.CAP_PROP_FRAME_COUNT))}")
    print(f"[*] Resolution:  {int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))}x{int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))}")

    model = YOLO("yolov8n.pt")
    
    # Test on multiple frames (e.g. frame 1, 30, 60, 100, 200, 500)
    test_frame_indices = [1, 30, 60, 100, 200, 500]
    
    for target_idx in test_frame_indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, target_idx)
        ret, frame = cap.read()
        if not ret or frame is None:
            print(f"[!] Could not read frame {target_idx}")
            continue
            
        print(f"\n--- Frame #{target_idx} (Shape: {frame.shape}, Dtype: {frame.dtype}) ---")
        
        # Run raw YOLO model with confidence = 0.1 to see ALL raw detections
        results = model(frame, verbose=False)[0]
        num_raw = len(results.boxes)
        print(f"Total Raw YOLO Bounding Boxes Detected: {num_raw}")
        
        classes_found = {}
        person_count_conf05 = 0
        person_count_conf025 = 0
        
        for box in results.boxes:
            cls_id = int(box.cls)
            conf = float(box.conf)
            classes_found[cls_id] = classes_found.get(cls_id, 0) + 1
            
            if cls_id == 0:  # person
                if conf >= 0.50:
                    person_count_conf05 += 1
                if conf >= 0.25:
                    person_count_conf025 += 1
                    
        print(f"Class Breakdown: {classes_found}")
        print(f"Person Detections (conf >= 0.50):  {person_count_conf05}")
        print(f"Person Detections (conf >= 0.25):  {person_count_conf025}")
        
        # For frame 60, save diagnostic image with bounding boxes
        if target_idx == 60 and num_raw > 0:
            diag_frame = frame.copy()
            for box in results.boxes:
                cls_id = int(box.cls)
                conf = float(box.conf)
                if cls_id == 0 and conf >= 0.25:
                    x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                    cv2.rectangle(diag_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    cv2.putText(diag_frame, f"person {conf:.2f}", (x1, max(y1 - 5, 15)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            cv2.imwrite("scratch/yolo_debug_output.jpg", diag_frame)
            print(f"[OK] Saved raw YOLO diagnostic image to: scratch/yolo_debug_output.jpg")
            
    cap.release()

if __name__ == "__main__":
    debug_yolo_on_video()
