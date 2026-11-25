"""Tests for CrowdMotionAnalyzer optical flow module"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import cv2
from ultralytics.utils import ASSETS
from src.motion_analysis import CrowdMotionAnalyzer, GridMotionCell


def test_motion_analyzer_initialization():
    """Test analyzer initialization"""
    analyzer = CrowdMotionAnalyzer(grid_size=(4, 4))
    assert analyzer is not None
    print("[✓] Motion analyzer initialization test passed")


def test_motion_stationary_frames():
    """Test motion analysis on identical stationary frames"""
    analyzer = CrowdMotionAnalyzer(grid_size=(4, 4))
    frame1 = np.zeros((720, 1280, 3), dtype=np.uint8)
    frame2 = np.zeros((720, 1280, 3), dtype=np.uint8)
    
    grid1, summary1 = analyzer.analyze_frame(frame1)
    assert len(grid1) == 4
    assert len(grid1[0]) == 4
    assert summary1["dominant_direction"] == "STATIONARY"
    
    grid2, summary2 = analyzer.analyze_frame(frame2)
    assert summary2["avg_speed"] < 0.1
    assert summary2["dominant_direction"] == "STATIONARY"
    print("[✓] Stationary frames motion test passed")


def test_camera_motion_subtraction():
    """Test global camera motion detection and subtraction on image translation"""
    analyzer = CrowdMotionAnalyzer(grid_size=(4, 4))
    img1 = cv2.imread(str(ASSETS / "bus.jpg"))
    h, w = img1.shape[:2]
    
    # Translate whole image to simulate camera pan
    M = np.float32([[1, 0, 15], [0, 1, 0]])
    img2 = cv2.warpAffine(img1, M, (w, h))
    
    _, _ = analyzer.analyze_frame(img1)
    grid, summary = analyzer.analyze_frame(img2)
    
    assert summary["camera_motion_detected"] == True
    print(f"[✓] Camera motion subtraction test passed: Camera Motion Detected = {summary['camera_motion_detected']}")


def test_localized_crowd_movement():
    """Test localized motion detection in a specific grid cell"""
    analyzer = CrowdMotionAnalyzer(grid_size=(4, 4))
    img1 = cv2.imread(str(ASSETS / "bus.jpg"))
    img2 = img1.copy()
    
    h, w = img1.shape[:2]
    # Move localized region in bottom right quadrant
    patch = img1[h//2:h//2+100, w//2:w//2+100]
    img2[h//2+10:h//2+110, w//2+10:w//2+110] = patch
    
    _, _ = analyzer.analyze_frame(img1)
    grid, summary = analyzer.analyze_frame(img2)
    
    assert summary["max_speed"] > 0.1
    print(f"[✓] Localized crowd movement test passed: Max Speed = {summary['max_speed']} px/frame")


if __name__ == "__main__":
    test_motion_analyzer_initialization()
    test_motion_stationary_frames()
    test_camera_motion_subtraction()
    test_localized_crowd_movement()
    print("\n[✓] All optical flow motion tests passed!")
