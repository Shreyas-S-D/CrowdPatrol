"""
Test chunked sub-batching for MobileNetV2 in PyTorch CPU mode.
"""

import sys
from pathlib import Path
BASE_DIR = Path(__file__).parent.parent
sys.path.append(str(BASE_DIR))
import torch, time

def test_chunking():
    from src.tracking import PersonTracker
    tracker = PersonTracker(max_age=15, n_init=1)
    model = tracker.tracker.embedder.model
    
    n_crops = 60
    x = torch.randn(n_crops, 3, 224, 224, dtype=torch.float32).to(memory_format=torch.channels_last)
    
    # 1. Monolithic batch 60
    t_mono = []
    for _ in range(3):
        t0 = time.perf_counter()
        with torch.inference_mode():
            out1 = model(x)
        t_mono.append((time.perf_counter() - t0) * 1000)
    print(f"Monolithic batch {n_crops}: {min(t_mono):.1f} ms")
    
    # 2. Chunked sub-batches of size 16
    chunk_size = 16
    t_chunk = []
    for _ in range(3):
        t0 = time.perf_counter()
        outs = []
        with torch.inference_mode():
            for i in range(0, n_crops, chunk_size):
                sub_x = x[i:i+chunk_size]
                outs.append(model(sub_x))
            out2 = torch.cat(outs, dim=0)
        t_chunk.append((time.perf_counter() - t0) * 1000)
    print(f"Chunked (size={chunk_size}) batch {n_crops}: {min(t_chunk):.1f} ms")
    
    max_diff = torch.max(torch.abs(out1 - out2)).item()
    print(f"Max diff: {max_diff:.8f}")

if __name__ == "__main__":
    test_chunking()
