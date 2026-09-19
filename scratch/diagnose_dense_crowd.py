"""
Comprehensive Diagnostic Script for Dense Crowd Performance in CrowdPatrol.
Executes Phase 1, Phase 2, Phase 3, and Phase 6 diagnostics on data/videos/dense_crowd_test.mp4.
"""

import os
import sys
import json
import time
import cv2
import numpy as np
import torch
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.detection import PersonDetector
from src.tracking import PersonTracker
from src.density import DensityEstimator
from src.motion_analysis import CrowdMotionAnalyzer
from src.risk_assessment import RiskAssessor
from src.heatmap import generate_heatmap
from src.utils import FrameAnnotator

def run_diagnostics(max_eval_frames=300):
    video_path = "data/videos/dense_crowd_test.mp4"
    model_v2_path = "models/crowdpatrol_yolov8n_finetuned_v2.pt"
    model_stock_path = "yolov8n.pt"
    viz_dir = Path("training/visualizations/dense_crowd_diagnostics")
    viz_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"=== CROWDPATROL DENSE CROWD DIAGNOSTICS ===")
    print(f"Video Path: {video_path}")
    print(f"Fine-Tuned V2 Model: {model_v2_path}")
    print(f"Stock Model: {model_stock_path}")
    
    # 0. Open Video & Get Properties
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {video_path}")
        
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = float(cap.get(cv2.CAP_PROP_FPS))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    
    video_info = {
        "width": width,
        "height": height,
        "fps": fps,
        "total_frames": total_frames,
        "analyzed_frames": min(max_eval_frames, total_frames)
    }
    print(f"Video Properties: Resolution={width}x{height}, FPS={fps:.2f}, Total Frames={total_frames}")

    # =========================================================================
    # PHASE 1: REPRODUCE PROBLEM & DOWNSTREAM TRACE (Default V2, conf=0.35)
    # =========================================================================
    print(f"\n--- Running Phase 1: Problem Reproduction & Pipeline Trace ({video_info['analyzed_frames']} frames) ---")
    detector_v2_default = PersonDetector(model_path=model_v2_path, confidence=0.35, device="cpu")
    tracker = PersonTracker(max_age=30)
    density_estimator = DensityEstimator(grid_size=(4, 4))
    motion_analyzer = CrowdMotionAnalyzer(grid_size=(4, 4))
    risk_assessor = RiskAssessor()
    
    cap = cv2.VideoCapture(video_path)
    frame_count = 0
    phase1_records = []
    
    raw_yolo_counts = []
    deepsort_track_counts = []
    max_densities = []
    risk_scores = []
    risk_levels = []
    confidences_all = []
    
    while frame_count < video_info['analyzed_frames']:
        ret, frame = cap.read()
        if not ret:
            break
        frame_count += 1
        
        # Raw YOLO detection
        detections = detector_v2_default.detect(frame) # returns ([x, y, w, h], conf, cls)
        raw_count = len(detections)
        raw_yolo_counts.append(raw_count)
        
        frame_confs = [d[1] for d in detections]
        confidences_all.extend(frame_confs)
        
        # DeepSORT update
        tracks = tracker.update(detections, frame)
        track_count = len(tracks)
        deepsort_track_counts.append(track_count)
        
        # Motion analysis
        grid_matrix, motion_summary = motion_analyzer.analyze_frame(frame)
        
        # Density calculation
        density_map, max_density = density_estimator.calculate_density(tracks, frame.shape)
        max_densities.append(int(max_density))
        
        # Movement anomaly
        anomaly_score = risk_assessor.calculate_movement_anomaly(tracks, frame.shape)
        
        # Risk Assessment
        risk_res = risk_assessor.assess_frame(
            max_density=max_density,
            motion_summary=motion_summary,
            tracks=tracks,
            timestamp=time.time(),
            anomaly_score=anomaly_score
        )
        risk_scores.append(float(risk_res["combined_score"]))
        risk_levels.append(risk_res["risk"])
        
        phase1_records.append({
            "frame": frame_count,
            "raw_yolo_count": raw_count,
            "deepsort_tracks": track_count,
            "max_density": int(max_density),
            "anomaly_score": round(float(anomaly_score), 3),
            "risk_score": round(float(risk_res["combined_score"]), 2),
            "risk_level": risk_res["risk"],
            "confidences": [round(float(c), 3) for c in frame_confs]
        })
        
        # Save raw detection frame visual for representative frames
        if frame_count in [1, 15, 30, 45, 60, 90, 120, 150, 200, 250, 300]:
            raw_vis = frame.copy()
            for d in detections:
                box_tlwh, conf, cls = d
                x1, y1, w, h = box_tlwh
                x2, y2 = x1 + w, y1 + h
                cv2.rectangle(raw_vis, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
                cv2.putText(raw_vis, f"person {conf:.2f}", (int(x1), max(int(y1)-5, 15)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
            cv2.putText(raw_vis, f"Frame {frame_count} | Raw YOLO Detections: {raw_count} | Tracks: {track_count}", (20, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
            cv2.imwrite(str(viz_dir / f"raw_yolo_v2_frame_{frame_count:03d}.jpg"), raw_vis)
            
    cap.release()
    
    p1_stats = {
        "frames_analyzed": frame_count,
        "avg_raw_yolo": float(np.mean(raw_yolo_counts)),
        "min_raw_yolo": int(np.min(raw_yolo_counts)),
        "max_raw_yolo": int(np.max(raw_yolo_counts)),
        "avg_deepsort_tracks": float(np.mean(deepsort_track_counts)),
        "avg_max_density": float(np.mean(max_densities)),
        "avg_risk_score": float(np.mean(risk_scores)),
        "final_risk_level": risk_levels[-1] if risk_levels else "N/A",
        "mean_confidence": float(np.mean(confidences_all)) if confidences_all else 0.0,
        "median_confidence": float(np.median(confidences_all)) if confidences_all else 0.0,
        "max_confidence": float(np.max(confidences_all)) if confidences_all else 0.0
    }
    
    print("\nPhase 1 Reproduction Summary:")
    print(f"  Frames Analyzed:               {p1_stats['frames_analyzed']}")
    print(f"  Avg Raw YOLO Detections/Frame: {p1_stats['avg_raw_yolo']:.2f} (Min: {p1_stats['min_raw_yolo']}, Max: {p1_stats['max_raw_yolo']})")
    print(f"  Avg DeepSORT Tracks/Frame:     {p1_stats['avg_deepsort_tracks']:.2f}")
    print(f"  Avg Max Density:              {p1_stats['avg_max_density']:.2f}")
    print(f"  Avg Risk Score:               {p1_stats['avg_risk_score']:.2f}")
    print(f"  Final Risk Level:             {p1_stats['final_risk_level']}")
    print(f"  Mean Detection Confidence:    {p1_stats['mean_confidence']:.3f}")

    # =========================================================================
    # PHASE 2: CONFIDENCE THRESHOLD INVESTIGATION
    # =========================================================================
    print(f"\n--- Running Phase 2: Confidence Threshold Sweep ({video_info['analyzed_frames']} frames) ---")
    conf_thresholds = [0.10, 0.20, 0.25, 0.35, 0.50]
    conf_sweep_results = {}
    
    for conf in conf_thresholds:
        det = PersonDetector(model_path=model_v2_path, confidence=conf, device="cpu")
        cap = cv2.VideoCapture(video_path)
        
        counts = []
        confs = []
        frames_0 = 0
        frames_ge_50 = 0
        frames_ge_100 = 0
        saturation_300 = False
        
        fc = 0
        while fc < video_info['analyzed_frames']:
            ret, frame = cap.read()
            if not ret:
                break
            fc += 1
            dets = det.detect(frame)
            cnt = len(dets)
            counts.append(cnt)
            
            for d in dets:
                confs.append(float(d[1]))
                
            if cnt == 0:
                frames_0 += 1
            if cnt >= 50:
                frames_ge_50 += 1
            if cnt >= 100:
                frames_ge_100 += 1
            if cnt >= 300:
                saturation_300 = True
                
        cap.release()
        
        conf_sweep_results[f"conf_{conf:.2f}"] = {
            "confidence_threshold": float(conf),
            "avg_detections_per_frame": float(np.mean(counts)),
            "min_detections_per_frame": int(np.min(counts)),
            "max_detections_per_frame": int(np.max(counts)),
            "mean_confidence": float(np.mean(confs)) if confs else 0.0,
            "median_confidence": float(np.median(confs)) if confs else 0.0,
            "max_confidence": float(np.max(confs)) if confs else 0.0,
            "frames_with_0_detections": int(frames_0),
            "frames_with_ge_50_detections": int(frames_ge_50),
            "frames_with_ge_100_detections": int(frames_ge_100),
            "saturation_300_occurred": bool(saturation_300)
        }
        
        print(f"Conf {conf:.2f}: avg={np.mean(counts):.2f}, min={np.min(counts)}, max={np.max(counts)}, "
              f"mean_conf={(np.mean(confs) if confs else 0):.3f}, >=50={frames_ge_50}, >=100={frames_ge_100}, sat300={saturation_300}")

    # =========================================================================
    # PHASE 3: STOCK YOLOV8N VS FINE-TUNED V2 COMPARISON
    # =========================================================================
    print(f"\n--- Running Phase 3: Stock YOLOv8n vs Fine-Tuned V2 Comparison ({video_info['analyzed_frames']} frames) ---")
    comp_results = {}
    
    for conf_val in [0.35, 0.10]:
        det_stock = PersonDetector(model_path=model_stock_path, confidence=conf_val, device="cpu")
        det_v2 = PersonDetector(model_path=model_v2_path, confidence=conf_val, device="cpu")
        
        cap = cv2.VideoCapture(video_path)
        stock_counts = []
        v2_counts = []
        stock_confs = []
        v2_confs = []
        
        tracker_stock = PersonTracker(max_age=30)
        tracker_v2 = PersonTracker(max_age=30)
        stock_tracks_list = []
        v2_tracks_list = []
        
        fc = 0
        while fc < video_info['analyzed_frames']:
            ret, frame = cap.read()
            if not ret:
                break
            fc += 1
            
            # Stock
            dets_stock = det_stock.detect(frame)
            stock_counts.append(len(dets_stock))
            stock_confs.extend([float(d[1]) for d in dets_stock])
            tr_stock = tracker_stock.update(dets_stock, frame)
            stock_tracks_list.append(len(tr_stock))
            
            # V2
            dets_v2 = det_v2.detect(frame)
            v2_counts.append(len(dets_v2))
            v2_confs.extend([float(d[1]) for d in dets_v2])
            tr_v2 = tracker_v2.update(dets_v2, frame)
            v2_tracks_list.append(len(tr_v2))
            
            # Draw side-by-side comparison images for representative frames
            if fc in [1, 15, 30, 60, 90, 120, 180, 240, 300]:
                vis_stock = frame.copy()
                for d in dets_stock:
                    box_tlwh, c, _ = d
                    x1, y1, w, h = box_tlwh
                    x2, y2 = x1 + w, y1 + h
                    cv2.rectangle(vis_stock, (int(x1), int(y1)), (int(x2), int(y2)), (255, 0, 0), 2)
                    cv2.putText(vis_stock, f"{c:.2f}", (int(x1), max(int(y1)-5, 15)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 0, 0), 1)
                cv2.putText(vis_stock, f"Stock YOLOv8n (conf={conf_val}) | Dets: {len(dets_stock)} | Tracks: {len(tr_stock)}", 
                            (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

                vis_v2 = frame.copy()
                for d in dets_v2:
                    box_tlwh, c, _ = d
                    x1, y1, w, h = box_tlwh
                    x2, y2 = x1 + w, y1 + h
                    cv2.rectangle(vis_v2, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
                    cv2.putText(vis_v2, f"{c:.2f}", (int(x1), max(int(y1)-5, 15)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)
                cv2.putText(vis_v2, f"Fine-Tuned V2 (conf={conf_val}) | Dets: {len(dets_v2)} | Tracks: {len(tr_v2)}", 
                            (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

                side_by_side = np.hstack([vis_stock, vis_v2])
                out_path = viz_dir / f"comparison_conf_{conf_val:.2f}_frame_{fc:03d}.jpg"
                cv2.imwrite(str(out_path), side_by_side)
                
        cap.release()
        
        comp_results[f"conf_{conf_val:.2f}"] = {
            "stock_avg_detections": float(np.mean(stock_counts)),
            "stock_max_detections": int(np.max(stock_counts)),
            "stock_mean_confidence": float(np.mean(stock_confs)) if stock_confs else 0.0,
            "stock_avg_tracks": float(np.mean(stock_tracks_list)),
            "v2_avg_detections": float(np.mean(v2_counts)),
            "v2_max_detections": int(np.max(v2_counts)),
            "v2_mean_confidence": float(np.mean(v2_confs)) if v2_confs else 0.0,
            "v2_avg_tracks": float(np.mean(v2_tracks_list))
        }
        
        print(f"Conf={conf_val:.2f}: Stock Avg={np.mean(stock_counts):.2f} (Max {np.max(stock_counts)}, Tracks {np.mean(stock_tracks_list):.1f}), "
              f"V2 Avg={np.mean(v2_counts):.2f} (Max {np.max(v2_counts)}, Tracks {np.mean(v2_tracks_list):.1f})")

    # =========================================================================
    # PHASE 6: DOWNSTREAM PIPELINE TRACE ON REPRESENTATIVE FRAMES
    # =========================================================================
    print("\n--- Running Phase 6: Detailed Downstream Pipeline Trace ---")
    pipeline_trace = []
    
    detector_v2 = PersonDetector(model_path=model_v2_path, confidence=0.35, device="cpu")
    tracker_trace = PersonTracker(max_age=30)
    density_trace = DensityEstimator(grid_size=(4, 4))
    motion_trace = CrowdMotionAnalyzer(grid_size=(4, 4))
    risk_trace = RiskAssessor()
    
    cap = cv2.VideoCapture(video_path)
    fc = 0
    while fc < video_info['analyzed_frames']:
        ret, frame = cap.read()
        if not ret:
            break
        fc += 1
        
        raw_dets = detector_v2.detect(frame)
        tracks = tracker_trace.update(raw_dets, frame)
        grid_mat, motion_sum = motion_trace.analyze_frame(frame)
        d_map, max_d = density_trace.calculate_density(tracks, frame.shape)
        anom = risk_trace.calculate_movement_anomaly(tracks, frame.shape)
        r_res = risk_trace.assess_frame(
            max_density=max_d,
            motion_summary=motion_sum,
            tracks=tracks,
            timestamp=time.time(),
            anomaly_score=anom
        )
        
        trace_entry = {
            "frame": int(fc),
            "raw_yolo_count": int(len(raw_dets)),
            "deepsort_active_tracks": int(len(tracks)),
            "max_density": int(max_d),
            "anomaly_score": round(float(anom), 3),
            "raw_risk_score": round(float(r_res["raw_score"]), 2),
            "smoothed_risk_score": round(float(r_res["smoothed_score"]), 2),
            "risk_level": str(r_res["risk"])
        }
        pipeline_trace.append(trace_entry)
        
    cap.release()

    # Compile Final JSON Diagnostics
    final_output = {
        "video_info": video_info,
        "phase1_problem_reproduction": p1_stats,
        "phase2_confidence_sweep": conf_sweep_results,
        "phase3_stock_vs_v2": comp_results,
        "phase6_pipeline_trace_sample": pipeline_trace[:15] + pipeline_trace[::20] + pipeline_trace[-5:]
    }
    
    json_path = Path("training/dense_crowd_diagnostics.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(final_output, f, indent=2)
    print(f"\n[OK] Saved JSON Diagnostics to {json_path}")
    
    return final_output

if __name__ == "__main__":
    run_diagnostics(max_eval_frames=300)
