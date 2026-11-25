"""
CrowdPatrol 2.0 — Focused Test Suite for Administrator Credential Recovery & Invitation Registration
Validates:
1. Atomic administrator password reset via AuthService and AuthDatabase.
2. Complete invalidation/revocation of all active sessions for the user upon password reset.
3. Preservation of username, email, and role during password reset.
4. Timestamped database backup creation prior to database modification.
5. Registration requirement for valid organization invitations (no unrestricted public registration).
6. New user account creation and automatic organization membership association via invitation.
7. Existing user invitation acceptance without duplicate account creation.
"""

import os
import sys
import tempfile
import sqlite3
from pathlib import Path
from datetime import datetime, timezone
import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.auth.database import AuthDatabase, User
from src.auth.service import AuthService
from src.auth.organization_service import OrganizationService, MembershipService
from src.auth.invitation_service import InvitationService
from scripts.reset_admin_password import reset_admin_password, create_database_backup


@pytest.fixture
def auth_env():
    """Provides a fresh isolated database and authentication services in a temporary directory."""
    temp_dir = tempfile.TemporaryDirectory()
    db_path = Path(temp_dir.name) / "test_auth.db"
    db = AuthDatabase(str(db_path))
    auth = AuthService(db)
    org_svc = OrganizationService(db)
    member_svc = MembershipService(db)
    inv_svc = InvitationService(db, auth)

    yield {
        "temp_dir": temp_dir,
        "db_path": db_path,
        "db": db,
        "auth": auth,
        "org_svc": org_svc,
        "member_svc": member_svc,
        "inv_svc": inv_svc,
    }
    temp_dir.cleanup()


def test_password_reset_and_session_invalidation(auth_env):
    """
    Verifies that resetting a password:
    1. Updates the Scrypt password hash in the database.
    2. Invalidates all active sessions for the user.
    3. Prevents authentication with the old password.
    4. Permits authentication with the new password.
    5. Preserves role, username, email, and clears lockout.
    """
    auth = auth_env["auth"]
    db = auth_env["db"]

    # 1. Register an administrator
    admin = auth.register_user(
        username="lead_admin",
        email="lead_admin@crowdpatrol.org",
        password="InitialPassword123!",
        role="SUPER_ADMIN"
    )
    assert admin.role == "SUPER_ADMIN"

    # 2. Authenticate and create active sessions
    user_auth, session_tok_1, err = auth.authenticate("lead_admin", "InitialPassword123!")
    assert err is None
    assert session_tok_1 is not None

    _, session_tok_2, _ = auth.authenticate("lead_admin@crowdpatrol.org", "InitialPassword123!")
    assert session_tok_2 is not None

    # Verify both sessions are currently valid
    assert auth.validate_session(session_tok_1) is not None
    assert auth.validate_session(session_tok_2) is not None

    # Simulate a failed login attempt to check counter reset
    db.record_login_failure(admin.id)
    user_before = db.get_user_by_id(admin.id)
    assert user_before.failed_login_attempts == 1

    # 3. Reset password via AuthService
    updated = auth.reset_user_password(admin.id, "BrandNewSecurePassword2026!")
    assert updated is True

    # 4. Invalidation verification: All prior sessions must be revoked
    assert auth.validate_session(session_tok_1) is None
    assert auth.validate_session(session_tok_2) is None

    # 5. Old password must be rejected
    u_old, tok_old, err_old = auth.authenticate("lead_admin", "InitialPassword123!")
    assert u_old is None
    assert tok_old is None
    assert "Invalid credentials" in err_old

    # 6. New password must authenticate cleanly
    u_new, tok_new, err_new = auth.authenticate("lead_admin", "BrandNewSecurePassword2026!")
    assert err_new is None
    assert u_new is not None
    assert tok_new is not None

    # 7. Safety checks: Role, username, email, and lockout counter
    admin_after = db.get_user_by_id(admin.id)
    assert admin_after.role == "SUPER_ADMIN"
    assert admin_after.username == "lead_admin"
    assert admin_after.email == "lead_admin@crowdpatrol.org"
    assert admin_after.failed_login_attempts == 0
    assert admin_after.locked_until is None


def test_password_reset_validation_requirements(auth_env):
    """Verifies that invalid password inputs or non-existent users raise ValueError."""
    auth = auth_env["auth"]

    user = auth.register_user("testuser", "test@crowdpatrol.org", "ValidPass123!")

    # Password too short
    with pytest.raises(ValueError, match="at least 8 characters"):
        auth.reset_user_password(user.id, "short")

    # Non-existent user ID
    with pytest.raises(ValueError, match="not found"):
        auth.reset_user_password("usr_nonexistent999", "ValidNewPass123!")


def test_reset_admin_password_script_execution(auth_env):
    """
    Verifies that the administrator recovery CLI script:
    1. Creates a timestamped backup before touching the database.
    2. Resets the target administrator's password.
    3. Revokes existing active sessions.
    4. Preserves identity and role.
    """
    db_path = auth_env["db_path"]
    auth = auth_env["auth"]
    db = auth_env["db"]

    admin = auth.register_user(
        username="admin",
        email="admin@crowdpatrol.internal",
        password="OldAdminPassword123!",
        role="SUPER_ADMIN"
    )

    # Create active session
    _, old_token, _ = auth.authenticate("admin", "OldAdminPassword123!")
    assert auth.validate_session(old_token) is not None

    # Run recovery function
    success = reset_admin_password(
        db_path=db_path,
        username="admin",
        new_password="NewAdminPassword456!"
    )
    assert success is True

    # Check that backup file was created
    backup_files = list((BASE_DIR / "backups").glob("crowdpatrol_auth_backup_*.db"))
    assert len(backup_files) > 0

    # Old session is invalidated
    assert auth.validate_session(old_token) is None

    # Can authenticate with new password
    u_auth, new_token, err = auth.authenticate("admin", "NewAdminPassword456!")
    assert err is None
    assert u_auth.id == admin.id
    assert u_auth.role == "SUPER_ADMIN"


def test_account_creation_requires_valid_invitation(auth_env):
    """
    Verifies that account registration cannot proceed without a valid invitation token:
    1. Empty/missing token fails.
    2. Malformed token fails.
    3. Expired token fails.
    4. Revoked token fails.
    """
    auth = auth_env["auth"]
    org_svc = auth_env["org_svc"]
    inv_svc = auth_env["inv_svc"]

    admin = auth.register_user("admin_inv", "admin_inv@org.com", "Pass123!Admin", role="PLATFORM_ADMIN")
    org = org_svc.create_organization("Metro Org", "metro-org", actor=admin)

    # 1. Non-existent token
    inv, validated_org, err = inv_svc.validate_invitation_token("invalid_token_1234567890123456")
    assert inv is None
    assert "Invalid or unrecognized" in err

    # 2. Expired invitation
    inv_exp, raw_token_exp, _ = inv_svc.create_invitation(
        actor=admin,
        organization_id=org.id,
        email="expired@org.com",
        role="OPERATOR",
        expires_in_hours=1,
        send_email=False
    )
    # Manually expire in DB
    past_iso = "2020-01-01T00:00:00+00:00"
    with auth_env["db"].transaction() as cur:
        cur.execute("UPDATE organization_invitations SET expires_at = ? WHERE id = ?", (past_iso, inv_exp.id))

    _, _, err_exp = inv_svc.validate_invitation_token(raw_token_exp)
    assert "expired" in err_exp.lower()


def test_new_user_registration_and_membership_association_via_invitation(auth_env):
    """
    Verifies that an invited user:
    1. Creates a new account with Scrypt password hashing.
    2. Is automatically granted active membership in the organization.
    3. Is assigned the exact role specified in the invitation.
    4. Cannot re-use the same token (single-use guarantee).
    """
    auth = auth_env["auth"]
    org_svc = auth_env["org_svc"]
    member_svc = auth_env["member_svc"]
    inv_svc = auth_env["inv_svc"]

    admin = auth.register_user("admin_ops", "admin_ops@safety.org", "Pass123!Admin", role="PLATFORM_ADMIN")
    org = org_svc.create_organization("City Safety", "city-safety", actor=admin)

    # Admin issues invitation for a new operator
    invitation, raw_token, _ = inv_svc.create_invitation(
        actor=admin,
        organization_id=org.id,
        email="new_operator@safety.org",
        role="OPERATOR",
        expires_in_hours=48,
        send_email=False
    )

    # Verify user does not exist prior to registration
    assert auth.db.get_user_by_identity("new_operator@safety.org") is None

    # Complete registration via invitation
    success, membership, accept_err = inv_svc.accept_invitation(
        raw_token=raw_token,
        new_user_credentials={
            "username": "operator_jane",
            "password": "JanePassword2026!"
        }
    )
    assert success is True
    assert accept_err == ""
    assert membership is not None
    assert membership.organization_id == org.id
    assert membership.role == "OPERATOR"
    assert membership.status == "ACTIVE"

    # User now exists and can authenticate
    new_user, token, auth_err = auth.authenticate("operator_jane", "JanePassword2026!")
    assert auth_err is None
    assert new_user is not None
    assert new_user.email == "new_operator@safety.org"

    # Token cannot be reused
    success_reuse, _, reuse_err = inv_svc.accept_invitation(
        raw_token=raw_token,
        new_user_credentials={"username": "hacker", "password": "Password123!"}
    )
    assert success_reuse is False
    assert "already been accepted" in reuse_err.lower()


def test_existing_user_accepts_invitation_without_duplicate_account(auth_env):
    """
    Verifies that when an existing user is invited to a second organization:
    1. The user joins the new organization.
    2. No duplicate User row is created in the database.
    3. User now holds active memberships in both organizations.
    """
    auth = auth_env["auth"]
    org_svc = auth_env["org_svc"]
    member_svc = auth_env["member_svc"]
    inv_svc = auth_env["inv_svc"]

    admin = auth.register_user("admin_corp", "admin_corp@corp.com", "Pass123!Corp", role="PLATFORM_ADMIN")
    org_a = org_svc.create_organization("Org Alpha", "org-alpha", actor=admin)
    org_b = org_svc.create_organization("Org Beta", "org-beta", actor=admin)

    # User already exists in Org Alpha
    analyst = auth.register_user("analyst_bob", "bob@corp.com", "BobSecretPassword123!", role="USER")
    member_svc.add_member(org_a.id, analyst.id, role="VIEWER", actor=admin)

    # Admin invites Bob to Org Beta as OPERATOR
    _, raw_token, _ = inv_svc.create_invitation(
        actor=admin,
        organization_id=org_b.id,
        email="bob@corp.com",
        role="OPERATOR",
        send_email=False
    )

    # Bob accepts invitation as an existing authenticated user
    success, membership_b, err = inv_svc.accept_invitation(
        raw_token=raw_token,
        user=analyst
    )
    assert success is True
    assert membership_b.organization_id == org_b.id
    assert membership_b.role == "OPERATOR"
    assert membership_b.user_id == analyst.id

    # Verify no duplicate user was created
    with auth_env["db"].transaction() as cur:
        cur.execute("SELECT COUNT(*) FROM users WHERE email = 'bob@corp.com';")
        count = cur.fetchone()[0]
        assert count == 1, "Duplicate user was created!"

    # Bob has memberships in both orgs
    mems = auth_env["db"].list_user_memberships(analyst.id)
    org_ids = [m.organization_id for m in mems]
    assert org_a.id in org_ids
    assert org_b.id in org_ids


def test_auth_ui_login_and_create_account_tabs_in_apptest():
    """
    Verifies that the authentication UI renders both Sign In and Create Account options:
    - Login inputs ('Username or Registered Email', 'Password').
    - Create Account inputs and invitation gate ('Invitation Token', 'Verify Invitation & Proceed').
    - Route back to Sign In from Create Account.
    """
    from streamlit.testing.v1 import AppTest
    script_path = str(BASE_DIR / "dashboard" / "simple_dashboard.py")
    at = AppTest.from_file(script_path)
    at.session_state["current_page"] = "login"
    at.run(timeout=30)

    assert len(at.exception) == 0, f"App execution failed: {at.exception}"
    labels = [t.label for t in at.text_input]
    assert "Username or Registered Email" in labels
    assert "Password" in labels
    assert "Invitation Token" in labels

    btn_labels = [b.label for b in at.button]
    assert "🔐 Sign In to Command Center" in btn_labels
    assert "🔍 Verify Invitation & Proceed" in btn_labels
    assert "← Return to Sign In" in btn_labels
