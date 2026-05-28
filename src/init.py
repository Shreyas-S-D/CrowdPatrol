"""
CrowdPatrol - Autonomous Public Safety & Monitoring System
Core modules for detection, tracking, density estimation, and risk assessment.
"""

__version__ = "1.0.0"
__author__ = "Team 21 - AMC Engineering College"

from .detection import PersonDetector
from .tracking import PersonTracker
from .density import DensityEstimator
from .risk_assessment import RiskAssessor, RiskLevel
from .alerts import AlertManager
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
    "AlertManager",
    "VideoProcessor",
    "MetricsLogger",
    "FrameAnnotator",
    "ConfigLoader",
    "preprocess_frame",
    "calculate_optical_flow",
    "format_timestamp",
    "create_directory_structure"
]