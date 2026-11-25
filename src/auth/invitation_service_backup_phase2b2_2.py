"""
CrowdPatrol 2.0 — Secure Member Invitation Subsystem
Handles cryptographically secure invitation token generation, SHA-256 token hashing,
single-use acceptance, expiration tracking, anti-escalation enforcement, and SMTP delivery.
"""

import os
import re
import uuid
import secrets
import hashlib
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Tuple

from src.auth.database import (
    AuthDatabase,
    User,
    Organization,
    OrganizationMembership,
    OrganizationInvitation
)
from src.auth.service import AuthService, EMAIL_REGEX, USERNAME_REGEX
from src.auth.organization_service import (
    VALID_ORG_ROLES,
    can_manage_members,
    require_authenticated_user,
)
from src.notification_dispatcher import NotificationConfig

logger = logging.getLogger("crowdpatrol.auth.invitations")


def normalize_email(email: str) -> str:
    """Normalizes an email address to lowercase stripped form."""
    if not email or not isinstance(email, str):
        raise ValueError("Email address cannot be empty.")
    norm = email.strip().lower()
    if not EMAIL_REGEX.match(norm):
        raise ValueError(f"Invalid email address format: '{email}'.")
    return norm


def generate_invitation_token() -> Tuple[str, str]:
    """
    Generates a cryptographically secure random invitation token (32 bytes urlsafe)
    and computes its SHA-256 hash.
    The raw token is transmitted to the recipient; only the token hash is stored in the database.
    """
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    return raw_token, token_hash


def hash_invitation_token(raw_token: str) -> str:
    """Computes SHA-256 hash of a candidate raw invitation token."""
    return hashlib.sha256(raw_token.strip().encode("utf-8")).hexdigest()


# =============================================================================
# INVITATION EMAIL DELIVERY HELPER
# =============================================================================

def send_invitation_email(
    to_email: str,
    org_name: str,
    invited_role: str,
    invite_link: str,
    inviter_username: str,
    config: Optional[NotificationConfig] = None
) -> Tuple[bool, Optional[str]]:
    """
    Delivers an invitation email using the configured SMTP server.
    Reuses existing NotificationConfig to prevent duplicate credential storage.
    Never exposes raw tokens in application logs.
    """
    cfg = config if config is not None else NotificationConfig.from_env()

    if not cfg.is_email_configured:
        logger.warning("SMTP email delivery skipped: SMTP credentials not fully configured in environment.")
        return False, "SMTP email delivery is not configured on this server."

    subject = f"🛡️ CrowdPatrol: Invitation to join {org_name} as {invited_role}"

    text_body = f"""Hello,

You have been invited by {inviter_username} to join '{org_name}' on the CrowdPatrol 2.0 Autonomous Crowd Intelligence Platform.

Assigned Organization Role: {invited_role}
This invitation is valid for 72 hours from the time of issue.

To accept your invitation and access the command center, visit the link below:
{invite_link}

If you did not anticipate this invitation, you may disregard this email.

---
CrowdPatrol 2.0 Security Operations
"""

    html_body = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #060B18; color: #EAF4FF; margin: 0; padding: 24px; }}
    .card {{ max-width: 540px; margin: 0 auto; background: #0B132B; border: 1px solid rgba(0,217,255,0.3); border-radius: 14px; padding: 32px; box-shadow: 0 12px 32px rgba(0,0,0,0.6); }}
    .badge {{ display: inline-block; background: rgba(0,217,255,0.12); color: #00D9FF; border: 1px solid rgba(0,217,255,0.4); padding: 4px 10px; border-radius: 6px; font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; }}
    .btn {{ display: inline-block; background: linear-gradient(135deg, #2563EB 0%, #00D9FF 100%); color: #FFFFFF; font-weight: 700; text-decoration: none; padding: 14px 28px; border-radius: 8px; margin: 24px 0 16px 0; font-size: 15px; box-shadow: 0 4px 20px rgba(0,217,255,0.4); }}
    .meta {{ font-size: 13px; color: #94A3B8; line-height: 1.6; margin-top: 16px; }}
    .footer {{ font-size: 11px; color: #64748B; margin-top: 24px; border-top: 1px solid rgba(255,255,255,0.08); padding-top: 16px; }}
  </style>
</head>
<body>
  <div class="card">
    <div style="font-size: 28px; margin-bottom: 12px;">🛡️</div>
    <h2 style="margin: 0 0 8px 0; color: #FFFFFF; font-size: 22px;">Command Center Invitation</h2>
    <p style="margin: 0 0 18px 0; color: #94A3B8; font-size: 14px;">
      You have been invited by <strong>{inviter_username}</strong> to join <strong>{org_name}</strong> on CrowdPatrol 2.0.
    </p>
    <div style="margin: 16px 0;">
      <span class="badge">ROLE: {invited_role}</span>
    </div>
    <a href="{invite_link}" class="btn">Accept Invitation & Access Workspace</a>
    <div class="meta">
      This invitation is single-use and will expire in <strong>72 hours</strong>.<br>
      If the button above does not work, copy and paste this URL into your browser:<br>
      <code style="word-break: break-all; color: #00D9FF; font-size: 12px;">{invite_link}</code>
    </div>
    <div class="footer">
      CrowdPatrol 2.0 &bull; Autonomous Crowd Monitoring & Public Safety Intelligence
    </div>
  </div>
</body>
</html>
"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = cfg.email_sender or cfg.smtp_username or "noreply@crowdpatrol.internal"
    msg["To"] = to_email
    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        server = smtplib.SMTP(cfg.smtp_host, cfg.smtp_port, timeout=15)
        if cfg.smtp_use_tls:
            server.starttls()
        if cfg.smtp_username and cfg.smtp_password:
            server.login(cfg.smtp_username, cfg.smtp_password)
        server.sendmail(msg["From"], [to_email], msg.as_string())
        server.quit()
        logger.info("Invitation email successfully sent to recipient for organization '%s'.", org_name)
        return True, None
    except Exception as e:
        err_msg = f"Failed to send email via SMTP: {type(e).__name__}: {e}"
        logger.warning(err_msg)
        return False, err_msg


# =============================================================================
# INVITATION SERVICE
# =============================================================================

class InvitationService:
    """
    Business service managing the organization member invitation lifecycle,
    single-use token validation, role constraints, and audit logging.
    """

    def __init__(
        self,
        db: Optional[AuthDatabase] = None,
        auth_service: Optional[AuthService] = None
    ):
        self.db = db if db is not None else AuthDatabase()
        self.auth_service = auth_service if auth_service is not None else AuthService(self.db)

    def create_invitation(
        self,
        actor: User,
        organization_id: str,
        email: str,
        role: str,
        expires_in_hours: int = 72,
        send_email: bool = True,
        base_url: str = "http://localhost:8501"
    ) -> Tuple[OrganizationInvitation, str, Optional[str]]:
        """
        Creates and registers a new organization member invitation.

        Security Guarantees:
        1. Verifies actor holds ORG_ADMIN or PLATFORM_ADMIN role in the target org.
        2. Strictly blocks elevation to PLATFORM_ADMIN or SUPER_ADMIN (must be in VALID_ORG_ROLES).
        3. Prevents duplicate pending invitations for the same email and organization.
        4. Rejects invitations if the email is already an active member of the organization.
        5. Computes SHA-256 hash of the 32-byte cryptographically secure token; raw token is NEVER persisted.
        6. Logs an INVITATION_CREATED audit event without leaking the token.

        Returns:
            Tuple of (OrganizationInvitation record, raw_token: str, delivery_error: Optional[str])
        """
        require_authenticated_user(actor)
        org = self.db.get_organization_by_id(organization_id)
        if not org:
            raise ValueError(f"Organization '{organization_id}' not found.")

        if org.status != "ACTIVE":
            raise PermissionError(f"Cannot invite members to a {org.status.lower()} organization.")

        actor_membership = self.db.get_membership(org.id, actor.id)
        if not can_manage_members(actor, org, actor_membership):
            raise PermissionError("Insufficient role: you do not have permission to invite members to this organization.")

        # Validate and normalize email
        norm_email = normalize_email(email)

        # Validate role (STRICT ANTI-ESCALATION: VALID_ORG_ROLES only)
        clean_role = role.strip().upper()
        if clean_role not in VALID_ORG_ROLES:
            raise ValueError(f"Invalid invitation role '{role}'. Allowed roles: {', '.join(VALID_ORG_ROLES)}")

        # Check if an account with this email is ALREADY an active member of the organization
        existing_user = self.db.get_user_by_identity(norm_email)
        if existing_user:
            existing_membership = self.db.get_membership(org.id, existing_user.id)
            if existing_membership and existing_membership.status == "ACTIVE":
                raise ValueError(f"User '{norm_email}' is already an active member of '{org.name}'.")

        # Check for existing PENDING invitation for this org and email
        existing_pending = self.db.get_pending_invitation(org.id, norm_email)
        if existing_pending:
            raise ValueError(f"A pending invitation already exists for '{norm_email}' in '{org.name}'.")

        # Generate cryptographically secure token and hash
        raw_token, token_hash = generate_invitation_token()

        # Set expiration
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=max(1, expires_in_hours))

        invitation_id = f"inv_{uuid.uuid4().hex[:12]}"
        invitation = self.db.create_invitation(
            invitation_id=invitation_id,
            organization_id=org.id,
            normalized_email=norm_email,
            invited_role=clean_role,
            token_hash=token_hash,
            invited_by=actor.id,
            expires_at=expires_at
        )

        # Non-repudiable audit event (NEVER include token)
        event_id = f"aud_{uuid.uuid4().hex[:12]}"
        self.db.create_audit_event(
            event_id=event_id,
            organization_id=org.id,
            actor_user_id=actor.id,
            action="INVITATION_CREATED",
            target_type="INVITATION",
            target_id=invitation.id,
            metadata={
                "invited_email": norm_email,
                "role": clean_role,
                "expires_at": expires_at.isoformat()
            }
        )

        logger.info(
            "Created invitation '%s' for '%s' to org '%s' as %s by %s",
            invitation.id, norm_email, org.name, clean_role, actor.username
        )

        # Email delivery
        delivery_error = None
        if send_email:
            invite_url = f"{base_url.rstrip('/')}/?page=accept_invite&token={raw_token}"
            delivered, err = send_invitation_email(
                to_email=norm_email,
                org_name=org.name,
                invited_role=clean_role,
                invite_link=invite_url,
                inviter_username=actor.username
            )
            if not delivered:
                delivery_error = err

        return invitation, raw_token, delivery_error

    def revoke_invitation(
        self,
        actor: User,
        invitation_id: str
    ) -> OrganizationInvitation:
        """Revokes a pending invitation."""
        require_authenticated_user(actor)
        invitation = self.db.get_invitation_by_id(invitation_id)
        if not invitation:
            raise ValueError(f"Invitation '{invitation_id}' not found.")

        org = self.db.get_organization_by_id(invitation.organization_id)
        if not org:
            raise ValueError("Associated organization not found.")

        actor_membership = self.db.get_membership(org.id, actor.id)
        if not can_manage_members(actor, org, actor_membership):
            raise PermissionError("Insufficient role: you do not have permission to revoke invitations for this organization.")

        if invitation.status != "PENDING":
            raise ValueError(f"Cannot revoke invitation with status '{invitation.status}'.")

        updated = self.db.update_invitation_status(
            invitation_id=invitation.id,
            status="REVOKED",
            timestamp_field="revoked_at"
        )

        event_id = f"aud_{uuid.uuid4().hex[:12]}"
        self.db.create_audit_event(
            event_id=event_id,
            organization_id=org.id,
            actor_user_id=actor.id,
            action="INVITATION_REVOKED",
            target_type="INVITATION",
            target_id=invitation.id,
            metadata={"invited_email": invitation.normalized_email}
        )

        logger.info("Invitation '%s' revoked by %s", invitation.id, actor.username)
        return updated  # type: ignore

    def list_invitations(
        self,
        actor: User,
        organization_id: str,
        status: Optional[str] = None
    ) -> List[OrganizationInvitation]:
        """Lists invitations for an organization, auto-expiring overdue pending items."""
        require_authenticated_user(actor)
        org = self.db.get_organization_by_id(organization_id)
        if not org:
            raise ValueError(f"Organization '{organization_id}' not found.")

        actor_membership = self.db.get_membership(org.id, actor.id)
        if not can_manage_members(actor, org, actor_membership):
            raise PermissionError("Insufficient role: you do not have permission to view invitations.")

        invitations = self.db.list_organization_invitations(org.id, status=status)
        now = datetime.now(timezone.utc)

        # Auto-expire overdue pending invitations
        active_list = []
        for inv in invitations:
            if inv.status == "PENDING" and inv.expires_at <= now:
                self.db.update_invitation_status(inv.id, "EXPIRED")
                inv.status = "EXPIRED"
            active_list.append(inv)

        return active_list

    def validate_invitation_token(
        self,
        raw_token: str
    ) -> Tuple[Optional[OrganizationInvitation], Optional[Organization], str]:
        """
        Validates an incoming raw invitation token.

        Returns:
            Tuple of (OrganizationInvitation, Organization, error_message: str)
            If valid, error_message is empty string ("").
        """
        if not raw_token or not isinstance(raw_token, str) or len(raw_token.strip()) < 16:
            return None, None, "Invalid or malformed invitation token."

        token_hash = hash_invitation_token(raw_token)
        invitation = self.db.get_invitation_by_token_hash(token_hash)

        if not invitation:
            return None, None, "Invalid or unrecognized invitation token."

        if invitation.status == "ACCEPTED":
            return None, None, "This invitation has already been accepted."

        if invitation.status == "REVOKED":
            return None, None, "This invitation has been revoked by an administrator."

        now = datetime.now(timezone.utc)
        if invitation.expires_at <= now:
            if invitation.status == "PENDING":
                self.db.update_invitation_status(invitation.id, "EXPIRED")
                invitation.status = "EXPIRED"
            return None, None, "This invitation has expired."

        org = self.db.get_organization_by_id(invitation.organization_id)
        if not org:
            return None, None, "The organization associated with this invitation no longer exists."

        if org.status == "SUSPENDED":
            return None, None, f"Organization '{org.name}' is currently suspended."

        if org.status == "ARCHIVED":
            return None, None, f"Organization '{org.name}' has been archived."

        return invitation, org, ""

    def accept_invitation(
        self,
        raw_token: str,
        user: Optional[User] = None,
        new_user_credentials: Optional[Dict[str, str]] = None
    ) -> Tuple[bool, Optional[OrganizationMembership], str]:
        """
        Executes single-use atomic acceptance of an invitation.

        Acceptance Modes:
        1. Existing logged-in User: `user` must match `invitation.normalized_email`.
        2. New User Registration: `new_user_credentials` must provide `username` and `password`.
           The new account is registered with `email=invitation.normalized_email` and Scrypt hashing.

        Security Guarantees:
        - Atomic transition from PENDING to ACCEPTED and creation of OrganizationMembership.
        - Rejection of email mismatches.
        - Single-use guarantee: Re-acceptance is blocked.
        - Role constrained strictly to `invitation.invited_role`.

        Returns:
            Tuple of (success: bool, OrganizationMembership, error_message: str)
        """
        invitation, org, err = self.validate_invitation_token(raw_token)
        if err or not invitation or not org:
            return False, None, err

        target_user: Optional[User] = None

        if user:
            # Existing authenticated user acceptance
            if user.email.lower() != invitation.normalized_email:
                return (
                    False,
                    None,
                    f"Signed-in account email '{user.email}' does not match invitation recipient '{invitation.normalized_email}'."
                )
            target_user = user
        elif new_user_credentials:
            # New user account registration
            username = new_user_credentials.get("username", "").strip()
            password = new_user_credentials.get("password", "")

            try:
                target_user = self.auth_service.register_user(
                    username=username,
                    email=invitation.normalized_email,
                    password=password,
                    role="USER"
                )
            except ValueError as ve:
                return False, None, str(ve)
        else:
            return False, None, "Authentication or account registration credentials required to accept invitation."

        if not target_user:
            return False, None, "Failed to resolve target user identity."

        membership_id = f"mem_{uuid.uuid4().hex[:12]}"
        success = self.db.atomic_accept_invitation(
            invitation_id=invitation.id,
            membership_id=membership_id,
            user_id=target_user.id,
            organization_id=org.id,
            role=invitation.invited_role
        )

        if not success:
            return False, None, "Invitation acceptance failed. The invitation may have expired or already been accepted."

        membership = self.db.get_membership(org.id, target_user.id)

        # Audit events
        event_id = f"aud_{uuid.uuid4().hex[:12]}"
        self.db.create_audit_event(
            event_id=event_id,
            organization_id=org.id,
            actor_user_id=target_user.id,
            action="INVITATION_ACCEPTED",
            target_type="INVITATION",
            target_id=invitation.id,
            metadata={"user_id": target_user.id, "role": invitation.invited_role}
        )

        self.db.create_audit_event(
            event_id=f"aud_{uuid.uuid4().hex[:12]}",
            organization_id=org.id,
            actor_user_id=target_user.id,
            action="MEMBER_ADDED",
            target_type="MEMBERSHIP",
            target_id=membership.id if membership else membership_id,
            metadata={"via_invitation": invitation.id, "role": invitation.invited_role}
        )

        logger.info(
            "User '%s' accepted invitation '%s' to organization '%s' as %s",
            target_user.username, invitation.id, org.name, invitation.invited_role
        )

        return True, membership, ""
