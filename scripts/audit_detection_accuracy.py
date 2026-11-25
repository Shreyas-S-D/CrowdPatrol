"""
CrowdPatrol Phase 11.2 — Detection Agreement Audit: 1080p Reference vs. 720p Candidate
Compares Person Mode and Head Mode detections using cross-resolution agreement metrics:
- Spatial Overlap: Bounding-Box IoU of matched pairs
- Score Stability: Confidence differences between matched pairs
- Resolution Agreement: 1080p Retention Rate (Sensitivity), 720p Concordance Rate, Harmonic Concordance Index
- Discrepancies: 1080p Dropouts (missed in 720p), 720p Additional Detections (not in 1080p)

NOTE: This measures consistency and stability between two input resolutions of the same model;
it is NOT an absolute benchmark against human-annotated ground truth.
"""

import sys
import os
import cv2
import torch
import numpy as np
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
sys.path.append(str(BASE_DIR))

from src.detection import PersonDetector
from src.experimental_head_mode import ExperimentalHeadDetector, DEFAULT_HEAD_MODEL_PATH


def compute_iou(boxA, boxB):
    # box format: [x1, y1, x2, y2]
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[2], boxB[2])
    yB = min(boxA[3], boxB[3])

    interArea = max(0, xB - xA) * max(0, yB - yA)
    boxAArea = (boxA[2] - boxA[0]) * (boxA[3] - boxA[1])
    boxBArea = (boxB[2] - boxB[0]) * (boxB[3] - boxB[1])

    unionArea = boxAArea + boxBArea - interArea
    if unionArea <= 0:
        return 0.0
    return interArea / unionArea


def match_boxes(boxes1080, boxes720_scaled, iou_thresh=0.5):
    """
    Match 1080p boxes to 720p scaled boxes using greedy IoU.
    boxes1080: list of ([x1, y1, x2, y2], conf)
    boxes720_scaled: list of ([x1, y1, x2, y2], conf)
    """
    matched = []
    unmatched_1080 = list(range(len(boxes1080)))
    unmatched_720 = list(range(len(boxes720_scaled)))

    # Compute pairwise IoU
    iou_matrix = np.zeros((len(boxes1080), len(boxes720_scaled)))
    for i, (b1, _) in enumerate(boxes1080):
        for j, (b2, _) in enumerate(boxes720_scaled):
            iou_matrix[i, j] = compute_iou(b1, b2)

    while True:
        if iou_matrix.size == 0:
            break
        max_idx = np.unravel_index(np.argmax(iou_matrix), iou_matrix.shape)
        max_iou = iou_matrix[max_idx]
        if max_iou < iou_thresh:
            break
        i, j = max_idx
        matched.append((i, j, max_iou, abs(boxes1080[i][1] - boxes720_scaled[j][1])))
        if i in unmatched_1080:
            unmatched_1080.remove(i)
        if j in unmatched_720:
            unmatched_720.remove(j)
        iou_matrix[i, :] = -1.0
        iou_matrix[:, j] = -1.0

    return matched, unmatched_1080, unmatched_720


def evaluate_video(video_path, mode="PERSON", num_frames=10, step=15):
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Error opening {video_path}")
        return

    if mode == "PERSON":
        detector = PersonDetector(confidence=0.35, device="cpu", imgsz=640)
    else:
        head_path = "models/crowdpatrol_yolov8n_head_v4.pt" if os.path.exists("models/crowdpatrol_yolov8n_head_v4.pt") else DEFAULT_HEAD_MODEL_PATH
        detector = ExperimentalHeadDetector(model_path=head_path, confidence=0.25, device="cpu", imgsz=640)

    all_ious = []
    all_conf_diffs = []
    total_1080_count = 0
    total_720_count = 0
    total_matched = 0
    total_missed = 0
    total_extra = 0

    scale_x = 1920.0 / 1280.0
    scale_y = 1080.0 / 720.0

    frame_idx = 0
    evaluated_frames = 0
    while evaluated_frames < num_frames:
        ret, frame1080 = cap.read()
        if not ret:
            break
        frame_idx += 1
        if frame_idx % step != 0:
            continue

        h, w = frame1080.shape[:2]
        frame720 = cv2.resize(frame1080, (1280, 720), interpolation=cv2.INTER_LINEAR)

        # Run inference
        if mode == "PERSON":
            dets1080_raw = detector.detect(frame1080)
            dets720_raw = detector.detect(frame720)
        else:
            dets1080_raw = detector.detect(frame1080, tiled=False)
            dets720_raw = detector.detect(frame720, tiled=False)

        # Format: ([x1, y1, x2, y2], conf)
        boxes1080 = []
        for d in dets1080_raw:
            x, y, bw, bh = d[0]
            boxes1080.append(([x, y, x + bw, y + bh], float(d[1])))

        boxes720_scaled = []
        for d in dets720_raw:
            x, y, bw, bh = d[0]
            # Rescale to 1080p
            sx1 = x * scale_x
            sy1 = y * scale_y
            sx2 = (x + bw) * scale_x
            sy2 = (y + bh) * scale_y
            boxes720_scaled.append(([sx1, sy1, sx2, sy2], float(d[1])))

        matched, missed, extra = match_boxes(boxes1080, boxes720_scaled, iou_thresh=0.5)

        for _, _, iou_val, c_diff in matched:
            all_ious.append(iou_val)
            all_conf_diffs.append(c_diff)

        total_1080_count += len(boxes1080)
        total_720_count += len(boxes720_scaled)
        total_matched += len(matched)
        total_missed += len(missed)
        total_extra += len(extra)
        evaluated_frames += 1

    cap.release()

    # Cross-resolution agreement metrics (relative to 1080p reference detections)
    # Note: Evaluates relative consistency between resolutions, not absolute accuracy vs. human annotations.
    retention_rate = total_matched / total_1080_count if total_1080_count > 0 else 0.0  # 1080p detections matched in 720p
    concordance_rate = total_matched / total_720_count if total_720_count > 0 else 0.0  # 720p detections matched in 1080p
    harmonic_concordance = 2 * (concordance_rate * retention_rate) / (concordance_rate + retention_rate) if (concordance_rate + retention_rate) > 0 else 0.0
    dropout_rate = total_missed / total_1080_count if total_1080_count > 0 else 0.0
    extra_rate = total_extra / total_720_count if total_720_count > 0 else 0.0
    mean_iou = np.mean(all_ious) if all_ious else 0.0
    mean_conf_diff = np.mean(all_conf_diffs) if all_conf_diffs else 0.0

    print(f"\n--- Mode: {mode} ({evaluated_frames} frames evaluated) ---")
    print(f"Total Detections in 1080p (Reference): {total_1080_count}")
    print(f"Total Detections in 720p (Candidate):  {total_720_count}")
    print(f"Matched Detections (IoU >= 0.5):        {total_matched}")
    print(f"Discrepant (in 1080p, absent in 720p):  {total_missed} ({dropout_rate*100:.2f}%)")
    print(f"Additional (in 720p, absent in 1080p):  {total_extra} ({extra_rate*100:.2f}%)")
    print(f"Mean Bounding-Box IoU of Matches:       {mean_iou:.4f} ({mean_iou*100:.2f}%)")
    print(f"Mean Confidence Score Difference:       {mean_conf_diff:.4f}")
    print(f"1080p Reference Retention Rate:         {retention_rate:.4f} ({retention_rate*100:.2f}%)")
    print(f"720p Candidate Concordance Rate:        {concordance_rate:.4f} ({concordance_rate*100:.2f}%)")
    print(f"Harmonic Concordance Index (F-agree):   {harmonic_concordance:.4f}")


if __name__ == "__main__":
    print("=" * 65)
    print("DETECTION AGREEMENT AUDIT: 1080p REFERENCE vs. 720p CANDIDATE")
    print("=" * 65)
    video = "data/videos/temp/upload_CAM-01_temple 1.mp4"
    evaluate_video(video, mode="PERSON", num_frames=10)
    evaluate_video(video, mode="HEAD", num_frames=10)
    print("=" * 65)
