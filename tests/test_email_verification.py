"""
Verification tests for the email verification OTP flow during sign-up.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.notification_dispatcher import NotificationDispatcher, NotificationConfig
from src.demo_auth import init_auth_db, register_user, authenticate_user


def test_send_verification_code_email(tmp_path):
    """Verify that send_verification_code_email formats subject and transmits OTP code."""
    mock_email_service = MagicMock()
    config = NotificationConfig(
        smtp_host="smtp.gmail.com",
        smtp_port=587,
        smtp_username="shreyaskeyboardtutorials@gmail.com",
        smtp_password="dummy_password",
        email_sender="shreyaskeyboardtutorials@gmail.com",
        email_recipients=["shreyaskeyboardtutorials@gmail.com"],
        enabled=True
    )
    dispatcher = NotificationDispatcher(config=config, email_service=mock_email_service, autostart_worker=False)

    target_email = "new_security_officer@metropark.org"
    code = "749201"

    ok, msg = dispatcher.send_verification_code_email(target_email, code, username="Officer_Miller")
    assert ok is True
    assert "successfully sent" in msg

    mock_email_service.send_email.assert_called_once()
    args, kwargs = mock_email_service.send_email.call_args
    subject, html_body, text_body = args[0], args[1], args[2]
    recipients = kwargs.get("recipients")

    assert "749201" in subject
    assert "749201" in text_body
    assert "749201" in html_body
    assert recipients == [target_email]


def test_verified_signup_flow(tmp_path):
    """Verify that after code confirmation, user is registered and can authenticate."""
    test_db = tmp_path / "signup_verification.db"
    init_auth_db(test_db)

    # Simulated verified OTP confirmation
    email = "verified_analyst@police.gov"
    username = "analyst_sam"
    password = "StrongPassword2026!"

    ok, msg, new_user = register_user(username, email, password, role="Operator", db_path=test_db)
    assert ok is True
    assert new_user["email"] == email

    # Can sign in using either username or verified email
    u_by_name = authenticate_user(username, password, db_path=test_db)
    assert u_by_name is not None
    assert u_by_name["email"] == email

    u_by_email = authenticate_user(email, password, db_path=test_db)
    assert u_by_email is not None
    assert u_by_email["username"] == username
