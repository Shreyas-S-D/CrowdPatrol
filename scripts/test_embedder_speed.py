import time
import cv2
import torch
import numpy as np
from deep_sort_realtime.embedder.embedder_pytorch import MobileNetv2_Embedder

torch.set_num_threads(14)
emb = MobileNetv2_Embedder()
emb.model.eval()

crops = [np.random.randint(0, 255, (100, 50, 3), dtype=np.uint8) for _ in range(19)]
b = np.empty((19, 224, 224, 3), dtype=np.uint8)
for i, c in enumerate(crops):
    cv2.cvtColor(cv2.resize(c, (224, 224)), cv2.COLOR_BGR2RGB, dst=b[i])
tens = torch.from_numpy(b).permute(0, 3, 1, 2).float() / 255.0

# 1. Standard eager
with torch.inference_mode():
    _ = emb.model(tens)

t0 = time.perf_counter()
for _ in range(5):
    with torch.inference_mode():
        _ = emb.model(tens)
t_eager = (time.perf_counter() - t0) / 5 * 1000
print(f"Standard Eager: {t_eager:.2f} ms")

# 2. Channels last
emb.model = emb.model.to(memory_format=torch.channels_last)
tens_cl = tens.to(memory_format=torch.channels_last)
with torch.inference_mode():
    _ = emb.model(tens_cl)

t0 = time.perf_counter()
for _ in range(5):
    with torch.inference_mode():
        _ = emb.model(tens_cl)
t_cl = (time.perf_counter() - t0) / 5 * 1000
print(f"Channels-last: {t_cl:.2f} ms")

# 3. TorchScript traced
example = tens[:1]
try:
    with torch.inference_mode():
        traced = torch.jit.trace(emb.model, example)
        traced = torch.jit.optimize_for_inference(traced)
    
    t0 = time.perf_counter()
    for _ in range(5):
        with torch.inference_mode():
            _ = traced(tens_cl)
    t_traced = (time.perf_counter() - t0) / 5 * 1000
    print(f"TorchScript Traced + optimize_for_inference: {t_traced:.2f} ms")
except Exception as e:
    print(f"Tracing failed: {e}")
