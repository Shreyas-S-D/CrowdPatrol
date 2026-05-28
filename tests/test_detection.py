"""Tests for detection module"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
from src.detection import PersonDetector


def test_detector_initialization():
    """Test that detector loads correctly"""
    detector = PersonDetector(model_path="yolov8n.pt", device="cpu")
    assert detector is not None
    print("[✓] Detector initialization test passed")


def test_detect_empty_frame():
    """Test detection on blank frame"""
    detector = PersonDetector(model_path="yolov8n.pt", device="cpu")
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    detections = detector.detect(frame)
    assert len(detections) == 0  # No persons in blank frame
    print("[✓] Empty frame detection test passed")


if __name__ == "__main__":
    test_detector_initialization()
    test_detect_empty_frame()
    print("\n[✓] All detection tests passed!")