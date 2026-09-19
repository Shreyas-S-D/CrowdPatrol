# CrowdPatrol Training Dataset Audit & Specification

## Dataset Audit & Usage Categorization Summary

| Dataset Name | Source / URL | License | Annotation Format | Genuine Full-Body BBoxes? | Category & Usage |
|---|---|---|---|---|---|
| **CrowdHuman** | [https://www.crowdhuman.org/](https://www.crowdhuman.org/) | Custom Non-Commercial / Academic Research Use Only | JSON / ODGT (fbox: [x,y,w,h] full body, vbox: [x,y,w,h] visible body, headbox) | Yes (fbox / vbox) | **A. YOLO PERSON-DETECTION TRAINING** |
| **UCF-QNRF** | [https://www.crcv.ucf.edu/data/ucf-qnrf/](https://www.crcv.ucf.edu/data/ucf-qnrf/) | Academic Research Use Only | MATLAB .mat (Point locations / Head coordinates [x, y]) | No (Point / Count / Synthetic) | **B. DENSE-CROWD / COUNT / MOTION EVALUATION ONLY** |
| **HAJJv2-CrowdCount** | [https://github.com/reem-8899/HAJJv2-CrowdCount](https://github.com/reem-8899/HAJJv2-CrowdCount) | MIT / Academic Research | CSV (Global crowd counts per video frame) | No (Point / Count / Synthetic) | **B. DENSE-CROWD / COUNT / MOTION EVALUATION ONLY** |
| **PPS-D (Public Space Surveillance)** | [https://zenodo.org/records/15124010](https://zenodo.org/records/15124010) | CC-BY 4.0 (Synthetic Surveillance Data) | JSON / Synthetic Bounding Boxes | No (Point / Count / Synthetic) | **B. DENSE-CROWD / COUNT / MOTION EVALUATION ONLY** |
| **Bengaluru Real-World Crowd Video** | [Local Repository Asset (data/videos/youtube_crowd_test.mp4)](Local Repository Asset (data/videos/youtube_crowd_test.mp4)) | Held-out Evaluation Video | MP4 Video Stream (1280x720, 3493 frames) | Yes (fbox / vbox) | **C. HELD-OUT BENGALURU TESTING** |

---

## Categorization Guidelines & Rules Enforced

1. **A. YOLO PERSON-DETECTION TRAINING**: Only datasets containing verified, genuine person/full-body bounding boxes (`fbox` / `vbox`) enter the YOLOv8 detector training split. **CrowdHuman** (real human photos) is the primary training dataset.
2. **B. DENSE-CROWD / COUNT / MOTION EVALUATION ONLY**: Datasets containing point annotations (UCF-QNRF), global crowd counts (HAJJv2), or synthetic video (PPS-D) are **NOT** used for bounding box training to prevent fake/fabricated bounding boxes.
3. **C. HELD-OUT BENGALURU TESTING**: `data/videos/youtube_crowd_test.mp4` is strictly held out for real-world final evaluation. **ZERO frames from this video enter training or validation splits.**
4. **ZERO SYNTHETIC SHAPES**: All training images are real-world human crowd photographs downloaded directly from CrowdHuman. No gray synthetic canvas shapes are used.
