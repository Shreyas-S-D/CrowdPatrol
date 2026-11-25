import os
import sys
import time
import platform
import psutil
import json
import cv2
import torch
import numpy as np
from pathlib import Path

# Add project root to sys.path
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from src.detection import PersonDetector
from src.tracking import PersonTracker
from src.density import DensityEstimator
from src.motion_analysis import CrowdMotionAnalyzer
from src.risk_assessment import RiskAssessor

def get_hardware_and_environment():
    uname = platform.uname()
    cpu_info = uname.processor or "Intel"
    # Query WMI or powershell for CPU name on Windows if needed
    try:
        import subprocess
        cpu_name = subprocess.check_output("wmic cpu get name", shell=True).decode().split('\n')[1].strip()
    except Exception:
        cpu_name = platform.processor()

    ram_gb = round(psutil.virtual_memory().total / (1024**3), 2)
    has_gpu = torch.cuda.is_available()
    gpu_name = torch.cuda.get_device_name(0) if has_gpu else "None (CPU Execution)"

    import ultralytics
    import deep_sort_realtime

    env_info = {
        "python_version": sys.version.split()[0],
        "opencv_version": cv2.__version__,
        "torch_version": torch.__version__,
        "ultralytics_version": ultralytics.__version__,
        "deep_sort_realtime_version": getattr(deep_sort_realtime, "__version__", "1.3.2"),
        "cpu_model": cpu_name,
        "physical_cores": psutil.cpu_count(logical=False),
        "logical_cores": psutil.cpu_count(logical=True),
        "ram_gb": ram_gb,
        "gpu_available": has_gpu,
        "gpu_used": gpu_name
    }
    return env_info

def inspect_video(video_path):
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise FileNotFoundError(f"Cannot open video: {video_path}")
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = float(cap.get(cv2.CAP_PROP_FPS))
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    return {
        "name": Path(video_path).name,
        "path": str(video_path),
        "width": w,
        "height": h,
        "resolution": f"{w}x{h}",
        "fps": fps,
        "frame_count": frame_count
    }

def run_pipeline_benchmark(video_path, detect_interval=3, total_frames_to_process=330, warmup_frames=30):
    """
    Runs the full pipeline, recording per-stage latencies for each frame.
    Warmup frames are discarded from statistical metrics.
    """
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise FileNotFoundError(f"Cannot open video: {video_path}")

    detector = PersonDetector(confidence=0.35, device="cpu", imgsz=640)
    tracker = PersonTracker(max_age=30, n_init=1)
    density_estimator = DensityEstimator(grid_size=(4, 4))
    motion_analyzer = CrowdMotionAnalyzer(grid_size=(4, 4), downscale_size=(320, 180), flow_interval=1)
    risk_assessor = RiskAssessor()

    decode_times = []
    detect_times = []
    track_times = []
    density_times = []
    flow_times = []
    risk_times = []
    total_frame_times = []
    
    person_counts = []
    detections_per_frame = []
    active_tracks_per_frame = []

    frame_idx = 0
    while frame_idx < total_frames_to_process:
        t_start = time.perf_counter()
        
        # 1. Decode & read
        t0 = time.perf_counter()
        ret, frame = cap.read()
        if not ret:
            break
        t_decode = (time.perf_counter() - t0) * 1000.0

        frame_idx += 1
        is_detect = (frame_idx == 1 or (frame_idx % detect_interval == 0))

        # 2. YOLOv8 Detection
        t0 = time.perf_counter()
        if is_detect:
            detections = detector.detect(frame)
        else:
            detections = []
        t_detect = (time.perf_counter() - t0) * 1000.0

        # 3. DeepSORT Tracking
        t0 = time.perf_counter()
        if is_detect:
            current_tracks = tracker.update(detections, frame)
        else:
            current_tracks = tracker.predict()
        t_track = (time.perf_counter() - t0) * 1000.0

        # 4. Density
        t0 = time.perf_counter()
        density_map, max_density = density_estimator.calculate_density(current_tracks, frame.shape)
        t_density = (time.perf_counter() - t0) * 1000.0

        # 5. Optical flow
        t0 = time.perf_counter()
        grid_matrix, motion_summary = motion_analyzer.analyze_frame(frame)
        t_flow = (time.perf_counter() - t0) * 1000.0

        # 6. Risk Engine
        t0 = time.perf_counter()
        motion_anomaly = motion_summary.get("anomaly_score", 0.0)
        track_anomaly = risk_assessor.calculate_movement_anomaly(current_tracks, frame.shape) if current_tracks else 0.0
        anomaly_score = max(track_anomaly, motion_anomaly)
        risk_res = risk_assessor.assess_frame(
            max_density=max_density,
            motion_summary=motion_summary,
            tracks=current_tracks,
            timestamp=time.time(),
            anomaly_score=anomaly_score
        )
        t_risk = (time.perf_counter() - t0) * 1000.0

        t_total = (time.perf_counter() - t_start) * 1000.0

        # Only record stats after warmup
        if frame_idx > warmup_frames:
            decode_times.append(t_decode)
            detect_times.append(t_detect)
            track_times.append(t_track)
            density_times.append(t_density)
            flow_times.append(t_flow)
            risk_times.append(t_risk)
            total_frame_times.append(t_total)
            if is_detect:
                detections_per_frame.append(len(detections))
            person_counts.append(len(current_tracks))

    cap.release()

    def stats(arr):
        if arr is None or len(arr) == 0:
            return {"mean": 0.0, "median": 0.0, "std": 0.0, "min": 0.0, "max": 0.0}
        a = np.array(arr, dtype=np.float64)
        return {
            "mean": float(np.mean(a)),
            "median": float(np.median(a)),
            "std": float(np.std(a)),
            "min": float(np.min(a)),
            "max": float(np.max(a))
        }

    total_time_arr = np.array(total_frame_times)
    fps_arr = 1000.0 / total_time_arr if len(total_time_arr) > 0 else []

    return {
        "frames_evaluated": len(total_frame_times),
        "warmup_frames_discarded": warmup_frames,
        "detect_interval": detect_interval,
        "pipeline_fps": stats(fps_arr),
        "total_ms": stats(total_frame_times),
        "decode_ms": stats(decode_times),
        "detect_ms": stats(detect_times),
        "track_ms": stats(track_times),
        "density_ms": stats(density_times),
        "flow_ms": stats(flow_times),
        "risk_ms": stats(risk_times),
        "detections_per_detect_frame": stats(detections_per_frame),
        "tracked_persons_per_frame": stats(person_counts),
        "max_persons_in_any_frame": int(np.max(person_counts)) if person_counts else 0,
        "avg_persons_detected_per_frame": float(np.mean(detections_per_frame)) if detections_per_frame else 0.0
    }

def run_optical_flow_comparison(video_path, total_frames=330, warmup_frames=30):
    """
    Times Farneback optical flow at full resolution vs 320x180 reduced resolution on the same frames.
    """
    cap = cv2.VideoCapture(str(video_path))
    farneback_params = dict(
        pyr_scale=0.5, levels=3, winsize=15,
        iterations=3, poly_n=5, poly_sigma=1.2, flags=0
    )

    full_res_times = []
    downscaled_times = []

    prev_gray_full = None
    prev_gray_down = None

    frame_idx = 0
    while frame_idx < total_frames:
        ret, frame = cap.read()
        if not ret:
            break
        frame_idx += 1

        gray_full = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray_down = cv2.resize(gray_full, (320, 180))

        if prev_gray_full is not None and prev_gray_down is not None:
            # Time full resolution Farneback
            t0 = time.perf_counter()
            cv2.calcOpticalFlowFarneback(prev_gray_full, gray_full, None, **farneback_params)
            t_full = (time.perf_counter() - t0) * 1000.0

            # Time downscaled Farneback
            t0 = time.perf_counter()
            cv2.calcOpticalFlowFarneback(prev_gray_down, gray_down, None, **farneback_params)
            t_down = (time.perf_counter() - t0) * 1000.0

            if frame_idx > warmup_frames:
                full_res_times.append(t_full)
                downscaled_times.append(t_down)

        prev_gray_full = gray_full
        prev_gray_down = gray_down

    cap.release()

    def stats(arr):
        if arr is None or len(arr) == 0:
            return {"mean": 0.0, "median": 0.0, "std": 0.0}
        a = np.array(arr, dtype=np.float64)
        return {
            "mean": float(np.mean(a)),
            "median": float(np.median(a)),
            "std": float(np.std(a))
        }

    return {
        "full_resolution_ms": stats(full_res_times),
        "downscaled_resolution_ms": stats(downscaled_times)
    }

if __name__ == "__main__":
    print("=" * 60)
    print("CrowdPatrol IEEE Benchmark & Extraction Suite")
    print("=" * 60)

    env = get_hardware_and_environment()
    print("Environment:", json.dumps(env, indent=2))

    video_file = _ROOT / "data" / "videos" / "youtube_crowd_test.mp4"
    if not video_file.exists():
        video_file = _ROOT.parent / "CrowdPatrol" / "data" / "videos" / "youtube_crowd_test.mp4"
    
    vid_meta = inspect_video(video_file)
    print("Video Metadata:", json.dumps(vid_meta, indent=2))

    print("\n[1/3] Running Full Pipeline Benchmark with Frame Skipping ON (detect_interval=3)...")
    res_skip_on = run_pipeline_benchmark(video_file, detect_interval=3, total_frames_to_process=330, warmup_frames=30)
    print(f"Skipping ON: FPS = {res_skip_on['pipeline_fps']['mean']:.2f} +/- {res_skip_on['pipeline_fps']['std']:.2f}")

    print("\n[2/3] Running Full Pipeline Benchmark with Frame Skipping OFF (detect_interval=1)...")
    res_skip_off = run_pipeline_benchmark(video_file, detect_interval=1, total_frames_to_process=330, warmup_frames=30)
    print(f"Skipping OFF: FPS = {res_skip_off['pipeline_fps']['mean']:.2f} +/- {res_skip_off['pipeline_fps']['std']:.2f}")

    print("\n[3/3] Running Farneback Optical Flow Resolution Comparison...")
    flow_comp = run_optical_flow_comparison(video_file, total_frames=330, warmup_frames=30)
    print(f"Full Res Flow: {flow_comp['full_resolution_ms']['mean']:.2f} ms | Downscaled Flow: {flow_comp['downscaled_resolution_ms']['mean']:.2f} ms")

    benchmark_output = {
        "environment": env,
        "video": vid_meta,
        "benchmark_frame_skip_on": res_skip_on,
        "benchmark_frame_skip_off": res_skip_off,
        "optical_flow_comparison": flow_comp
    }

    out_json = _ROOT / "paper_eval" / "benchmark_results.json"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    with open(out_json, "w") as f:
        json.dump(benchmark_output, f, indent=2)

    print(f"\n[✓] Benchmark complete! Results saved to {out_json}")
