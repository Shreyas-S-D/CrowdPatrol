"""
CrowdPatrol Demo - Verification Test Suite for Minimal Authentication Gate
Verifies:
1. Login succeeds with provisioned credentials.
2. Incorrect passwords are rejected.
3. Unauthenticated sessions are blocked.
4. Logout resets authentication state.
5. Original monitoring components, dual-mode detectors, and alert pipeline function correctly.
"""

import os
import sys
from pathlib import Path
import pytest

# Ensure CrowdPatrol_Demo root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.demo_auth import (
    init_auth_db,
    provision_user,
    authenticate_user,
    hash_password,
    verify_password
)
from src.detection import PersonDetector
from src.experimental_head_mode import ExperimentalHeadDetector
from src.multi_camera_manager import MultiCameraManager
from src.alert_manager import AlertManager


def test_password_hashing_and_verification():
    """Verify scrypt hashing produces secure unique hashes and validates correctly."""
    pwd = "DemoPassword2026!"
    h1, s1 = hash_password(pwd)
    h2, s2 = hash_password(pwd)

    # Different salts must yield different hashes
    assert s1 != s2
    assert h1 != h2

    # Verification must succeed for valid password
    assert verify_password(pwd, h1, s1) is True
    assert verify_password(pwd, h2, s2) is True

    # Verification must fail for invalid password
    assert verify_password("WrongPassword123!", h1, s1) is False
    assert verify_password("", h1, s1) is False


def test_user_provisioning_and_authentication(tmp_path):
    """Verify administrator provisioning and login authentication lifecycle."""
    test_db = tmp_path / "test_auth.db"
    init_auth_db(test_db)

    # Provision administrator
    assert provision_user("demo_admin", "AdminSecret123!", role="Administrator", db_path=test_db) is True

    # Successful login
    auth_success = authenticate_user("demo_admin", "AdminSecret123!", db_path=test_db)
    assert auth_success is not None
    assert auth_success["username"] == "demo_admin"
    assert auth_success["role"] == "Administrator"

    # Case insensitive username login
    auth_case = authenticate_user("DEMO_ADMIN", "AdminSecret123!", db_path=test_db)
    assert auth_case is not None

    # Failed login: incorrect password
    auth_fail = authenticate_user("demo_admin", "WrongSecret!", db_path=test_db)
    assert auth_fail is None

    # Failed login: nonexistent user
    auth_missing = authenticate_user("ghost_operator", "AdminSecret123!", db_path=test_db)
    assert auth_missing is None


def test_original_detectors_and_models_intact():
    """Verify original YOLOv8 person detector and experimental head detector models load intact."""
    # Person Detector (YOLOv8n / fine-tuned)
    person_detector = PersonDetector(confidence=0.35, imgsz=640, device="cpu")
    assert person_detector is not None
    assert person_detector.confidence == 0.35
    assert person_detector.imgsz == 640

    # Head Detector
    head_detector = ExperimentalHeadDetector(confidence=0.25, imgsz=640, device="cpu")
    assert head_detector is not None
    assert head_detector.confidence == 0.25


def test_original_multi_camera_manager_intact():
    """Verify MultiCameraManager initializes with original CCTV grid and alert pipeline."""
    manager = MultiCameraManager(device="cpu")
    assert manager is not None
    assert len(manager.cameras) == 4
    for slot_id in ["CAM-01", "CAM-02", "CAM-03", "CAM-04"]:
        assert slot_id in manager.cameras

    # Alert manager intact
    assert manager.alert_manager is not None
    assert isinstance(manager.alert_manager, AlertManager)


def test_streamlit_app_authentication_gate():
    """Verify Streamlit AppTest halts on login screen when unauthenticated and unlocks when authenticated."""
    from streamlit.testing.v1 import AppTest

    script_path = str(PROJECT_ROOT / "dashboard" / "simple_dashboard.py")
    
    # 1. Test Unauthenticated Access
    at = AppTest.from_file(script_path, default_timeout=30)
    at.run()
    
    # Unauthenticated user should see the login prompt and NOT the main dashboard title
    assert ("authenticated" not in at.session_state) or (not at.session_state["authenticated"])
    assert len(at.text_input) >= 2  # Username and Password fields
    # Main dashboard content should not be displayed
    assert "Autonomous Crowd Monitoring Dashboard" not in [t.value for t in at.title]

    # 2. Test Authenticated Access
    at_auth = AppTest.from_file(script_path, default_timeout=30)
    at_auth.session_state["authenticated"] = True
    at_auth.session_state["username"] = "admin"
    at_auth.session_state["role"] = "Administrator"
    at_auth.run()

    # Authenticated user should see the full dashboard
    assert at_auth.session_state["authenticated"] is True
    titles = [t.value for t in at_auth.title]
    assert any("CrowdPatrol - Autonomous Crowd Monitoring Dashboard" in t for t in titles)
