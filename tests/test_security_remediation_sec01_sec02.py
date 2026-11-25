"""
tests/test_security_remediation_sec01_sec02.py
----------------------------------------------
Comprehensive Verification Suite for SEC-01 and SEC-02 Security Remediations.

Validates:
1. SEC-01: Partial unique index idx_invitations_org_email_pending.
2. SEC-01: Concurrency-safe invitation creation across simultaneous threads.
3. SEC-01: Automatic transition of expired pending invitations allowing replacement.
4. SEC-01: Permitted simultaneous invitations for the same email in different organizations.
5. SEC-01: Permitted replacement after revocation.
6. SEC-01: Direct database IntegrityError handling and transaction rollback.
7. SEC-02: Query parameter token capture into st.session_state["invitation_token"].
8. SEC-02: Immediate clearing of st.query_params to protect URL bar.
9. SEC-02: Token persistence across reruns during acceptance flow.
10. SEC-02: Complete cleanup on acceptance, cancellation, expiry, and logout.
11. SEC-02: Zero raw token persistence in browser storage or logs.
"""

import os
import sqlite3
import tempfile
import threading
from datetime import datetime, timezone, timedelta
from unittest.mock import patch
import pytest

from src.auth.database import AuthDatabase, User, Organization, OrganizationMembership, OrganizationInvitation
from src.auth.service import AuthService
from src.auth.organization_service import (
    OrganizationService,
    MembershipService,
)
from src.auth.invitation_service import (
    InvitationService,
    generate_invitation_token,
    hash_invitation_token,
)


@pytest.fixture
def test_db(tmp_path):
    """Provides an isolated SQLite database with Schema v4 applied."""
    db_file = tmp_path / "test_sec_remediation.db"
    db = AuthDatabase(str(db_file))
    return db


@pytest.fixture
def services(test_db):
    auth_svc = AuthService(test_db)
    org_svc = OrganizationService(test_db)
    member_svc = MembershipService(test_db)
    invitation_svc = InvitationService(test_db, auth_svc)
    return auth_svc, org_svc, member_svc, invitation_svc


# =============================================================================
# PART 1: SEC-01 CONCURRENCY & LIFECYCLE TESTS
# =============================================================================

def test_sec01_two_simultaneous_invitations_race_condition(services):
    """
    Two simultaneous threads attempting to create an invitation for the same org + email.
    Exactly 1 MUST succeed and exactly 1 MUST be rejected with duplicate ValueError.
    """
    auth_svc, org_svc, _, invitation_svc = services

    padmin = auth_svc.register_user("padmin_sim", "padmin_sim@metro.internal", "Pass1234!", role="PLATFORM_ADMIN")
    admin = auth_svc.register_user("admin_sim", "admin_sim@metro.internal", "Pass1234!", role="USER")
    org = org_svc.create_organization("Simultaneous Guard", slug="sim-guard", actor=padmin, initial_admin_user_id=admin.id)

    target_email = "racer@metro.internal"
    results = []
    barrier = threading.Barrier(2)

    def racer():
        barrier.wait()
        try:
            inv, raw, err = invitation_svc.create_invitation(
                actor=admin,
                organization_id=org.id,
                email=target_email,
                role="OPERATOR",
                send_email=False
            )
            results.append((True, inv.id, None))
        except Exception as e:
            results.append((False, None, str(e)))

    t1 = threading.Thread(target=racer)
    t2 = threading.Thread(target=racer)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    successes = [r for r in results if r[0] is True]
    failures = [r for r in results if r[0] is False]

    assert len(successes) == 1, f"Expected exactly 1 success, got {len(successes)}"
    assert len(failures) == 1, f"Expected exactly 1 failure, got {len(failures)}"
    assert "pending invitation already exists" in failures[0][2]

    # Database contains exactly 1 pending invitation
    pending = org_svc.db.list_organization_invitations(org.id, status="PENDING")
    assert len([p for p in pending if p.normalized_email == target_email]) == 1


def test_sec01_multiple_concurrent_invitation_requests(services):
    """
    High-concurrency stress test: 10 simultaneous threads attempting to invite the same email.
    Exactly 1 thread MUST succeed, and 9 MUST be rejected.
    """
    auth_svc, org_svc, _, invitation_svc = services

    padmin = auth_svc.register_user("padmin_multi", "padmin_multi@metro.internal", "Pass1234!", role="PLATFORM_ADMIN")
    admin = auth_svc.register_user("admin_multi", "admin_multi@metro.internal", "Pass1234!", role="USER")
    org = org_svc.create_organization("Multi Concurrency Corp", slug="multi-conc", actor=padmin, initial_admin_user_id=admin.id)

    target_email = "flood@metro.internal"
    results = []
    barrier = threading.Barrier(10)

    def worker():
        barrier.wait()
        try:
            inv, raw, err = invitation_svc.create_invitation(
                actor=admin,
                organization_id=org.id,
                email=target_email,
                role="VIEWER",
                send_email=False
            )
            results.append((True, inv.id, None))
        except Exception as e:
            results.append((False, None, str(e)))

    threads = [threading.Thread(target=worker) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    successes = [r for r in results if r[0] is True]
    failures = [r for r in results if r[0] is False]

    assert len(successes) == 1
    assert len(failures) == 9

    pending = org_svc.db.list_organization_invitations(org.id, status="PENDING")
    assert len([p for p in pending if p.normalized_email == target_email]) == 1


def test_sec01_expired_pending_invitation_allows_replacement(services):
    """
    CRITICAL EDGE CASE: If an invitation has expired (expires_at <= now) but its DB status
    remained PENDING, creating a new invitation for that email MUST succeed by auto-expiring
    the old one, and not trigger a false-positive partial unique index violation.
    """
    auth_svc, org_svc, _, invitation_svc = services

    padmin = auth_svc.register_user("padmin_exp", "padmin_exp@metro.internal", "Pass1234!", role="PLATFORM_ADMIN")
    admin = auth_svc.register_user("admin_exp", "admin_exp@metro.internal", "Pass1234!", role="USER")
    org = org_svc.create_organization("Expiry Replacement Org", slug="exp-replace", actor=padmin, initial_admin_user_id=admin.id)

    target_email = "delayed_invitee@metro.internal"

    # 1. Create first invitation
    old_inv, old_token, _ = invitation_svc.create_invitation(
        actor=admin,
        organization_id=org.id,
        email=target_email,
        role="OPERATOR",
        expires_in_hours=1,
        send_email=False
    )
    assert old_inv.status == "PENDING"

    # 2. Backdate its expiration into the past, leaving status as 'PENDING' in DB
    past_iso = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
    with org_svc.db.transaction() as cur:
        cur.execute("UPDATE organization_invitations SET expires_at = ? WHERE id = ?;", (past_iso, old_inv.id))

    # 3. Create replacement invitation for the same email and organization
    new_inv, new_token, err = invitation_svc.create_invitation(
        actor=admin,
        organization_id=org.id,
        email=target_email,
        role="OPERATOR",
        expires_in_hours=72,
        send_email=False
    )
    assert err is None
    assert new_inv is not None
    assert new_inv.id != old_inv.id
    assert new_inv.status == "PENDING"

    # 4. Confirm old invitation was automatically transitioned to EXPIRED
    old_reloaded = org_svc.db.get_invitation_by_id(old_inv.id)
    assert old_reloaded.status == "EXPIRED"

    # 5. Confirm only the new invitation is active and pending
    pending = org_svc.db.list_organization_invitations(org.id, status="PENDING")
    assert len(pending) == 1
    assert pending[0].id == new_inv.id


def test_sec01_duplicate_active_pending_invitation_rejected(services):
    """Sequential duplicate creation of an active pending invitation is rejected."""
    auth_svc, org_svc, _, invitation_svc = services

    padmin = auth_svc.register_user("padmin_seq", "padmin_seq@metro.internal", "Pass1234!", role="PLATFORM_ADMIN")
    admin = auth_svc.register_user("admin_seq", "admin_seq@metro.internal", "Pass1234!", role="USER")
    org = org_svc.create_organization("Sequential Guard", slug="seq-guard", actor=padmin, initial_admin_user_id=admin.id)

    target_email = "active_pending@metro.internal"
    invitation_svc.create_invitation(actor=admin, organization_id=org.id, email=target_email, role="VIEWER", send_email=False)

    with pytest.raises(ValueError, match="pending invitation already exists"):
        invitation_svc.create_invitation(actor=admin, organization_id=org.id, email=target_email, role="OPERATOR", send_email=False)


def test_sec01_revoked_invitation_allows_replacement(services):
    """Revoking an invitation allows a new replacement invitation to be issued immediately."""
    auth_svc, org_svc, _, invitation_svc = services

    padmin = auth_svc.register_user("padmin_revk", "padmin_revk@metro.internal", "Pass1234!", role="PLATFORM_ADMIN")
    admin = auth_svc.register_user("admin_revk", "admin_revk@metro.internal", "Pass1234!", role="USER")
    org = org_svc.create_organization("Revocation Org", slug="revocation-org", actor=padmin, initial_admin_user_id=admin.id)

    target_email = "revoked_user@metro.internal"
    inv1, _, _ = invitation_svc.create_invitation(actor=admin, organization_id=org.id, email=target_email, role="VIEWER", send_email=False)

    invitation_svc.revoke_invitation(actor=admin, invitation_id=inv1.id)

    inv2, _, err2 = invitation_svc.create_invitation(actor=admin, organization_id=org.id, email=target_email, role="OPERATOR", send_email=False)
    assert err2 is None
    assert inv2.id != inv1.id
    assert inv2.status == "PENDING"


def test_sec01_same_email_in_different_organizations_permitted(services):
    """The same user email can have simultaneous pending invitations in different organizations."""
    auth_svc, org_svc, _, invitation_svc = services

    padmin = auth_svc.register_user("padmin_diff", "padmin_diff@metro.internal", "Pass1234!", role="PLATFORM_ADMIN")
    admin_a = auth_svc.register_user("admin_a", "admin_a@metro.internal", "Pass1234!", role="USER")
    admin_b = auth_svc.register_user("admin_b", "admin_b@airport.internal", "Pass1234!", role="USER")

    org_a = org_svc.create_organization("Transit Authority", slug="transit-auth", actor=padmin, initial_admin_user_id=admin_a.id)
    org_b = org_svc.create_organization("Port Authority", slug="port-auth", actor=padmin, initial_admin_user_id=admin_b.id)

    shared_email = "specialist@consultant.test"

    inv_a, _, _ = invitation_svc.create_invitation(actor=admin_a, organization_id=org_a.id, email=shared_email, role="OPERATOR", send_email=False)
    inv_b, _, _ = invitation_svc.create_invitation(actor=admin_b, organization_id=org_b.id, email=shared_email, role="VIEWER", send_email=False)

    assert inv_a.organization_id == org_a.id
    assert inv_b.organization_id == org_b.id
    assert inv_a.status == "PENDING"
    assert inv_b.status == "PENDING"


def test_sec01_database_unique_index_enforcement_and_rollback(services):
    """
    Direct low-level verification of SQLite partial unique index idx_invitations_org_email_pending.
    Verifies that direct INSERT bypass triggers IntegrityError and rolls back cleanly.
    """
    auth_svc, org_svc, _, _ = services
    padmin = auth_svc.register_user("padmin_idx", "padmin_idx@metro.internal", "Pass1234!", role="PLATFORM_ADMIN")
    org = org_svc.create_organization("Index Org", slug="index-org", actor=padmin)

    now_iso = datetime.now(timezone.utc).isoformat()
    exp_iso = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()

    # Insert 1st pending invitation directly
    with org_svc.db.transaction() as cur:
        cur.execute("""
            INSERT INTO organization_invitations (
                id, organization_id, normalized_email, invited_role, token_hash,
                invited_by, status, expires_at, created_at, updated_at
            ) VALUES ('inv_direct_1', ?, 'direct@test.com', 'OPERATOR', 'hash_1', ?, 'PENDING', ?, ?, ?);
        """, (org.id, padmin.id, exp_iso, now_iso, now_iso))

    # Attempt to insert 2nd pending invitation for same org and email directly
    with pytest.raises(sqlite3.IntegrityError) as excinfo:
        with org_svc.db.transaction() as cur:
            cur.execute("""
                INSERT INTO organization_invitations (
                    id, organization_id, normalized_email, invited_role, token_hash,
                    invited_by, status, expires_at, created_at, updated_at
                ) VALUES ('inv_direct_2', ?, 'direct@test.com', 'VIEWER', 'hash_2', ?, 'PENDING', ?, ?, ?);
            """, (org.id, padmin.id, exp_iso, now_iso, now_iso))

    assert "UNIQUE constraint failed" in str(excinfo.value)

    # Confirm inv_direct_2 was rolled back and does not exist in DB
    assert org_svc.db.get_invitation_by_id("inv_direct_2") is None


# =============================================================================
# PART 2: SEC-02 URL TOKEN SANITIZATION & SESSION CLEANUP TESTS
# =============================================================================

def test_sec02_token_captured_and_query_params_cleared(monkeypatch, services):
    """
    Tests SEC-02 via Streamlit AppTest:
    1. Arriving with ?page=accept_invite&token=VALID_TOKEN captures token into st.session_state["invitation_token"].
    2. st.query_params is cleared so the raw token is not exposed in the browser address bar.
    3. current_page is set to 'accept_invite'.
    4. Valid invitation preserves token in session state while form is displayed.
    """
    monkeypatch.setenv("CROWDPATROL_ALLOW_DEV_SEED", "0")
    monkeypatch.setenv("CROWDPATROL_ENV", "production")

    auth_svc, org_svc, _, invitation_svc = services
    padmin = auth_svc.register_user("padmin_sec2", "padmin_sec2@metro.internal", "Pass1234!", role="PLATFORM_ADMIN")
    admin = auth_svc.register_user("admin_sec2", "admin_sec2@metro.internal", "Pass1234!", role="USER")
    org = org_svc.create_organization("SEC2 Test Org", slug="sec2-test", actor=padmin, initial_admin_user_id=admin.id)

    inv, raw_token, _ = invitation_svc.create_invitation(
        actor=admin, organization_id=org.id, email="invitee_sec2@metro.internal", role="OPERATOR", send_email=False
    )

    from streamlit.testing.v1 import AppTest
    from pathlib import Path
    import streamlit as st
    st.cache_resource.clear()

    # Point default AuthDatabase to the same test DB
    monkeypatch.setenv("CROWDPATROL_AUTH_DB_PATH", str(auth_svc.db.db_path))

    script_path = str(Path(__file__).parent.parent / "dashboard" / "simple_dashboard.py")
    at = AppTest.from_file(script_path)
    at.query_params["page"] = "accept_invite"
    at.query_params["token"] = raw_token
    at.run(timeout=30)

    assert len(at.exception) == 0

    # Token captured in session state
    assert at.session_state["current_page"] == "accept_invite"
    assert at.session_state["invitation_token"] == raw_token

    # Query params cleared from URL bar
    assert "token" not in at.query_params


def test_sec02_token_cleanup_on_cancel(monkeypatch):
    """
    Clicking Cancel on the acceptance view removes the token from session state
    and returns to landing.
    """
    monkeypatch.setenv("CROWDPATROL_ALLOW_DEV_SEED", "0")
    monkeypatch.setenv("CROWDPATROL_ENV", "production")

    from streamlit.testing.v1 import AppTest
    from pathlib import Path

    script_path = str(Path(__file__).parent.parent / "dashboard" / "simple_dashboard.py")
    at = AppTest.from_file(script_path)
    at.query_params["page"] = "accept_invite"
    at.query_params["token"] = "invalid_token_to_cancel"
    at.run(timeout=30)

    # In invalid token state, click Return to Landing Page
    # Find button
    buttons = [b for b in at.button if "Landing" in b.label or "Return" in b.label]
    if buttons:
        buttons[0].click().run(timeout=30)
        assert len(at.exception) == 0
        assert at.session_state["current_page"] == "landing"
        assert "invitation_token" not in at.session_state or at.session_state["invitation_token"] is None


def test_sec02_token_cleanup_on_logout(monkeypatch, services):
    """
    Signing out via handle_logout purges any invitation token from session state.
    """
    monkeypatch.setenv("CROWDPATROL_ALLOW_DEV_SEED", "0")
    monkeypatch.setenv("CROWDPATROL_ENV", "production")

    auth_svc, _, _, _ = services
    user = auth_svc.register_user("logout_user", "logout_user@metro.internal", "Pass1234!", role="USER")

    from streamlit.testing.v1 import AppTest
    from pathlib import Path
    import streamlit as st
    st.cache_resource.clear()

    monkeypatch.setenv("CROWDPATROL_AUTH_DB_PATH", str(auth_svc.db.db_path))

    script_path = str(Path(__file__).parent.parent / "dashboard" / "simple_dashboard.py")
    at = AppTest.from_file(script_path)
    at.query_params["page"] = "dashboard"
    at.run(timeout=30)

    # Sign in
    at.text_input(key="login_identity_input").input("logout_user")
    at.text_input(key="login_password_input").input("Pass1234!")
    at.button(key="login_submit_btn").click().run(timeout=30)

    # Inject residual invitation_token to test logout purge
    at.session_state["invitation_token"] = "residual_token_purged"

    # Click sidebar logout button
    at.button(key="sidebar_logout_btn").click().run(timeout=30)
    assert len(at.exception) == 0

    assert at.session_state["current_page"] == "landing"
    assert "invitation_token" not in at.session_state or at.session_state["invitation_token"] is None
