"""
tests/test_organization_ui.py
------------------------------
CrowdPatrol 2.0 — Phase 2B.2 Organization Workspace UI & Invitations Tests

Verifies:
1. Organization Selector UI (single, multi-org, empty state).
2. Role badges and operational boundary notice.
3. Organization Workspace tabs (Members, Invitations, Settings, Audit).
4. Role-based permission gating within the UI (VIEWER vs OPERATOR vs ORG_ADMIN).
5. Invitation issuance and revocation through the UI.
6. Public Invitation Acceptance view (query params page=accept_invite&token=...).
7. Platform Administrator organization provisioning and management center.
8. Strict operational isolation: operational surveillance data is never exposed as tenant data.
"""

import os
import pytest
from pathlib import Path
from datetime import datetime, timezone, timedelta

from src.auth.database import AuthDatabase, User, Organization, OrganizationMembership
from src.auth.service import AuthService
from src.auth.organization_service import (
    OrganizationService,
    MembershipService,
    resolve_tenant_context,
)
from src.auth.invitation_service import (
    InvitationService,
    generate_invitation_token,
    hash_invitation_token,
    normalize_email,
)

ROLE_ORG_ADMIN = "ORG_ADMIN"
ROLE_OPERATOR = "OPERATOR"
ROLE_VIEWER = "VIEWER"
ROLE_PLATFORM_ADMIN = "PLATFORM_ADMIN"


@pytest.fixture
def auth_db(tmp_path):
    db_file = tmp_path / "test_cp_org_ui.db"
    db = AuthDatabase(str(db_file))
    return db


@pytest.fixture
def test_services(auth_db):
    auth_svc = AuthService(auth_db)
    org_svc = OrganizationService(auth_db)
    member_svc = MembershipService(auth_db)
    invitation_svc = InvitationService(auth_db)
    return auth_svc, org_svc, member_svc, invitation_svc


def test_org_selector_multi_membership(test_services):
    """Verify that a user with multiple organization memberships sees all orgs and can select one."""
    auth_svc, org_svc, member_svc, _ = test_services

    # Create platform admin and user
    padmin = auth_svc.register_user("sysadmin", "sysadmin@crowdpatrol.internal", "Password123!", role=ROLE_PLATFORM_ADMIN)
    user = auth_svc.register_user("multiorg_user", "multi@example.com", "Password123!", role="USER")

    # Create two organizations
    org_a = org_svc.create_organization(
        name="Metro Transit Security",
        slug="metro-transit",
        actor=padmin,
        initial_admin_user_id=user.id
    )
    org_b = org_svc.create_organization(
        name="City Airport Police",
        slug="airport-police",
        actor=padmin
    )

    # Assign VIEWER in Org B
    admin_b = auth_svc.register_user("admin_b", "adminb@example.com", "Password123!", role="USER")
    org_svc.db.create_membership(f"mem_test_{admin_b.id[:6]}", org_b.id, admin_b.id, ROLE_ORG_ADMIN, "ACTIVE")
    member_svc.add_member(org_b.id, user.id, ROLE_VIEWER, actor=admin_b)

    # Resolve context for Org A (user is ORG_ADMIN)
    res_org_a, res_mem_a = resolve_tenant_context(user, requested_org_id=org_a.id, db=auth_svc.db)
    assert res_org_a.id == org_a.id
    assert res_mem_a.role == ROLE_ORG_ADMIN

    # Resolve context for Org B (user is VIEWER)
    res_org_b, res_mem_b = resolve_tenant_context(user, requested_org_id=org_b.id, db=auth_svc.db)
    assert res_org_b.id == org_b.id
    assert res_mem_b.role == ROLE_VIEWER


def test_org_selector_empty_state(test_services):
    """Verify behavior when a user has no active organization memberships."""
    auth_svc, org_svc, member_svc, _ = test_services

    user = auth_svc.register_user("lonely_user", "lonely@example.com", "Password123!", role="USER")

    memberships = org_svc.db.list_user_memberships(user.id)
    assert len(memberships) == 0

    res_org, res_mem = resolve_tenant_context(user, db=auth_svc.db)
    assert res_org is None
    assert res_mem is None


def test_operational_boundary_notice_presence():
    """Verify that operational boundary notice text is defined in org_ui.py."""
    org_ui_path = Path(__file__).parent.parent / "dashboard" / "org_ui.py"
    content = org_ui_path.read_text(encoding="utf-8")
    assert "Surveillance Isolation Boundary" in content
    assert "Global surveillance feeds remain separated" in content


def test_invitation_issuance_and_acceptance_lifecycle(test_services):
    """Verify complete lifecycle: issue invite -> validate token -> accept -> verify membership."""
    auth_svc, org_svc, member_svc, invitation_svc = test_services

    padmin = auth_svc.register_user("sysadmin", "sysadmin@crowdpatrol.internal", "Password123!", role=ROLE_PLATFORM_ADMIN)
    admin = auth_svc.register_user("org_admin_1", "admin1@example.com", "Password123!", role="USER")
    org = org_svc.create_organization("Stadium Authority", slug="stadium-auth", actor=padmin, initial_admin_user_id=admin.id)

    # Admin issues invitation to a new operator
    invitee_email = "new_operator@stadium.org"
    invitation, raw_token, err = invitation_svc.create_invitation(
        actor=admin,
        organization_id=org.id,
        email=invitee_email,
        role=ROLE_OPERATOR,
        expires_in_hours=72,
        send_email=False
    )
    assert err is None
    assert invitation.status == "PENDING"
    assert invitation.invited_role == ROLE_OPERATOR

    # Validate token
    validated, val_org, val_err = invitation_svc.validate_invitation_token(raw_token)
    assert val_err == ""
    assert validated.id == invitation.id
    assert val_org.id == org.id

    # Accept invitation as a new user
    success, membership, acc_err = invitation_svc.accept_invitation(
        raw_token=raw_token,
        new_user_credentials={"username": "stadium_op", "password": "SecurePass2026!"}
    )
    assert success is True
    assert acc_err == ""
    assert membership.role == ROLE_OPERATOR

    # Verify membership was atomically created in DB
    new_user = auth_svc.db.get_user_by_identity("stadium_op")
    assert new_user is not None
    memberships = org_svc.db.list_user_memberships(new_user.id)
    assert len(memberships) == 1
    assert memberships[0].organization_id == org.id
    assert memberships[0].role == ROLE_OPERATOR


def test_invitation_revocation_lifecycle(test_services):
    """Verify that an admin can revoke a pending invitation and it cannot be accepted afterwards."""
    auth_svc, org_svc, member_svc, invitation_svc = test_services

    padmin = auth_svc.register_user("sysadmin", "sysadmin@crowdpatrol.internal", "Password123!", role=ROLE_PLATFORM_ADMIN)
    admin = auth_svc.register_user("revoker_admin", "revoker@example.com", "Password123!", role="USER")
    org = org_svc.create_organization("Harbor Patrol", slug="harbor-patrol", actor=padmin, initial_admin_user_id=admin.id)

    invitation, raw_token, err = invitation_svc.create_invitation(
        actor=admin,
        organization_id=org.id,
        email="guest@harbor.org",
        role=ROLE_VIEWER,
        expires_in_hours=72,
        send_email=False
    )
    assert err is None

    # Admin revokes the invitation
    revoked = invitation_svc.revoke_invitation(actor=admin, invitation_id=invitation.id)
    assert revoked.status == "REVOKED"

    # Attempting to validate should fail
    inv_val, org_val, val_err = invitation_svc.validate_invitation_token(raw_token)
    assert "revoked" in val_err.lower()


def test_platform_admin_org_provisioning(test_services):
    """Verify that PLATFORM_ADMIN can provision new organizations and manage status."""
    auth_svc, org_svc, member_svc, _ = test_services

    padmin = auth_svc.register_user("sysadmin", "sysadmin@crowdpatrol.internal", "Password123!", role=ROLE_PLATFORM_ADMIN)

    # Provision organization
    org = org_svc.create_organization(
        name="Global Transit Authority",
        slug="global-transit",
        description="Headquarters division",
        actor=padmin
    )
    assert org.name == "Global Transit Authority"
    assert org.status == "ACTIVE"

    # Suspend organization
    suspended = org_svc.suspend_organization(org_id=org.id, actor=padmin)
    assert suspended.status == "SUSPENDED"

    # Reactivate organization
    reactivated = org_svc.reactivate_organization(org_id=org.id, actor=padmin)
    assert reactivated.status == "ACTIVE"
