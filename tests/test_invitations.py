"""
CrowdPatrol 2.0 — Phase 2B.2 Member Invitation & Email Delivery Test Suite
Validates cryptographically secure token generation, SHA-256 hashed storage,
single-use atomic acceptance, role constraint enforcement, anti-escalation,
expiration handling, and concurrent acceptance safety.
"""

import os
import tempfile
import threading
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
import pytest

from src.auth.database import AuthDatabase, User, Organization, OrganizationMembership, OrganizationInvitation
from src.auth.service import AuthService
from src.auth.organization_service import OrganizationService, MembershipService
from src.auth.invitation_service import (
    InvitationService,
    normalize_email,
    generate_invitation_token,
    hash_invitation_token,
    send_invitation_email
)
from src.notification_dispatcher import NotificationConfig


@pytest.fixture
def temp_db():
    """Provides a fresh isolated SQLite database with schema version 3 applied."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    db = AuthDatabase(db_path)
    yield db
    try:
        os.remove(db_path)
    except OSError:
        pass


@pytest.fixture
def auth_service(temp_db):
    return AuthService(temp_db)


@pytest.fixture
def org_service(temp_db):
    return OrganizationService(temp_db)


@pytest.fixture
def member_service(temp_db):
    return MembershipService(temp_db)


@pytest.fixture
def invitation_service(temp_db, auth_service):
    return InvitationService(temp_db, auth_service)


@pytest.fixture
def platform_admin(auth_service):
    return auth_service.register_user(
        username="platform_admin",
        email="padmin@crowdpatrol.internal",
        password="ValidPassword123!",
        role="PLATFORM_ADMIN"
    )


@pytest.fixture
def org_admin(auth_service):
    return auth_service.register_user(
        username="sarah_admin",
        email="sarah@corp.internal",
        password="ValidPassword123!",
        role="USER"
    )


@pytest.fixture
def standard_operator(auth_service):
    return auth_service.register_user(
        username="dave_operator",
        email="dave@corp.internal",
        password="ValidPassword123!",
        role="USER"
    )


@pytest.fixture
def test_org(org_service, platform_admin, org_admin):
    return org_service.create_organization(
        name="Metro Transit Command",
        slug="metro-transit-command",
        actor=platform_admin,
        initial_admin_user_id=org_admin.id
    )


# =============================================================================
# 1. TOKEN GENERATION & HASHING TESTS
# =============================================================================

def test_token_generation_and_hashing():
    raw_token, token_hash = generate_invitation_token()
    assert len(raw_token) >= 32
    assert len(token_hash) == 64  # SHA-256 hex digest
    assert hash_invitation_token(raw_token) == token_hash
    # Ensure randomness
    raw_token2, token_hash2 = generate_invitation_token()
    assert raw_token != raw_token2
    assert token_hash != token_hash2


def test_normalize_email():
    assert normalize_email("  User.Name+Tag@Domain.COM  ") == "user.name+tag@domain.com"
    with pytest.raises(ValueError, match="cannot be empty"):
        normalize_email("")
    with pytest.raises(ValueError, match="Invalid email address format"):
        normalize_email("not-an-email")


# =============================================================================
# 2. INVITATION CREATION & CONSTRAINTS TESTS
# =============================================================================

def test_create_invitation_success(invitation_service, org_admin, test_org):
    """ORG_ADMIN can create an invitation; raw token is not stored in DB."""
    with patch("src.auth.invitation_service.send_invitation_email", return_value=(True, None)):
        invitation, raw_token, err = invitation_service.create_invitation(
            actor=org_admin,
            organization_id=test_org.id,
            email="recruit@metro.internal",
            role="OPERATOR",
            expires_in_hours=72,
            send_email=True
        )

    assert err is None
    assert invitation is not None
    assert invitation.normalized_email == "recruit@metro.internal"
    assert invitation.invited_role == "OPERATOR"
    assert invitation.status == "PENDING"
    assert invitation.token_hash == hash_invitation_token(raw_token)
    assert raw_token not in invitation.token_hash

    # Verify audit event emitted
    events = invitation_service.db.list_audit_events(test_org.id)
    actions = [e.action for e in events]
    assert "INVITATION_CREATED" in actions


def test_create_invitation_unauthorized_operator_denied(invitation_service, standard_operator, test_org, member_service, org_admin):
    """An OPERATOR cannot create invitations."""
    member_service.add_member(
        org_id=test_org.id,
        user_id=standard_operator.id,
        role="OPERATOR",
        actor=org_admin
    )
    with pytest.raises(PermissionError, match="Insufficient role"):
        invitation_service.create_invitation(
            actor=standard_operator,
            organization_id=test_org.id,
            email="newbie@metro.internal",
            role="VIEWER"
        )


def test_create_invitation_role_escalation_blocked(invitation_service, org_admin, test_org):
    """Cannot invite anyone with PLATFORM_ADMIN or SUPER_ADMIN role."""
    with pytest.raises(ValueError, match="Invalid invitation role"):
        invitation_service.create_invitation(
            actor=org_admin,
            organization_id=test_org.id,
            email="escalate@metro.internal",
            role="PLATFORM_ADMIN"
        )
    with pytest.raises(ValueError, match="Invalid invitation role"):
        invitation_service.create_invitation(
            actor=org_admin,
            organization_id=test_org.id,
            email="escalate@metro.internal",
            role="SUPER_ADMIN"
        )


def test_create_invitation_duplicate_pending_rejected(invitation_service, org_admin, test_org):
    """Cannot create two active pending invitations for the same org + email."""
    with patch("src.auth.invitation_service.send_invitation_email", return_value=(True, None)):
        invitation_service.create_invitation(
            actor=org_admin,
            organization_id=test_org.id,
            email="duplicate@metro.internal",
            role="VIEWER"
        )
        with pytest.raises(ValueError, match="pending invitation already exists"):
            invitation_service.create_invitation(
                actor=org_admin,
                organization_id=test_org.id,
                email="duplicate@metro.internal",
                role="OPERATOR"
            )


def test_create_invitation_already_active_member_rejected(invitation_service, org_admin, standard_operator, test_org, member_service):
    """Cannot invite a user who is already an active member."""
    member_service.add_member(
        org_id=test_org.id,
        user_id=standard_operator.id,
        role="OPERATOR",
        actor=org_admin
    )
    with pytest.raises(ValueError, match="already an active member"):
        invitation_service.create_invitation(
            actor=org_admin,
            organization_id=test_org.id,
            email=standard_operator.email,
            role="VIEWER"
        )


def test_revoke_invitation_success(invitation_service, org_admin, test_org):
    """ORG_ADMIN can revoke a pending invitation."""
    with patch("src.auth.invitation_service.send_invitation_email", return_value=(True, None)):
        inv, raw_token, _ = invitation_service.create_invitation(
            actor=org_admin,
            organization_id=test_org.id,
            email="revokeme@metro.internal",
            role="OPERATOR"
        )
    revoked = invitation_service.revoke_invitation(actor=org_admin, invitation_id=inv.id)
    assert revoked.status == "REVOKED"
    assert revoked.revoked_at is not None

    # Validating revoked token returns error
    _, _, err = invitation_service.validate_invitation_token(raw_token)
    assert "revoked" in err.lower()


# =============================================================================
# 3. INVITATION ACCEPTANCE & TOKEN VALIDATION TESTS
# =============================================================================

def test_validate_token_expired(invitation_service, org_admin, test_org):
    """Expired invitation is detected and auto-updated to EXPIRED."""
    with patch("src.auth.invitation_service.send_invitation_email", return_value=(True, None)):
        inv, raw_token, _ = invitation_service.create_invitation(
            actor=org_admin,
            organization_id=test_org.id,
            email="expired@metro.internal",
            role="OPERATOR",
            expires_in_hours=1
        )
    # Manually backdate expiration in DB
    past_iso = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    with invitation_service.db.transaction() as cur:
        cur.execute("UPDATE organization_invitations SET expires_at = ? WHERE id = ?;", (past_iso, inv.id))

    _, _, err = invitation_service.validate_invitation_token(raw_token)
    assert "expired" in err.lower()

    # Verify status transitioned to EXPIRED in database
    refetched = invitation_service.db.get_invitation_by_id(inv.id)
    assert refetched.status == "EXPIRED"


def test_accept_invitation_existing_user_success(invitation_service, org_admin, test_org, auth_service):
    """Existing registered user with matching email accepts and receives membership."""
    target_user = auth_service.register_user(
        username="existing_hire",
        email="hire@metro.internal",
        password="ValidPassword123!",
        role="USER"
    )
    with patch("src.auth.invitation_service.send_invitation_email", return_value=(True, None)):
        inv, raw_token, _ = invitation_service.create_invitation(
            actor=org_admin,
            organization_id=test_org.id,
            email="hire@metro.internal",
            role="OPERATOR"
        )

    success, membership, err = invitation_service.accept_invitation(
        raw_token=raw_token,
        user=target_user
    )
    assert success is True
    assert err == ""
    assert membership is not None
    assert membership.user_id == target_user.id
    assert membership.role == "OPERATOR"
    assert membership.status == "ACTIVE"

    # Single-use check: Trying to accept again fails
    success2, _, err2 = invitation_service.accept_invitation(raw_token=raw_token, user=target_user)
    assert success2 is False
    assert "already been accepted" in err2


def test_accept_invitation_email_mismatch_rejected(invitation_service, org_admin, test_org, auth_service):
    """Logged in user with different email is rejected."""
    wrong_user = auth_service.register_user(
        username="wrong_user",
        email="wrong@other.internal",
        password="ValidPassword123!",
        role="USER"
    )
    with patch("src.auth.invitation_service.send_invitation_email", return_value=(True, None)):
        _, raw_token, _ = invitation_service.create_invitation(
            actor=org_admin,
            organization_id=test_org.id,
            email="target@metro.internal",
            role="OPERATOR"
        )

    success, _, err = invitation_service.accept_invitation(raw_token=raw_token, user=wrong_user)
    assert success is False
    assert "does not match invitation recipient" in err


def test_accept_invitation_new_user_registration_success(invitation_service, org_admin, test_org, auth_service):
    """New user without an account registers credentials during acceptance."""
    with patch("src.auth.invitation_service.send_invitation_email", return_value=(True, None)):
        _, raw_token, _ = invitation_service.create_invitation(
            actor=org_admin,
            organization_id=test_org.id,
            email="brand_new_recruit@metro.internal",
            role="VIEWER"
        )

    success, membership, err = invitation_service.accept_invitation(
        raw_token=raw_token,
        new_user_credentials={
            "username": "brand_new_recruit",
            "password": "StrongPassword2026!"
        }
    )
    assert success is True
    assert err == ""
    assert membership is not None
    assert membership.role == "VIEWER"

    # Verify newly created user in database
    created_user = auth_service.db.get_user_by_identity("brand_new_recruit")
    assert created_user is not None
    assert created_user.email == "brand_new_recruit@metro.internal"

    # Authenticate new user to confirm password hashing works
    authed_user, sess_token, auth_err = auth_service.authenticate("brand_new_recruit", "StrongPassword2026!")
    assert auth_err is None
    assert authed_user.id == created_user.id


def test_concurrent_invitation_acceptance_single_use_guaranteed(invitation_service, org_admin, test_org, auth_service):
    """
    Stress-test concurrent acceptance of the exact same invitation token.
    Exactly 1 thread MUST succeed, and all competing threads MUST be rejected.
    """
    target_user = auth_service.register_user(
        username="race_target",
        email="race@metro.internal",
        password="ValidPassword123!",
        role="USER"
    )
    with patch("src.auth.invitation_service.send_invitation_email", return_value=(True, None)):
        _, raw_token, _ = invitation_service.create_invitation(
            actor=org_admin,
            organization_id=test_org.id,
            email="race@metro.internal",
            role="OPERATOR"
        )

    results = []
    barrier = threading.Barrier(5)

    def attempt_accept():
        barrier.wait()
        success, mem, err = invitation_service.accept_invitation(raw_token=raw_token, user=target_user)
        results.append(success)

    threads = [threading.Thread(target=attempt_accept) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Exactly one thread succeeds
    assert results.count(True) == 1
    assert results.count(False) == 4

    # Organization has exactly 1 membership for this user
    members = invitation_service.db.list_user_memberships(target_user.id)
    assert len(members) == 1


# =============================================================================
# 4. EMAIL DELIVERY ERROR CAPTURE & MOCKING TESTS
# =============================================================================

def test_invitation_email_delivery_failure_handling(invitation_service, org_admin, test_org):
    """When SMTP delivery fails, invitation is still created and error is captured cleanly without leaking token."""
    with patch("src.auth.invitation_service.send_invitation_email", return_value=(False, "Connection refused")):
        inv, raw_token, err = invitation_service.create_invitation(
            actor=org_admin,
            organization_id=test_org.id,
            email="smtp_fail@metro.internal",
            role="OPERATOR",
            send_email=True
        )

    assert inv is not None
    assert inv.status == "PENDING"
    assert err == "Connection refused"
    assert raw_token not in err
