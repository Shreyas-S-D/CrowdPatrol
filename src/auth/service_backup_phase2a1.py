"""
CrowdPatrol 2.0 — Authentication Business Service
Encapsulates user provisioning, credential verification, rate-limiting & lockout,
session lifecycle, anti-fixation rotation, and zero-knowledge session validation.
"""

import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple, Dict, Any

from src.auth.crypto import (
    hash_password,
    verify_password,
    generate_session_token,
    hash_session_token
)
from src.auth.database import AuthDatabase, User, SessionRecord


# Security Constants
MAX_FAILED_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 15
SESSION_TTL_HOURS = 4
MAX_SESSION_AGE_HOURS = 12

USERNAME_REGEX = re.compile(r"^[a-zA-Z0-9_.-]{3,32}$")
EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


class AuthService:
    """
    Core security service for user authentication, session verification,
    and administrative provisioning.
    """

    def __init__(self, db: Optional[AuthDatabase] = None):
        self.db = db if db is not None else AuthDatabase()

    # =========================================================================
    # USER REGISTRATION & PROVISIONING
    # =========================================================================

    def register_user(
        self,
        username: str,
        email: str,
        password: str,
        role: str = "OPERATOR"
    ) -> User:
        """
        Controlled user provisioning. Normalizes identity, validates constraints,
        and persists Scrypt password hash.
        """
        if not username or not USERNAME_REGEX.match(username.strip()):
            raise ValueError(
                "Username must be 3-32 characters and contain only letters, numbers, underscores, dots, or dashes."
            )

        if not email or not EMAIL_REGEX.match(email.strip()):
            raise ValueError("Invalid email address format.")

        if not password or len(password) < 8:
            raise ValueError("Password must be at least 8 characters long.")

        norm_username = username.strip().lower()
        norm_email = email.strip().lower()

        # Check existing identity to give precise provisioning errors
        existing_user = self.db.get_user_by_identity(norm_username)
        if existing_user and existing_user.username == norm_username:
            raise ValueError(f"Username '{norm_username}' is already registered.")

        existing_email = self.db.get_user_by_identity(norm_email)
        if existing_email and existing_email.email == norm_email:
            raise ValueError(f"Email '{norm_email}' is already registered.")

        # Hash password using Scrypt
        pw_hash = hash_password(password)
        user_id = f"usr_{uuid.uuid4().hex[:12]}"

        return self.db.create_user(
            user_id=user_id,
            username=norm_username,
            email=norm_email,
            password_hash=pw_hash,
            role=role.upper()
        )

    # =========================================================================
    # AUTHENTICATION & LOGIN
    # =========================================================================

    def authenticate(
        self,
        identity: str,
        password: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Tuple[Optional[User], Optional[str], Optional[str]]:
        """
        Authenticates a user by username or email.
        Applies progressive rate limiting and account lockout.
        Returns:
            Tuple of (User or None, Raw Session Token or None, Error Message or None)
        """
        if not identity or not password:
            return None, None, "Invalid credentials."

        norm_identity = identity.strip().lower()
        user = self.db.get_user_by_identity(norm_identity)

        # Constant-time dummy verification if user doesn't exist (prevents timing enumeration)
        if not user:
            # Run dummy scrypt hash to prevent timing attacks
            verify_password(password, "$scrypt$N=16384,r=8,p=1$00112233445566778899aabbccddeeff$00")
            return None, None, "Invalid credentials."

        now = datetime.now(timezone.utc)

        # Check account lockout
        if user.locked_until and user.locked_until > now:
            remaining_mins = int((user.locked_until - now).total_seconds() / 60) + 1
            return None, None, f"Account is temporarily locked due to multiple failed login attempts. Please try again in {remaining_mins} minutes."

        # Check active status
        if not user.is_active:
            return None, None, "Account is disabled. Please contact your administrator."

        # Verify password with constant-time Scrypt comparison
        pw_valid = verify_password(password, user.password_hash)

        if not pw_valid:
            new_failed = user.failed_login_attempts + 1
            locked_until = None
            error_msg = "Invalid credentials."

            if new_failed >= MAX_FAILED_LOGIN_ATTEMPTS:
                locked_until = now + timedelta(minutes=LOCKOUT_DURATION_MINUTES)
                error_msg = f"Account is temporarily locked due to multiple failed login attempts. Please try again in {LOCKOUT_DURATION_MINUTES} minutes."

            self.db.update_login_failure(user.id, new_failed, locked_until)
            return None, None, error_msg

        # Reset failed attempts on success
        if user.failed_login_attempts > 0 or user.locked_until is not None:
            self.db.reset_login_lockout(user.id)

        # Session Rotation & Anti-Fixation:
        # Invalidate any previously active sessions for this device if needed,
        # and create a brand-new high-entropy cryptographic token
        raw_token = generate_session_token()
        token_hash = hash_session_token(raw_token)
        session_id = f"ses_{uuid.uuid4().hex[:12]}"
        expires_at = now + timedelta(hours=SESSION_TTL_HOURS)

        self.db.create_session(
            session_id=session_id,
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent
        )

        return user, raw_token, None

    # =========================================================================
    # SESSION VALIDATION & REVOCATION
    # =========================================================================

    def validate_session(self, raw_token: Optional[str]) -> Optional[User]:
        """
        Validates an incoming bearer session token.
        Computes SHA-256 hash to query the database, ensuring zero-knowledge persistence.
        Applies expiration check and sliding activity window.
        """
        if not raw_token or not isinstance(raw_token, str):
            return None

        try:
            token_hash = hash_session_token(raw_token)
        except Exception:
            return None

        session = self.db.get_session_by_token_hash(token_hash)
        if not session or session.is_revoked:
            return None

        now = datetime.now(timezone.utc)

        # Check expiration
        if session.expires_at <= now:
            # Mark expired session as revoked
            self.db.revoke_session_by_hash(token_hash)
            return None

        # Check maximum absolute session lifetime
        max_absolute_expiry = session.created_at + timedelta(hours=MAX_SESSION_AGE_HOURS)
        if now > max_absolute_expiry:
            self.db.revoke_session_by_hash(token_hash)
            return None

        # Verify user still exists and is active
        user = self.db.get_user_by_id(session.user_id)
        if not user or not user.is_active:
            self.db.revoke_session_by_hash(token_hash)
            return None

        # Slide activity window if needed (once every 5 minutes to minimize DB writes)
        if (now - session.last_activity_at).total_seconds() > 300:
            self.db.update_session_activity(session.id, now)

        return user

    def revoke_session(self, raw_token: Optional[str]) -> bool:
        """Revokes an active session by token (Logout)."""
        if not raw_token:
            return False
        try:
            token_hash = hash_session_token(raw_token)
            return self.db.revoke_session_by_hash(token_hash)
        except Exception:
            return False

    def revoke_all_user_sessions(self, user_id: str) -> int:
        """Revokes all active sessions for a user (e.g. after password reset)."""
        return self.db.revoke_all_user_sessions(user_id)
