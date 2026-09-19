"""
CrowdPatrol Training Module - YOLOv8 Person Detector Fine-Tuning Script (V2)
Fine-tunes YOLOv8n on real CrowdHuman human crowd images & genuine full-body annotations (fbox).
Saves resulting weights to models/crowdpatrol_yolov8n_finetuned_v2.pt without overwriting stock yolov8n.pt
or previous artifact models/crowdpatrol_yolov8n_finetuned.pt.
"""

import os
import sys
import time
import json
import torch
import shutil
from pathlib import Path
from ultralytics import YOLO

BASE_DIR = Path(__file__).parent.parent
YOLO_YAML = BASE_DIR / "data" / "training" / "yolo" / "dataset.yaml"
OUTPUT_MODEL_DIR = BASE_DIR / "models"
OUTPUT_MODEL_DIR.mkdir(parents=True, exist_ok=True)
FINAL_WEIGHTS_PATH = OUTPUT_MODEL_DIR / "crowdpatrol_yolov8n_finetuned_v2.pt"


def train_yolov8_person_detector():
    print("==================================================")
    print("   CROWDPATROL YOLOv8 PERSON DETECTOR FINE-TUNING (V2 - REAL CROWDHUMAN)")
    print("==================================================")
    
    # Detect hardware
    cuda_available = torch.cuda.is_available()
    device = "cuda" if cuda_available else "cpu"
    print(f"[*] Hardware Execution Environment: {'CUDA GPU (' + torch.cuda.get_device_name(0) + ')' if cuda_available else 'CPU (PyTorch 2.14.0+cpu)'}")
    print(f"[*] Dataset Config: {YOLO_YAML}")
    print(f"[*] Base Weights:    yolov8n.pt")
    print(f"[*] Target Weights:  {FINAL_WEIGHTS_PATH}")
    
    # Load pretrained baseline weights
    model = YOLO("yolov8n.pt")
    
    # Training configuration parameters optimized for CPU transfer learning
    epochs = 3
    imgsz = 480
    batch_size = 16 if cuda_available else 16
    fraction = 0.35  # Uses ~1,070 real crowd images (25,000+ person boxes)
    lr0 = 0.01
    seed = 42
    
    config_record = {
        "base_model": "yolov8n.pt",
        "dataset": str(YOLO_YAML),
        "imgsz": imgsz,
        "epochs": epochs,
        "batch_size": batch_size,
        "fraction": fraction,
        "optimizer": "auto",
        "learning_rate": lr0,
        "device": device,
        "cuda_available": cuda_available,
        "seed": seed,
        "target_model": str(FINAL_WEIGHTS_PATH)
    }
    
    print(f"\n[*] Starting YOLOv8 fine-tuning process ({epochs} epochs, fraction={fraction} on real CrowdHuman images)...")
    t_start = time.perf_counter()
    
    results = model.train(
        data=str(YOLO_YAML),
        epochs=epochs,
        imgsz=imgsz,
        batch=batch_size,
        fraction=fraction,
        device=device,
        seed=seed,
        project=str(BASE_DIR / "runs" / "detect"),
        name="crowdpatrol_finetune_v2",
        exist_ok=True,
        verbose=True
    )
    
    t_end = time.perf_counter()
    training_time_sec = t_end - t_start
    print(f"\n[OK] Fine-tuning completed in {training_time_sec:.2f} seconds ({training_time_sec/60.0:.2f} mins).")
    
    # Save the resulting fine-tuned model to models/crowdpatrol_yolov8n_finetuned_v2.pt
    best_weights = BASE_DIR / "runs" / "detect" / "crowdpatrol_finetune_v2" / "weights" / "best.pt"
    if best_weights.exists():
        shutil.copy(best_weights, FINAL_WEIGHTS_PATH)
        print(f"[OK] Saved fine-tuned V2 weights to {FINAL_WEIGHTS_PATH}")
    else:
        model.save(str(FINAL_WEIGHTS_PATH))
        print(f"[OK] Saved model weights to {FINAL_WEIGHTS_PATH}")
        
    config_record["training_time_sec"] = round(training_time_sec, 2)
    config_record["final_model_path"] = str(FINAL_WEIGHTS_PATH)
    
    with open(BASE_DIR / "training" / "training_config.json", "w") as f:
        json.dump(config_record, f, indent=2)
        
    print("[OK] Fine-tuning stage V2 completed successfully.")


if __name__ == "__main__":
    train_yolov8_person_detector()
