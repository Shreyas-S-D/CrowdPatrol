"""
CrowdPatrol 2.0 — Organization, Membership & Tenant Authorization Subsystem
Encapsulates multi-tenant organization lifecycle, membership access control,
server-side tenant context resolution, and non-repudiable administrative auditing.
"""

import re
import uuid
import logging
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timezone

from src.auth.database import (
    AuthDatabase,
    User,
    Organization,
    OrganizationMembership,
    OrganizationAuditEvent
)

logger = logging.getLogger("crowdpatrol.auth.organizations")

# Slug validation pattern: lowercase alphanumeric with single hyphens, 2-64 chars
SLUG_REGEX = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")

# Valid Organization & Membership Roles & Statuses
VALID_ORG_ROLES = ("ORG_ADMIN", "OPERATOR", "VIEWER")
VALID_ORG_STATUSES = ("ACTIVE", "SUSPENDED", "ARCHIVED")
VALID_MEMBERSHIP_STATUSES = ("ACTIVE", "INVITED", "SUSPENDED")


# =============================================================================
# SLUG UTILITY
# =============================================================================

def normalize_slug(text: str) -> str:
    """
    Normalizes a name or candidate slug into a valid URL-safe slug.
    Converts to lowercase, replaces spaces/symbols with hyphens, and trims.
    """
    if not text or not isinstance(text, str) or not text.strip():
        raise ValueError("Slug cannot be empty.")
    
    slug = text.strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    
    if not slug:
        raise ValueError("Slug contains no valid alphanumeric characters.")
    
    if len(slug) > 64:
        slug = slug[:64].rstrip("-")
        
    if not SLUG_REGEX.match(slug):
        raise ValueError(f"Normalized slug '{slug}' is invalid. Must be 2-64 alphanumeric characters and hyphens.")
        
    return slug


# =============================================================================
# REUSABLE AUTHORIZATION ENGINE (RBAC)
# =============================================================================

def is_platform_admin(user: Optional[User]) -> bool:
    """
    Returns True if user holds platform-level administrative privileges.
    Recognizes both PLATFORM_ADMIN and legacy SUPER_ADMIN for zero-regression compatibility.
    """
    if not user or not user.is_active:
        return False
    return user.role.upper() in ("PLATFORM_ADMIN", "SUPER_ADMIN")


def can_manage_organization(
    user_or_role: Any,
    org: Optional[Organization] = None,
    membership: Optional[OrganizationMembership] = None
) -> bool:
    """
    Evaluates whether a user or role can modify organization settings (name, description).
    Allowed for:
    - Role string: ORG_ADMIN, PLATFORM_ADMIN, SUPER_ADMIN
    - Platform Admins (for any organization)
    - Active ORG_ADMIN of an ACTIVE organization
    """
    if isinstance(user_or_role, str):
        return user_or_role.upper() in ("ORG_ADMIN", "PLATFORM_ADMIN", "SUPER_ADMIN")
    if not user_or_role or not getattr(user_or_role, "is_active", False):
        return False
    if is_platform_admin(user_or_role):
        return True
    if org and org.status != "ACTIVE":
        return False
    return bool(membership and membership.status == "ACTIVE" and membership.role == "ORG_ADMIN")


def can_manage_members(
    user_or_role: Any,
    org: Optional[Organization] = None,
    membership: Optional[OrganizationMembership] = None
) -> bool:
    """
    Evaluates whether a user or role can add, update, suspend, or remove members.
    Allowed for:
    - Role string: ORG_ADMIN, PLATFORM_ADMIN, SUPER_ADMIN
    - Platform Admins
    - Active ORG_ADMIN of an ACTIVE organization
    """
    if isinstance(user_or_role, str):
        return user_or_role.upper() in ("ORG_ADMIN", "PLATFORM_ADMIN", "SUPER_ADMIN")
    if not user_or_role or not getattr(user_or_role, "is_active", False):
        return False
    if is_platform_admin(user_or_role):
        return True
    if org and org.status != "ACTIVE":
        return False
    return bool(membership and membership.status == "ACTIVE" and membership.role == "ORG_ADMIN")


def can_operate_monitoring(
    user_or_role: Any,
    org: Optional[Organization] = None,
    membership: Optional[OrganizationMembership] = None
) -> bool:
    """
    Evaluates whether a user or role can start/stop cameras, run AI detection, or manage alerts.
    Allowed for:
    - Role string: ORG_ADMIN, OPERATOR, PLATFORM_ADMIN, SUPER_ADMIN
    - Platform Admins
    - Active ORG_ADMIN or OPERATOR of an ACTIVE organization
    """
    if isinstance(user_or_role, str):
        return user_or_role.upper() in ("ORG_ADMIN", "OPERATOR", "PLATFORM_ADMIN", "SUPER_ADMIN")
    if not user_or_role or not getattr(user_or_role, "is_active", False):
        return False
    if is_platform_admin(user_or_role):
        return True
    if org and org.status != "ACTIVE":
        return False
    return bool(
        membership and 
        membership.status == "ACTIVE" and 
        membership.role in ("ORG_ADMIN", "OPERATOR")
    )


def can_view_analytics(
    user_or_role: Any,
    org: Optional[Organization] = None,
    membership: Optional[OrganizationMembership] = None
) -> bool:
    """
    Evaluates whether a user or role can view analytics, telemetry, and camera streams.
    Allowed for:
    - Role string: ORG_ADMIN, OPERATOR, VIEWER, PLATFORM_ADMIN, SUPER_ADMIN
    - Platform Admins
    - Active ORG_ADMIN, OPERATOR, or VIEWER of an ACTIVE organization
    """
    if isinstance(user_or_role, str):
        return user_or_role.upper() in ("ORG_ADMIN", "OPERATOR", "VIEWER", "PLATFORM_ADMIN", "SUPER_ADMIN")
    if not user_or_role or not getattr(user_or_role, "is_active", False):
        return False
    if is_platform_admin(user_or_role):
        return True
    if org and org.status != "ACTIVE":
        return False
    return bool(
        membership and 
        membership.status == "ACTIVE" and 
        membership.role in ("ORG_ADMIN", "OPERATOR", "VIEWER")
    )


def require_authenticated_user(user: Optional[User]) -> User:
    """Enforces that an active authenticated user session exists."""
    if not user or not user.is_active:
        raise PermissionError("Authentication required.")
    return user


def require_organization_membership(
    user: User,
    org: Organization,
    membership: Optional[OrganizationMembership]
) -> Optional[OrganizationMembership]:
    """Enforces that the user has an authorized membership in the target organization."""
    require_authenticated_user(user)
    if is_platform_admin(user):
        return membership
    if org.status == "SUSPENDED":
        raise PermissionError(f"Organization '{org.name}' is currently suspended.")
    if org.status == "ARCHIVED":
        raise PermissionError(f"Organization '{org.name}' is archived.")
    if not membership or membership.status != "ACTIVE":
        raise PermissionError(f"User '{user.username}' does not have an active membership in organization '{org.name}'.")
    return membership


def require_organization_role(
    user: User,
    org: Organization,
    membership: Optional[OrganizationMembership],
    allowed_roles: List[str]
) -> Optional[OrganizationMembership]:
    """Enforces that the user holds one of the required roles in the organization."""
    require_organization_membership(user, org, membership)
    if is_platform_admin(user):
        return membership
    if not membership or membership.role not in allowed_roles:
        raise PermissionError(
            f"User '{user.username}' has role '{membership.role if membership else 'NONE'}', "
            f"which is not authorized for this operation (required: {', '.join(allowed_roles)})."
        )
    return membership


# =============================================================================
# ORGANIZATION SERVICE
# =============================================================================

class OrganizationService:
    """
    Business service managing multi-tenant organization creation, updates,
    lifecycle state transitions, and audit logging.
    """

    def __init__(self, db: Optional[AuthDatabase] = None):
        self.db = db if db is not None else AuthDatabase()

    def create_organization(
        self,
        name: str,
        slug: Optional[str] = None,
        description: Optional[str] = None,
        actor: Optional[User] = None,
        initial_admin_user_id: Optional[str] = None,
    ) -> Organization:
        """
        Creates a new organization.
        Only Platform Administrators are authorized to provision new organizations.
        """
        require_authenticated_user(actor)
        if not is_platform_admin(actor):
            raise PermissionError("Platform administrator privilege required to create organizations.")

        clean_name = name.strip() if name else ""
        if len(clean_name) < 2 or len(clean_name) > 100:
            raise ValueError("Organization name must be between 2 and 100 characters.")

        resolved_slug = normalize_slug(slug or clean_name)
        existing = self.db.get_organization_by_slug(resolved_slug)
        if existing:
            raise ValueError(f"Organization slug '{resolved_slug}' is already in use.")

        org_id = f"org_{uuid.uuid4().hex[:12]}"
        clean_desc = description.strip() if description else None

        org = self.db.create_organization(
            org_id=org_id,
            name=clean_name,
            slug=resolved_slug,
            description=clean_desc,
            created_by=actor.id if actor else None,
            status="ACTIVE"
        )

        # Record audit event
        event_id = f"aud_{uuid.uuid4().hex[:12]}"
        self.db.create_audit_event(
            event_id=event_id,
            organization_id=org.id,
            actor_user_id=actor.id if actor else "system",
            action="ORGANIZATION_CREATED",
            target_type="ORGANIZATION",
            target_id=org.id,
            metadata={"name": org.name, "slug": org.slug}
        )

        # Optionally provision initial administrator membership
        if initial_admin_user_id:
            mem_id = f"mem_{uuid.uuid4().hex[:12]}"
            self.db.create_membership(
                membership_id=mem_id,
                organization_id=org.id,
                user_id=initial_admin_user_id,
                role="ORG_ADMIN",
                status="ACTIVE"
            )
            self.db.create_audit_event(
                event_id=f"aud_{uuid.uuid4().hex[:12]}",
                organization_id=org.id,
                actor_user_id=actor.id if actor else "system",
                action="MEMBER_ADDED",
                target_type="MEMBERSHIP",
                target_id=mem_id,
                metadata={"initial_admin": True, "user_id": initial_admin_user_id, "role": "ORG_ADMIN"}
            )

        logger.info("Organization '%s' (slug: %s) created by %s", org.name, org.slug, actor.username if actor else "system")
        return org

    def get_organization(self, org_id: str) -> Optional[Organization]:
        """Retrieves an organization by ID."""
        if not org_id:
            return None
        return self.db.get_organization_by_id(org_id)

    def get_organization_by_slug(self, slug: str) -> Optional[Organization]:
        """Retrieves an organization by slug."""
        if not slug:
            return None
        return self.db.get_organization_by_slug(slug)

    def list_accessible_organizations(self, user: User) -> List[Organization]:
        """
        Lists all organizations accessible to the user:
        - Platform admins see all non-archived organizations.
        - Regular users see organizations where they have active memberships.
        """
        require_authenticated_user(user)
        if is_platform_admin(user):
            all_orgs = self.db.list_all_organizations()
            return [o for o in all_orgs if o.status != "ARCHIVED"]
        return self.db.list_organizations_for_user(user.id)

    def update_organization(
        self,
        org_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        actor: Optional[User] = None,
    ) -> Organization:
        """Updates organization metadata (name, description)."""
        require_authenticated_user(actor)
        org = self.db.get_organization_by_id(org_id)
        if not org:
            raise ValueError(f"Organization '{org_id}' not found.")

        membership = self.db.get_membership(org.id, actor.id) if actor else None
        if not can_manage_organization(actor, org, membership):
            raise PermissionError("You do not have permission to manage this organization.")

        clean_name = name.strip() if name is not None else None
        if clean_name is not None and (len(clean_name) < 2 or len(clean_name) > 100):
            raise ValueError("Organization name must be between 2 and 100 characters.")

        clean_desc = description.strip() if description is not None else None

        updated = self.db.update_organization(
            org_id=org.id,
            name=clean_name,
            description=clean_desc
        )

        event_id = f"aud_{uuid.uuid4().hex[:12]}"
        self.db.create_audit_event(
            event_id=event_id,
            organization_id=org.id,
            actor_user_id=actor.id if actor else "system",
            action="ORGANIZATION_UPDATED",
            target_type="ORGANIZATION",
            target_id=org.id,
            metadata={"name": updated.name, "description": updated.description}
        )

        logger.info("Organization '%s' updated by %s", org.id, actor.username if actor else "system")
        return updated

    def suspend_organization(
        self,
        org_id: str,
        actor: Optional[User] = None,
        reason: Optional[str] = None
    ) -> Organization:
        """Suspends an organization. Only Platform Administrators can suspend."""
        require_authenticated_user(actor)
        if not is_platform_admin(actor):
            raise PermissionError("Only platform administrators can suspend organizations.")

        org = self.db.get_organization_by_id(org_id)
        if not org:
            raise ValueError(f"Organization '{org_id}' not found.")

        updated = self.db.update_organization(org_id=org.id, status="SUSPENDED")

        event_id = f"aud_{uuid.uuid4().hex[:12]}"
        self.db.create_audit_event(
            event_id=event_id,
            organization_id=org.id,
            actor_user_id=actor.id if actor else "system",
            action="ORGANIZATION_SUSPENDED",
            target_type="ORGANIZATION",
            target_id=org.id,
            metadata={"reason": reason or "Administrative suspension"}
        )

        logger.warning("Organization '%s' suspended by %s. Reason: %s", org.id, actor.username if actor else "system", reason)
        return updated

    def reactivate_organization(
        self,
        org_id: str,
        actor: Optional[User] = None
    ) -> Organization:
        """Reactivates a suspended organization. Only Platform Administrators can reactivate."""
        require_authenticated_user(actor)
        if not is_platform_admin(actor):
            raise PermissionError("Only platform administrators can reactivate organizations.")

        org = self.db.get_organization_by_id(org_id)
        if not org:
            raise ValueError(f"Organization '{org_id}' not found.")

        updated = self.db.update_organization(org_id=org.id, status="ACTIVE")

        event_id = f"aud_{uuid.uuid4().hex[:12]}"
        self.db.create_audit_event(
            event_id=event_id,
            organization_id=org.id,
            actor_user_id=actor.id if actor else "system",
            action="ORGANIZATION_REACTIVATED",
            target_type="ORGANIZATION",
            target_id=org.id,
            metadata={}
        )

        logger.info("Organization '%s' reactivated by %s", org.id, actor.username if actor else "system")
        return updated

    def archive_organization(
        self,
        org_id: str,
        actor: Optional[User] = None
    ) -> Organization:
        """Archives an organization. Only Platform Administrators can archive."""
        require_authenticated_user(actor)
        if not is_platform_admin(actor):
            raise PermissionError("Only platform administrators can archive organizations.")

        org = self.db.get_organization_by_id(org_id)
        if not org:
            raise ValueError(f"Organization '{org_id}' not found.")

        updated = self.db.update_organization(org_id=org.id, status="ARCHIVED")

        event_id = f"aud_{uuid.uuid4().hex[:12]}"
        self.db.create_audit_event(
            event_id=event_id,
            organization_id=org.id,
            actor_user_id=actor.id if actor else "system",
            action="ORGANIZATION_ARCHIVED",
            target_type="ORGANIZATION",
            target_id=org.id,
            metadata={}
        )

        logger.warning("Organization '%s' archived by %s", org.id, actor.username if actor else "system")
        return updated


# =============================================================================
# MEMBERSHIP SERVICE
# =============================================================================

class MembershipService:
    """
    Business service managing organization memberships, role assignments,
    status transitions, and last-active-admin safeguards.
    """

    def __init__(self, db: Optional[AuthDatabase] = None):
        self.db = db if db is not None else AuthDatabase()

    def add_member(
        self,
        org_id: str,
        user_id: str,
        role: str = "VIEWER",
        actor: Optional[User] = None,
        organization_id: Optional[str] = None
    ) -> OrganizationMembership:
        """Adds a user to an organization with a specific role."""
        target_org_id = org_id or organization_id
        require_authenticated_user(actor)
        org = self.db.get_organization_by_id(target_org_id)
        if not org:
            raise ValueError(f"Organization '{target_org_id}' not found.")

        actor_membership = self.db.get_membership(org.id, actor.id) if actor else None
        if not can_manage_members(actor, org, actor_membership):
            raise PermissionError("Insufficient role: you do not have permission to manage members in this organization.")

        clean_role = role.strip().upper()
        if clean_role not in VALID_ORG_ROLES:
            raise ValueError(f"Invalid role '{role}'. Allowed roles: {', '.join(VALID_ORG_ROLES)}")

        target_user = self.db.get_user_by_id(user_id)
        if not target_user:
            raise ValueError(f"User '{user_id}' does not exist.")

        existing = self.db.get_membership(org.id, user_id)
        if existing:
            raise ValueError(f"User '{target_user.username}' is already a member of organization '{org.name}'.")

        membership_id = f"mem_{uuid.uuid4().hex[:12]}"
        membership = self.db.create_membership(
            membership_id=membership_id,
            organization_id=org.id,
            user_id=target_user.id,
            role=clean_role,
            status="ACTIVE"
        )

        event_id = f"aud_{uuid.uuid4().hex[:12]}"
        self.db.create_audit_event(
            event_id=event_id,
            organization_id=org.id,
            actor_user_id=actor.id if actor else "system",
            action="MEMBER_ADDED",
            target_type="MEMBERSHIP",
            target_id=membership.id,
            metadata={"target_username": target_user.username, "role": clean_role}
        )

        logger.info("User '%s' added to organization '%s' as %s by %s", target_user.username, org.name, clean_role, actor.username if actor else "system")
        return membership

    def get_membership(
        self,
        org_id: str,
        user_id: str,
        organization_id: Optional[str] = None
    ) -> Optional[OrganizationMembership]:
        """Retrieves a membership record by org ID and user ID."""
        target_org_id = org_id or organization_id
        if not target_org_id or not user_id:
            return None
        return self.db.get_membership(target_org_id, user_id)

    def list_members(
        self,
        org_id: str,
        actor: Optional[User] = None,
        organization_id: Optional[str] = None
    ) -> List[OrganizationMembership]:
        """Lists all members of an organization as membership objects."""
        target_org_id = org_id or organization_id
        require_authenticated_user(actor)
        org = self.db.get_organization_by_id(target_org_id)
        if not org:
            raise ValueError(f"Organization '{target_org_id}' not found.")

        actor_membership = self.db.get_membership(org.id, actor.id) if actor else None
        require_organization_membership(actor, org, actor_membership)

        raw_rows = self.db.list_organization_members(org.id)
        return [r["membership"] for r in raw_rows if "membership" in r]

    def list_organization_members(
        self,
        org_id: str,
        actor: Optional[User] = None,
        organization_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Lists detailed member dictionaries for presentation."""
        target_org_id = org_id or organization_id
        require_authenticated_user(actor)
        org = self.db.get_organization_by_id(target_org_id)
        if not org:
            raise ValueError(f"Organization '{target_org_id}' not found.")

        actor_membership = self.db.get_membership(org.id, actor.id) if actor else None
        require_organization_membership(actor, org, actor_membership)

        return self.db.list_organization_members(org.id)

    def change_member_role(
        self,
        org_id: str,
        user_id: str,
        new_role: str,
        actor: Optional[User] = None,
        organization_id: Optional[str] = None,
        target_user_id: Optional[str] = None
    ) -> OrganizationMembership:
        """Changes a member's role within an organization."""
        target_org_id = org_id or organization_id
        target_uid = user_id or target_user_id
        require_authenticated_user(actor)
        org = self.db.get_organization_by_id(target_org_id)
        if not org:
            raise ValueError(f"Organization '{target_org_id}' not found.")

        actor_membership = self.db.get_membership(org.id, actor.id) if actor else None
        if not can_manage_members(actor, org, actor_membership):
            raise PermissionError("Insufficient role: you do not have permission to modify membership roles in this organization.")

        clean_role = new_role.strip().upper()
        if clean_role not in VALID_ORG_ROLES:
            raise ValueError(f"Invalid role '{new_role}'. Allowed roles: {', '.join(VALID_ORG_ROLES)}")

        target_membership = self.db.get_membership(org.id, target_uid)
        if not target_membership:
            raise ValueError(f"User '{target_uid}' is not a member of organization '{org.name}'.")

        # LAST ACTIVE ORG_ADMIN PROTECTION:
        # If demoting an ORG_ADMIN to non-ORG_ADMIN, ensure at least one other active ORG_ADMIN remains
        if target_membership.role == "ORG_ADMIN" and clean_role != "ORG_ADMIN":
            active_admin_count = self.db.count_active_org_admins(org.id)
            if active_admin_count <= 1:
                raise ValueError("Cannot demote the last active ORG_ADMIN.")

        updated = self.db.update_membership(
            membership_id=target_membership.id,
            role=clean_role
        )

        event_id = f"aud_{uuid.uuid4().hex[:12]}"
        self.db.create_audit_event(
            event_id=event_id,
            organization_id=org.id,
            actor_user_id=actor.id if actor else "system",
            action="MEMBER_ROLE_CHANGED",
            target_type="MEMBERSHIP",
            target_id=target_membership.id,
            metadata={"target_user_id": target_uid, "previous_role": target_membership.role, "new_role": clean_role}
        )

        logger.info("Membership '%s' role changed to %s by %s", target_membership.id, clean_role, actor.username if actor else "system")
        return updated

    def suspend_member(
        self,
        org_id: str,
        user_id: str,
        actor: Optional[User] = None,
        organization_id: Optional[str] = None,
        target_user_id: Optional[str] = None
    ) -> OrganizationMembership:
        """Suspends a user's membership in an organization."""
        target_org_id = org_id or organization_id
        target_uid = user_id or target_user_id
        require_authenticated_user(actor)
        org = self.db.get_organization_by_id(target_org_id)
        if not org:
            raise ValueError(f"Organization '{target_org_id}' not found.")

        actor_membership = self.db.get_membership(org.id, actor.id) if actor else None
        if not can_manage_members(actor, org, actor_membership):
            raise PermissionError("Insufficient role: you do not have permission to suspend members in this organization.")

        target_membership = self.db.get_membership(org.id, target_uid)
        if not target_membership:
            raise ValueError(f"User '{target_uid}' is not a member of organization '{org.name}'.")

        # LAST ACTIVE ORG_ADMIN PROTECTION
        if target_membership.role == "ORG_ADMIN" and target_membership.status == "ACTIVE":
            active_admin_count = self.db.count_active_org_admins(org.id)
            if active_admin_count <= 1:
                raise ValueError("Cannot suspend the last active ORG_ADMIN.")

        updated = self.db.update_membership(
            membership_id=target_membership.id,
            status="SUSPENDED"
        )

        event_id = f"aud_{uuid.uuid4().hex[:12]}"
        self.db.create_audit_event(
            event_id=event_id,
            organization_id=org.id,
            actor_user_id=actor.id if actor else "system",
            action="MEMBER_SUSPENDED",
            target_type="MEMBERSHIP",
            target_id=target_membership.id,
            metadata={"target_user_id": target_uid}
        )

        logger.warning("Membership '%s' suspended by %s", target_membership.id, actor.username if actor else "system")
        return updated

    def reactivate_member(
        self,
        org_id: str,
        user_id: str,
        actor: Optional[User] = None,
        organization_id: Optional[str] = None,
        target_user_id: Optional[str] = None
    ) -> OrganizationMembership:
        """Reactivates a suspended membership."""
        target_org_id = org_id or organization_id
        target_uid = user_id or target_user_id
        require_authenticated_user(actor)
        org = self.db.get_organization_by_id(target_org_id)
        if not org:
            raise ValueError(f"Organization '{target_org_id}' not found.")

        actor_membership = self.db.get_membership(org.id, actor.id) if actor else None
        if not can_manage_members(actor, org, actor_membership):
            raise PermissionError("Insufficient role: you do not have permission to reactivate members in this organization.")

        target_membership = self.db.get_membership(org.id, target_uid)
        if not target_membership:
            raise ValueError(f"User '{target_uid}' is not a member of organization '{org.name}'.")

        updated = self.db.update_membership(
            membership_id=target_membership.id,
            status="ACTIVE"
        )

        event_id = f"aud_{uuid.uuid4().hex[:12]}"
        self.db.create_audit_event(
            event_id=event_id,
            organization_id=org.id,
            actor_user_id=actor.id if actor else "system",
            action="MEMBER_REACTIVATED",
            target_type="MEMBERSHIP",
            target_id=target_membership.id,
            metadata={"target_user_id": target_uid}
        )

        logger.info("Membership '%s' reactivated by %s", target_membership.id, actor.username if actor else "system")
        return updated

    def remove_member(
        self,
        org_id: str,
        user_id: str,
        actor: Optional[User] = None,
        organization_id: Optional[str] = None,
        target_user_id: Optional[str] = None
    ) -> bool:
        """Removes a membership from an organization."""
        target_org_id = org_id or organization_id
        target_uid = user_id or target_user_id
        require_authenticated_user(actor)
        org = self.db.get_organization_by_id(target_org_id)
        if not org:
            raise ValueError(f"Organization '{target_org_id}' not found.")

        actor_membership = self.db.get_membership(org.id, actor.id) if actor else None
        if not can_manage_members(actor, org, actor_membership):
            raise PermissionError("Insufficient role: you do not have permission to remove members from this organization.")

        target_membership = self.db.get_membership(org.id, target_uid)
        if not target_membership:
            raise ValueError(f"User '{target_uid}' is not a member of organization '{org.name}'.")

        # LAST ACTIVE ORG_ADMIN PROTECTION
        if target_membership.role == "ORG_ADMIN" and target_membership.status == "ACTIVE":
            active_admin_count = self.db.count_active_org_admins(org.id)
            if active_admin_count <= 1:
                raise ValueError("Cannot remove the last active ORG_ADMIN.")

        success = self.db.delete_membership(target_membership.id)

        event_id = f"aud_{uuid.uuid4().hex[:12]}"
        self.db.create_audit_event(
            event_id=event_id,
            organization_id=org.id,
            actor_user_id=actor.id if actor else "system",
            action="MEMBER_REMOVED",
            target_type="MEMBERSHIP",
            target_id=target_membership.id,
            metadata={"target_user_id": target_uid, "role": target_membership.role}
        )

        logger.info("Membership '%s' removed by %s", target_membership.id, actor.username if actor else "system")
        return success


# =============================================================================
# TENANT CONTEXT RESOLUTION (SERVER-SIDE)
# =============================================================================

def resolve_tenant_context(
    user: Optional[User],
    requested_org_id: Optional[str] = None,
    requested_slug: Optional[str] = None,
    db: Optional[AuthDatabase] = None
) -> Tuple[Optional[Organization], Optional[OrganizationMembership]]:
    """
    Server-side organization context resolution engine.

    Security Guarantees:
    1. Validates the authenticated user identity server-side.
    2. Resolves organizations only from active, authorized memberships or verified platform admin role.
    3. Rejects suspended organizations and suspended memberships fail-closed.
    4. Client-supplied org_id or slug is NEVER trusted without independent database validation.
    5. Returns (None, None) if the user has no permitted organization access.

    Returns:
        Tuple of (Resolved Organization, Resolved OrganizationMembership)
    """
    require_authenticated_user(user)

    database = db if db is not None else AuthDatabase()

    # Step 1: Identify target organization candidate
    target_org: Optional[Organization] = None

    if requested_org_id:
        target_org = database.get_organization_by_id(requested_org_id)
        if not target_org:
            logger.warning("Tenant context resolution failed: Organization ID '%s' not found.", requested_org_id)
            raise ValueError(f"Organization ID '{requested_org_id}' not found.")
    elif requested_slug:
        target_org = database.get_organization_by_slug(requested_slug)
        if not target_org:
            logger.warning("Tenant context resolution failed: Organization slug '%s' not found.", requested_slug)
            raise ValueError(f"Organization slug '{requested_slug}' not found.")
    else:
        # No specific organization requested: resolve user's primary/first active organization
        user_orgs = database.list_organizations_for_user(user.id, status="ACTIVE")
        if user_orgs:
            target_org = user_orgs[0]
        elif is_platform_admin(user):
            # Platform admin without memberships defaults to first active organization if any exist
            all_orgs = database.list_all_organizations()
            active_orgs = [o for o in all_orgs if o.status == "ACTIVE"]
            if active_orgs:
                target_org = active_orgs[0]

    if not target_org:
        return None, None

    # Step 2: Validate organization status
    if target_org.status == "SUSPENDED":
        logger.warning("Tenant context resolution blocked: Organization '%s' is suspended.", target_org.id)
        raise PermissionError(f"Organization '{target_org.name}' is currently suspended.")

    if target_org.status == "ARCHIVED":
        logger.warning("Tenant context resolution blocked: Organization '%s' is archived.", target_org.id)
        raise PermissionError(f"Organization '{target_org.name}' is archived.")

    # Step 3: Validate user membership in resolved organization
    membership = database.get_membership(target_org.id, user.id)

    # Platform administrators have platform-wide access
    if is_platform_admin(user):
        if not membership:
            # Synthetic virtual membership granting ORG_ADMIN administrative scope
            membership = OrganizationMembership(
                id=f"virt_{user.id}_{target_org.id}",
                organization_id=target_org.id,
                user_id=user.id,
                role="ORG_ADMIN",
                status="ACTIVE",
                joined_at=target_org.created_at,
                created_at=target_org.created_at,
                updated_at=target_org.updated_at
            )
        return target_org, membership

    # Non-platform admin MUST hold an ACTIVE membership
    if not membership:
        logger.warning(
            "Tenant context resolution rejected: User '%s' has no membership in organization '%s'.",
            user.username, target_org.id
        )
        raise PermissionError(f"User '{user.username}' is not an active member of organization '{target_org.name}'.")

    if membership.status != "ACTIVE":
        logger.warning(
            "Tenant context resolution rejected: User '%s' has non-active membership (%s) in organization '%s'.",
            user.username, membership.status, target_org.id
        )
        raise PermissionError(f"Membership of user '{user.username}' in organization '{target_org.name}' is {membership.status}.")

    return target_org, membership
