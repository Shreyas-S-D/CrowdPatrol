"""
Profile MobileNetV2 internal breakdown: OpenCV resize vs Tensor conversion vs PyTorch forward pass.
"""

import sys
import time
import cv2
import torch
import numpy as np
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
sys.path.append(str(BASE_DIR))

from src.tracking import PersonTracker

def profile_mobilenet():
    tracker = PersonTracker(max_age=15, n_init=1)
    embedder = tracker.tracker.embedder
    
    # 20 dummy head crops (e.g. 30x30 pixels each)
    crops = [np.random.randint(0, 256, (30, 30, 3), dtype=np.uint8) for _ in range(20)]
    
    # Warmup
    for _ in range(3):
        _ = embedder.predict(crops)
        
    t_resize_list = []
    t_tensor_list = []
    t_forward_list = []
    
    for _ in range(20):
        # 1. Resize & cvtColor
        t0 = time.perf_counter()
        n = len(crops)
        batch_np = np.empty((n, 224, 224, 3), dtype=np.uint8)
        for i, img in enumerate(crops):
            resized = cv2.resize(img, (224, 224), interpolation=cv2.INTER_LINEAR)
            cv2.cvtColor(resized, cv2.COLOR_BGR2RGB, dst=batch_np[i])
        t1 = time.perf_counter()
        t_resize_list.append((t1 - t0) * 1000)
        
        # 2. Tensor prep
        tensor = torch.from_numpy(batch_np).permute(0, 3, 1, 2).to(torch.float32) / 255.0
        if not hasattr(embedder, '_mean_tensor'):
            embedder._mean_tensor = torch.tensor([0.485, 0.456, 0.406]).view(1, 3, 1, 1)
            embedder._std_tensor = torch.tensor([0.229, 0.224, 0.225]).view(1, 3, 1, 1)
        tensor = (tensor - embedder._mean_tensor) / embedder._std_tensor
        t2 = time.perf_counter()
        t_tensor_list.append((t2 - t1) * 1000)
        
        # 3. Model forward
        with torch.inference_mode():
            output = embedder.model(tensor)
        t3 = time.perf_counter()
        t_forward_list.append((t3 - t2) * 1000)
        
    print(f"20 crops resize: {np.mean(t_resize_list):.2f} ms")
    print(f"20 crops tensor prep: {np.mean(t_tensor_list):.2f} ms")
    print(f"20 crops forward pass: {np.mean(t_forward_list):.2f} ms")
    print(f"Total: {np.mean(t_resize_list) + np.mean(t_tensor_list) + np.mean(t_forward_list):.2f} ms")

if __name__ == "__main__":
    profile_mobilenet()
