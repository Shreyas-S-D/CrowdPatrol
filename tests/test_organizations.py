"""
CrowdPatrol 2.0 — Phase 2B.1 Organization & Membership Test Suite
Validates organization data models, multi-tenancy isolation, RBAC,
membership lifecycle, last active ORG_ADMIN safeguards, and tenant context resolution.
"""

import os
import tempfile
import pytest

from src.auth.database import AuthDatabase, User, Organization, OrganizationMembership
from src.auth.service import AuthService
from src.auth.organization_service import (
    OrganizationService,
    MembershipService,
    resolve_tenant_context,
    normalize_slug,
    is_platform_admin,
    can_manage_organization,
    can_manage_members,
    can_operate_monitoring,
    can_view_analytics,
)


@pytest.fixture
def temp_db():
    """Provides a fresh isolated SQLite database with schema version 2 applied."""
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
    """Provides an AuthService instance connected to the temporary database."""
    return AuthService(temp_db)


@pytest.fixture
def org_service(temp_db):
    """Provides an OrganizationService instance connected to the temporary database."""
    return OrganizationService(temp_db)


@pytest.fixture
def member_service(temp_db):
    """Provides a MembershipService instance connected to the temporary database."""
    return MembershipService(temp_db)


@pytest.fixture
def platform_admin_user(auth_service):
    """Creates a platform administrator user."""
    return auth_service.register_user(
        username="platform_admin",
        email="platform_admin@crowdpatrol.internal",
        password="ValidPassword123!",
        role="PLATFORM_ADMIN",
    )


@pytest.fixture
def standard_user_1(auth_service):
    """Creates standard user 1."""
    return auth_service.register_user(
        username="sarah_admin",
        email="sarah@corp.internal",
        password="ValidPassword123!",
        role="USER",
    )


@pytest.fixture
def standard_user_2(auth_service):
    """Creates standard user 2."""
    return auth_service.register_user(
        username="dave_operator",
        email="dave@corp.internal",
        password="ValidPassword123!",
        role="USER",
    )


@pytest.fixture
def standard_user_3(auth_service):
    """Creates standard user 3."""
    return auth_service.register_user(
        username="emma_viewer",
        email="emma@corp.internal",
        password="ValidPassword123!",
        role="USER",
    )


# ============================================================================
# 1. SLUG NORMALIZATION & VALIDATION TESTS
# ============================================================================


def test_slug_normalization_valid():
    """Confirms valid slug strings are normalized correctly."""
    assert normalize_slug("Metro Transit Authority") == "metro-transit-authority"
    assert normalize_slug("Airport-Terminal-1") == "airport-terminal-1"
    assert normalize_slug("SmartCity 2026") == "smartcity-2026"
    assert normalize_slug("  Leading and Trailing  ") == "leading-and-trailing"
    assert normalize_slug("Special!@#Characters$$%Here") == "special-characters-here"


def test_slug_normalization_invalid():
    """Confirms empty, whitespace-only, or non-alphanumeric strings raise ValueError."""
    with pytest.raises(ValueError, match="Slug cannot be empty"):
        normalize_slug("")
    with pytest.raises(ValueError, match="Slug cannot be empty"):
        normalize_slug("    ")
    with pytest.raises(ValueError, match="contains no valid alphanumeric"):
        normalize_slug("!@#$%^&*()")


# ============================================================================
# 2. ORGANIZATION SERVICE & LIFECYCLE TESTS
# ============================================================================


def test_create_organization_by_platform_admin(org_service, platform_admin_user, standard_user_1):
    """Platform admin can create an organization with an initial ORG_ADMIN."""
    org = org_service.create_organization(
        name="Metro Transit Police",
        slug="metro-transit-police",
        description="Public transit surveillance division",
        actor=platform_admin_user,
        initial_admin_user_id=standard_user_1.id,
    )
    assert org is not None
    assert org.name == "Metro Transit Police"
    assert org.slug == "metro-transit-police"
    assert org.status == "ACTIVE"
    assert org.created_by == platform_admin_user.id

    # Verify initial membership was created
    membership = org_service.db.get_membership(org.id, standard_user_1.id)
    assert membership is not None
    assert membership.role == "ORG_ADMIN"
    assert membership.status == "ACTIVE"


def test_create_organization_unauthorized(org_service, standard_user_1):
    """Non-platform admin cannot create an organization."""
    with pytest.raises(PermissionError, match="Platform administrator privilege required"):
        org_service.create_organization(
            name="Rogue Org",
            slug="rogue-org",
            actor=standard_user_1,
        )


def test_create_organization_duplicate_slug_rejected(org_service, platform_admin_user):
    """Duplicate organization slugs are rejected with ValueError."""
    org_service.create_organization(
        name="Airport Security Alpha",
        slug="airport-security",
        actor=platform_admin_user,
    )
    with pytest.raises(ValueError, match="already in use"):
        org_service.create_organization(
            name="Airport Security Beta",
            slug="airport-security",
            actor=platform_admin_user,
        )


def test_get_organization_by_id_and_slug(org_service, platform_admin_user):
    """Can retrieve organizations by both ID and slug."""
    created = org_service.create_organization(
        name="Stadium Safety Command",
        slug="stadium-safety",
        actor=platform_admin_user,
    )
    by_id = org_service.get_organization(created.id)
    assert by_id is not None
    assert by_id.id == created.id
    assert by_id.name == created.name

    by_slug = org_service.get_organization_by_slug("stadium-safety")
    assert by_slug is not None
    assert by_slug.id == created.id


def test_list_accessible_organizations_platform_admin_vs_member(
    org_service, member_service, platform_admin_user, standard_user_1, standard_user_2
):
    """Platform admin sees all orgs, while standard users see only their memberships."""
    org1 = org_service.create_organization(
        name="Org One", slug="org-one", actor=platform_admin_user, initial_admin_user_id=standard_user_1.id
    )
    org2 = org_service.create_organization(
        name="Org Two", slug="org-two", actor=platform_admin_user, initial_admin_user_id=standard_user_2.id
    )

    # Platform admin sees both
    admin_orgs = org_service.list_accessible_organizations(platform_admin_user)
    org_ids_for_admin = [o.id for o in admin_orgs]
    assert org1.id in org_ids_for_admin
    assert org2.id in org_ids_for_admin

    # Standard user 1 sees only Org 1
    u1_orgs = org_service.list_accessible_organizations(standard_user_1)
    assert len(u1_orgs) == 1
    assert u1_orgs[0].id == org1.id

    # Standard user 2 sees only Org 2
    u2_orgs = org_service.list_accessible_organizations(standard_user_2)
    assert len(u2_orgs) == 1
    assert u2_orgs[0].id == org2.id


def test_update_organization_metadata(org_service, platform_admin_user, standard_user_1):
    """ORG_ADMIN and platform admin can update organization metadata."""
    org = org_service.create_organization(
        name="City Center Surveillance",
        slug="city-center",
        description="Initial description",
        actor=platform_admin_user,
        initial_admin_user_id=standard_user_1.id,
    )

    # Standard user 1 (ORG_ADMIN) updates description
    updated = org_service.update_organization(
        org_id=org.id,
        name="City Center Smart Surveillance",
        description="Updated high-priority operational zone",
        actor=standard_user_1,
    )
    assert updated.name == "City Center Smart Surveillance"
    assert updated.description == "Updated high-priority operational zone"


def test_organization_status_transitions_and_archival(org_service, platform_admin_user):
    """Verifies suspend, reactivate, and archive lifecycle transitions."""
    org = org_service.create_organization(
        name="Harbor Patrol",
        slug="harbor-patrol",
        actor=platform_admin_user,
    )
    assert org.status == "ACTIVE"

    # Suspend
    suspended = org_service.suspend_organization(org.id, actor=platform_admin_user)
    assert suspended.status == "SUSPENDED"

    # Reactivate
    reactivated = org_service.reactivate_organization(org.id, actor=platform_admin_user)
    assert reactivated.status == "ACTIVE"

    # Archive
    archived = org_service.archive_organization(org.id, actor=platform_admin_user)
    assert archived.status == "ARCHIVED"


# ============================================================================
# 3. MEMBERSHIP SERVICE & LAST ACTIVE ORG_ADMIN PROTECTION TESTS
# ============================================================================


def test_membership_lifecycle_add_list_role_change(
    org_service, member_service, platform_admin_user, standard_user_1, standard_user_2
):
    """Validates adding members, listing members, and changing member roles."""
    org = org_service.create_organization(
        name="Metro North Depot",
        slug="metro-north",
        actor=platform_admin_user,
        initial_admin_user_id=standard_user_1.id,
    )

    # Sarah (ORG_ADMIN) adds Dave as OPERATOR
    m_dave = member_service.add_member(
        org_id=org.id,
        user_id=standard_user_2.id,
        role="OPERATOR",
        actor=standard_user_1,
    )
    assert m_dave.user_id == standard_user_2.id
    assert m_dave.role == "OPERATOR"
    assert m_dave.status == "ACTIVE"

    # List members
    members = member_service.list_members(org.id, actor=standard_user_1)
    assert len(members) == 2
    user_ids = [m.user_id for m in members]
    assert standard_user_1.id in user_ids
    assert standard_user_2.id in user_ids

    # Change Dave's role to VIEWER
    updated_dave = member_service.change_member_role(
        org_id=org.id,
        user_id=standard_user_2.id,
        new_role="VIEWER",
        actor=standard_user_1,
    )
    assert updated_dave.role == "VIEWER"


def test_add_member_duplicate_rejected(
    org_service, member_service, platform_admin_user, standard_user_1, standard_user_2
):
    """Adding an already enrolled user raises ValueError."""
    org = org_service.create_organization(
        name="Campus Safety",
        slug="campus-safety",
        actor=platform_admin_user,
        initial_admin_user_id=standard_user_1.id,
    )
    member_service.add_member(
        org_id=org.id,
        user_id=standard_user_2.id,
        role="OPERATOR",
        actor=standard_user_1,
    )
    with pytest.raises(ValueError, match="already a member"):
        member_service.add_member(
            org_id=org.id,
            user_id=standard_user_2.id,
            role="VIEWER",
            actor=standard_user_1,
        )


def test_last_active_org_admin_protection_demotion(
    org_service, member_service, platform_admin_user, standard_user_1
):
    """Cannot demote the last active ORG_ADMIN to OPERATOR or VIEWER."""
    org = org_service.create_organization(
        name="Critical Perimeter Alpha",
        slug="perimeter-alpha",
        actor=platform_admin_user,
        initial_admin_user_id=standard_user_1.id,
    )

    with pytest.raises(ValueError, match="Cannot demote the last active ORG_ADMIN"):
        member_service.change_member_role(
            org_id=org.id,
            user_id=standard_user_1.id,
            new_role="OPERATOR",
            actor=platform_admin_user,
        )


def test_last_active_org_admin_protection_suspension(
    org_service, member_service, platform_admin_user, standard_user_1
):
    """Cannot suspend the last active ORG_ADMIN."""
    org = org_service.create_organization(
        name="Critical Perimeter Beta",
        slug="perimeter-beta",
        actor=platform_admin_user,
        initial_admin_user_id=standard_user_1.id,
    )

    with pytest.raises(ValueError, match="Cannot suspend the last active ORG_ADMIN"):
        member_service.suspend_member(
            org_id=org.id,
            user_id=standard_user_1.id,
            actor=platform_admin_user,
        )


def test_last_active_org_admin_protection_removal(
    org_service, member_service, platform_admin_user, standard_user_1
):
    """Cannot remove the last active ORG_ADMIN."""
    org = org_service.create_organization(
        name="Critical Perimeter Gamma",
        slug="perimeter-gamma",
        actor=platform_admin_user,
        initial_admin_user_id=standard_user_1.id,
    )

    with pytest.raises(ValueError, match="Cannot remove the last active ORG_ADMIN"):
        member_service.remove_member(
            org_id=org.id,
            user_id=standard_user_1.id,
            actor=platform_admin_user,
        )


def test_demote_permitted_when_another_org_admin_exists(
    org_service, member_service, platform_admin_user, standard_user_1, standard_user_2
):
    """Demotion is allowed if another active ORG_ADMIN exists."""
    org = org_service.create_organization(
        name="Dual Admin Division",
        slug="dual-admin",
        actor=platform_admin_user,
        initial_admin_user_id=standard_user_1.id,
    )
    # Add Dave as a second ORG_ADMIN
    member_service.add_member(
        org_id=org.id,
        user_id=standard_user_2.id,
        role="ORG_ADMIN",
        actor=standard_user_1,
    )

    # Now Sarah can be demoted to OPERATOR because Dave remains an active ORG_ADMIN
    demoted = member_service.change_member_role(
        org_id=org.id,
        user_id=standard_user_1.id,
        new_role="OPERATOR",
        actor=standard_user_2,
    )
    assert demoted.role == "OPERATOR"


# ============================================================================
# 4. ROLE-BASED ACCESS CONTROL (RBAC) PERMISSION TESTS
# ============================================================================


def test_rbac_permission_helpers(platform_admin_user, standard_user_1):
    """Validates RBAC helper matrix across PLATFORM_ADMIN, ORG_ADMIN, OPERATOR, VIEWER."""
    # Platform Admin
    assert is_platform_admin(platform_admin_user) is True

    # User with SUPER_ADMIN role (legacy backward compatibility)
    from datetime import datetime, timezone
    now_dt = datetime.now(timezone.utc)
    legacy_super = User(
        id="usr_legacy_999",
        username="legacy_super",
        email="legacy@crowdpatrol.internal",
        password_hash="...",
        role="SUPER_ADMIN",
        is_active=True,
        failed_login_attempts=0,
        locked_until=None,
        created_at=now_dt,
        updated_at=now_dt,
    )
    assert is_platform_admin(legacy_super) is True

    # Standard user
    assert is_platform_admin(standard_user_1) is False

    # ORG_ADMIN permissions
    assert can_manage_organization("ORG_ADMIN") is True
    assert can_manage_members("ORG_ADMIN") is True
    assert can_operate_monitoring("ORG_ADMIN") is True
    assert can_view_analytics("ORG_ADMIN") is True

    # OPERATOR permissions
    assert can_manage_organization("OPERATOR") is False
    assert can_manage_members("OPERATOR") is False
    assert can_operate_monitoring("OPERATOR") is True
    assert can_view_analytics("OPERATOR") is True

    # VIEWER permissions
    assert can_manage_organization("VIEWER") is False
    assert can_manage_members("VIEWER") is False
    assert can_operate_monitoring("VIEWER") is False
    assert can_view_analytics("VIEWER") is True


def test_unauthorized_member_management(
    org_service, member_service, platform_admin_user, standard_user_1, standard_user_2, standard_user_3
):
    """An OPERATOR or VIEWER cannot add members or change roles."""
    org = org_service.create_organization(
        name="Secure Facility Delta",
        slug="facility-delta",
        actor=platform_admin_user,
        initial_admin_user_id=standard_user_1.id,
    )
    # Sarah adds Dave as OPERATOR
    member_service.add_member(
        org_id=org.id,
        user_id=standard_user_2.id,
        role="OPERATOR",
        actor=standard_user_1,
    )

    # Dave (OPERATOR) tries to add Emma -> PermissionError
    with pytest.raises(PermissionError, match="Insufficient role"):
        member_service.add_member(
            org_id=org.id,
            user_id=standard_user_3.id,
            role="VIEWER",
            actor=standard_user_2,
        )


# ============================================================================
# 5. SERVER-SIDE TENANT CONTEXT RESOLUTION & ISOLATION TESTS
# ============================================================================


def test_resolve_tenant_context_success_by_id_and_slug(
    org_service, platform_admin_user, standard_user_1
):
    """Resolves tenant context successfully for authenticated member by org_id or slug."""
    org = org_service.create_organization(
        name="Logistics Port Central",
        slug="port-central",
        actor=platform_admin_user,
        initial_admin_user_id=standard_user_1.id,
    )

    # Resolve by ID
    resolved_org, membership = resolve_tenant_context(
        user=standard_user_1,
        requested_org_id=org.id,
        db=org_service.db,
    )
    assert resolved_org.id == org.id
    assert membership.role == "ORG_ADMIN"

    # Resolve by Slug
    resolved_org_slug, membership_slug = resolve_tenant_context(
        user=standard_user_1,
        requested_slug="port-central",
        db=org_service.db,
    )
    assert resolved_org_slug.id == org.id
    assert membership_slug.user_id == standard_user_1.id


def test_resolve_tenant_context_cross_tenant_access_denied(
    org_service, platform_admin_user, standard_user_1, standard_user_2
):
    """A user attempting to access an organization they are not a member of is denied."""
    org1 = org_service.create_organization(
        name="Org Alpha",
        slug="org-alpha",
        actor=platform_admin_user,
        initial_admin_user_id=standard_user_1.id,
    )

    # Standard user 2 has no membership in Org Alpha
    with pytest.raises(PermissionError, match="not an active member of organization"):
        resolve_tenant_context(
            user=standard_user_2,
            requested_org_id=org1.id,
            db=org_service.db,
        )


def test_resolve_tenant_context_suspended_org_denied(
    org_service, platform_admin_user, standard_user_1
):
    """Cannot resolve context for a suspended organization."""
    org = org_service.create_organization(
        name="Suspended Zone",
        slug="suspended-zone",
        actor=platform_admin_user,
        initial_admin_user_id=standard_user_1.id,
    )
    org_service.suspend_organization(org.id, actor=platform_admin_user)

    with pytest.raises(PermissionError, match="currently suspended"):
        resolve_tenant_context(
            user=standard_user_1,
            requested_org_id=org.id,
            db=org_service.db,
        )


def test_resolve_tenant_context_suspended_member_denied(
    org_service, member_service, platform_admin_user, standard_user_1, standard_user_2
):
    """A suspended member cannot resolve tenant context."""
    org = org_service.create_organization(
        name="Active Facility",
        slug="active-facility",
        actor=platform_admin_user,
        initial_admin_user_id=standard_user_1.id,
    )
    member_service.add_member(
        org_id=org.id,
        user_id=standard_user_2.id,
        role="OPERATOR",
        actor=standard_user_1,
    )
    # Suspend Dave
    member_service.suspend_member(org.id, standard_user_2.id, actor=standard_user_1)

    with pytest.raises(PermissionError, match="Membership .* is SUSPENDED"):
        resolve_tenant_context(
            user=standard_user_2,
            requested_org_id=org.id,
            db=org_service.db,
        )


def test_resolve_tenant_context_platform_admin_elevation(
    org_service, platform_admin_user, standard_user_1
):
    """Platform admin can resolve context for any active organization with virtual admin role."""
    org = org_service.create_organization(
        name="Independent Agency",
        slug="independent-agency",
        actor=platform_admin_user,
        initial_admin_user_id=standard_user_1.id,
    )

    resolved_org, membership = resolve_tenant_context(
        user=platform_admin_user,
        requested_org_id=org.id,
        db=org_service.db,
    )
    assert resolved_org.id == org.id
    assert membership.role == "ORG_ADMIN"
    assert membership.user_id == platform_admin_user.id


def test_resolve_tenant_context_default_to_first_accessible_org(
    org_service, platform_admin_user, standard_user_1
):
    """When no org_id or slug is provided, resolves to the user's first accessible active org."""
    org = org_service.create_organization(
        name="Primary Precinct",
        slug="primary-precinct",
        actor=platform_admin_user,
        initial_admin_user_id=standard_user_1.id,
    )

    resolved_org, membership = resolve_tenant_context(
        user=standard_user_1,
        db=org_service.db,
    )
    assert resolved_org.id == org.id
    assert membership.organization_id == org.id


def test_multi_organization_membership_switching(
    org_service, member_service, platform_admin_user, standard_user_1
):
    """User belonging to two organizations can resolve context for either with accurate roles."""
    org_a = org_service.create_organization(
        name="Sector A",
        slug="sector-a",
        actor=platform_admin_user,
        initial_admin_user_id=standard_user_1.id,
    )
    org_b = org_service.create_organization(
        name="Sector B",
        slug="sector-b",
        actor=platform_admin_user,
    )
    # Add user 1 to Sector B as VIEWER
    member_service.add_member(
        org_id=org_b.id,
        user_id=standard_user_1.id,
        role="VIEWER",
        actor=platform_admin_user,
    )

    # In Sector A, user is ORG_ADMIN
    _, mem_a = resolve_tenant_context(standard_user_1, requested_org_id=org_a.id, db=org_service.db)
    assert mem_a.role == "ORG_ADMIN"

    # In Sector B, user is VIEWER
    _, mem_b = resolve_tenant_context(standard_user_1, requested_org_id=org_b.id, db=org_service.db)
    assert mem_b.role == "VIEWER"


# ============================================================================
# 6. AUDIT EVENT LOGGING TESTS
# ============================================================================


def test_audit_events_emitted(org_service, member_service, platform_admin_user, standard_user_1, standard_user_2):
    """Verifies that actions create structured audit events in organization_audit_events."""
    org = org_service.create_organization(
        name="Audited Precinct",
        slug="audited-precinct",
        actor=platform_admin_user,
        initial_admin_user_id=standard_user_1.id,
    )

    member_service.add_member(
        org_id=org.id,
        user_id=standard_user_2.id,
        role="OPERATOR",
        actor=standard_user_1,
    )

    events = org_service.db.list_audit_events(org.id)
    actions = [e.action for e in events]

    assert "ORGANIZATION_CREATED" in actions
    assert "MEMBER_ADDED" in actions
    for e in events:
        assert e.organization_id == org.id
        assert e.created_at is not None
