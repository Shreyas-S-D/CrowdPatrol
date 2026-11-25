"""
Test channels-last memory format on MobileNetV2 and YOLOv8 on CPU.
"""

import sys
import time
import torch
import numpy as np
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
sys.path.append(str(BASE_DIR))

from src.tracking import PersonTracker

def test_channels_last():
    tracker = PersonTracker(max_age=15, n_init=1)
    model = tracker.tracker.embedder.model
    
    batch_size = 20
    x = torch.randn(batch_size, 3, 224, 224, dtype=torch.float32)
    
    # Warmup contiguous
    for _ in range(3):
        with torch.inference_mode():
            _ = model(x)
            
    t_std = []
    for _ in range(10):
        t0 = time.perf_counter()
        with torch.inference_mode():
            _ = model(x)
        t_std.append((time.perf_counter() - t0) * 1000)
    print(f"Standard Contiguous MobileNetV2: {np.mean(t_std):.2f} ms")
    
    # Channels Last
    model_cl = model.to(memory_format=torch.channels_last)
    x_cl = x.to(memory_format=torch.channels_last)
    
    for _ in range(3):
        with torch.inference_mode():
            _ = model_cl(x_cl)
            
    t_cl = []
    for _ in range(10):
        t0 = time.perf_counter()
        with torch.inference_mode():
            _ = model_cl(x_cl)
        t_cl.append((time.perf_counter() - t0) * 1000)
    print(f"Channels-Last MobileNetV2: {np.mean(t_cl):.2f} ms")
    
    # Check numerical equivalence
    with torch.inference_mode():
        out1 = model(x)
        out2 = model_cl(x_cl)
    max_diff = torch.max(torch.abs(out1 - out2)).item()
    print(f"Max difference between standard and channels-last: {max_diff:.8f}")

if __name__ == "__main__":
    test_channels_last()
