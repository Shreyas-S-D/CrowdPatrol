"""
CrowdPatrol - Autonomous Public Safety & Monitoring System
Core modules for detection, tracking, density estimation, and risk assessment.
"""

__version__ = "1.0.0"
__author__ = "Team 21 - AMC Engineering College"

from .detection import PersonDetector
from .tracking import PersonTracker
from .density import DensityEstimator
from .risk_assessment import RiskAssessor, RiskLevel, ScoreEMA, HysteresisStateMachine
from .alerts import FirebaseAlertManager as AlertManager
from .motion_analysis import CrowdMotionAnalyzer, GridMotionCell
from .utils import (
    VideoProcessor,
    MetricsLogger,
    FrameAnnotator,
    ConfigLoader,
    preprocess_frame,
    calculate_optical_flow,
    format_timestamp,
    create_directory_structure
)

__all__ = [
    "PersonDetector",
    "PersonTracker",
    "DensityEstimator",
    "RiskAssessor",
    "RiskLevel",
    "ScoreEMA",
    "HysteresisStateMachine",
    "AlertManager",
    "CrowdMotionAnalyzer",
    "GridMotionCell",
    "VideoProcessor",
    "MetricsLogger",
    "FrameAnnotator",
    "ConfigLoader",
    "preprocess_frame",
    "calculate_optical_flow",
    "format_timestamp",
    "create_directory_structure"
]