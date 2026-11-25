"""
CrowdPatrol Phase 11.1 — MobileNetV2 Embedding Numerical Equivalence Audit
"""

import torch
import numpy as np
from deep_sort_realtime.embedder.embedder_pytorch import MobileNetv2_Embedder


def audit_embeddings():
    print("=" * 65)
    print("MOBILENETV2 EMBEDDING NUMERICAL EQUIVALENCE AUDIT")
    print("=" * 65)

    emb = MobileNetv2_Embedder()
    emb.model.eval()

    torch.manual_seed(42)
    # Generate 50 simulated person crops
    x = torch.randn(50, 3, 224, 224)

    # 1. Standard Eager NCHW
    with torch.inference_mode():
        out_eager = emb.model(x).cpu().numpy()

    # 2. Optimized Channels-Last
    emb.model.to(memory_format=torch.channels_last)
    x_cl = x.to(memory_format=torch.channels_last)
    with torch.inference_mode():
        out_cl = emb.model(x_cl).cpu().numpy()

    max_abs_diff = np.max(np.abs(out_eager - out_cl))
    mean_abs_diff = np.mean(np.abs(out_eager - out_cl))

    # Cosine similarities
    cos_sims = []
    for i in range(len(out_eager)):
        v1 = out_eager[i]
        v2 = out_cl[i]
        sim = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))
        cos_sims.append(sim)

    min_cos_sim = np.min(cos_sims)
    mean_cos_sim = np.mean(cos_sims)

    print(f"Number of Evaluation Samples: {len(out_eager)} crops")
    print(f"Max Absolute Error:          {max_abs_diff:.8e}")
    print(f"Mean Absolute Error:         {mean_abs_diff:.8e}")
    print(f"Minimum Cosine Similarity:   {min_cos_sim:.8f} (1.0 = exact)")
    print(f"Mean Cosine Similarity:      {mean_cos_sim:.8f}")
    print(f"Pass Tolerance (sim >= 0.9999): {min_cos_sim >= 0.9999}")
    print("=" * 65)


if __name__ == "__main__":
    audit_embeddings()
