"""
CrowdPatrol 2.0 — Dedicated Authentication Database Layer
Transaction-safe SQLite database manager with WAL mode, foreign keys,
schema versioning, and parameterized queries.
Designed for zero-credential logging and seamless migration to PostgreSQL.
"""

import os
import json
import sqlite3
from pathlib import Path
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List, Generator, Tuple
from dataclasses import dataclass


DEFAULT_DB_PATH = Path(__file__).parent.parent.parent / "data" / "crowdpatrol_auth.db"


@dataclass
class User:
    id: str
    username: str
    email: str
    password_hash: str
    role: str
    is_active: bool
    failed_login_attempts: int
    locked_until: Optional[datetime]
    created_at: datetime
    updated_at: datetime


@dataclass
class SessionRecord:
    id: str
    user_id: str
    token_hash: str
    ip_address: Optional[str]
    user_agent: Optional[str]
    created_at: datetime
    last_activity_at: datetime
    expires_at: datetime
    is_revoked: bool


@dataclass
class Organization:
    id: str
    name: str
    slug: str
    description: Optional[str]
    status: str
    created_at: datetime
    updated_at: datetime
    created_by: str


@dataclass
class OrganizationMembership:
    id: str
    organization_id: str
    user_id: str
    role: str
    status: str
    joined_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime


@dataclass
class OrganizationAuditEvent:
    id: str
    organization_id: str
    actor_user_id: str
    action: str
    target_type: str
    target_id: str
    metadata: Dict[str, Any]
    created_at: datetime


@dataclass
class OrganizationInvitation:
    id: str
    organization_id: str
    normalized_email: str
    invited_role: str
    token_hash: str
    invited_by: str
    status: str  # PENDING, ACCEPTED, EXPIRED, REVOKED
    expires_at: datetime
    accepted_at: Optional[datetime]
    revoked_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime


class AuthDatabase:
    """
    Manages persistent SQLite storage for user accounts and authentication sessions.
    Thread-safe connection handling, explicit transaction isolation, and schema migrations.
    """

    SCHEMA_VERSION = 3

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            self.db_path = str(DEFAULT_DB_PATH)
        else:
            self.db_path = str(db_path)

        if self.db_path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)

        self._init_database()

    def _get_connection(self) -> sqlite3.Connection:
        """Creates a configured connection with foreign keys and row factory."""
        conn = sqlite3.connect(
            self.db_path,
            timeout=30.0,
            check_same_thread=False
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        if self.db_path != ":memory:":
            conn.execute("PRAGMA journal_mode = WAL;")
            conn.execute("PRAGMA synchronous = NORMAL;")
        return conn

    @contextmanager
    def transaction(self) -> Generator[sqlite3.Cursor, None, None]:
        """
        Context manager for transaction-safe operations.
        Commits on clean exit, rolls back on exception.
        """
        conn = self._get_connection()
        try:
            conn.execute("BEGIN IMMEDIATE;")
            cursor = conn.cursor()
            yield cursor
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_database(self) -> None:
        """Initializes database schema and applies pending migrations."""
        with self.transaction() as cur:
            # 1. Migrations table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    description TEXT NOT NULL
                );
            """)

            # Check applied version
            cur.execute("SELECT MAX(version) FROM schema_migrations;")
            row = cur.fetchone()
            current_ver = row[0] if (row and row[0] is not None) else 0

            if current_ver < 1:
                self._apply_migration_v1(cur)
            if current_ver < 2:
                self._apply_migration_v2(cur)
            if current_ver < 3:
                self._apply_migration_v3(cur)

    def _apply_migration_v1(self, cur: sqlite3.Cursor) -> None:
        """Migration 1: Base authentication schema."""
        # 1. Users table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'OPERATOR',
                is_active INTEGER NOT NULL DEFAULT 1,
                failed_login_attempts INTEGER NOT NULL DEFAULT 0,
                locked_until TIMESTAMP NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 2. Authentication sessions table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS authentication_sessions (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                token_hash TEXT UNIQUE NOT NULL,
                ip_address TEXT NULL,
                user_agent TEXT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_activity_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL,
                is_revoked INTEGER NOT NULL DEFAULT 0
            );
        """)

        # 3. Password reset tokens table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS password_reset_tokens (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                token_hash TEXT UNIQUE NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                used_at TIMESTAMP NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 4. Indexes for rapid lookups and constraints
        cur.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_sessions_token_hash ON authentication_sessions(token_hash);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON authentication_sessions(user_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON authentication_sessions(expires_at);")

        cur.execute("""
            INSERT INTO schema_migrations (version, description)
            VALUES (1, 'Initial base authentication schema: users, sessions, password_resets');
        """)

    def _apply_migration_v2(self, cur: sqlite3.Cursor) -> None:
        """Migration 2: Organizations, Organization Memberships, and Audit Events."""
        # 1. Organizations table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS organizations (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                slug TEXT UNIQUE NOT NULL,
                description TEXT NULL,
                status TEXT NOT NULL DEFAULT 'ACTIVE',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_by TEXT NOT NULL REFERENCES users(id)
            );
        """)

        # 2. Organization memberships table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS organization_memberships (
                id TEXT PRIMARY KEY,
                organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                role TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'ACTIVE',
                joined_at TIMESTAMP NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (organization_id, user_id)
            );
        """)

        # 3. Organization audit events table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS organization_audit_events (
                id TEXT PRIMARY KEY,
                organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
                actor_user_id TEXT NOT NULL REFERENCES users(id),
                action TEXT NOT NULL,
                target_type TEXT NOT NULL,
                target_id TEXT NOT NULL,
                metadata TEXT NOT NULL DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 4. Indexes for rapid lookups and constraints
        cur.execute("CREATE INDEX IF NOT EXISTS idx_organizations_slug ON organizations(slug);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_organizations_status ON organizations(status);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_memberships_org_id ON organization_memberships(organization_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_memberships_user_id ON organization_memberships(user_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_memberships_status ON organization_memberships(status);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_audit_org_id ON organization_audit_events(organization_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_audit_actor ON organization_audit_events(actor_user_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_audit_created_at ON organization_audit_events(created_at);")

        cur.execute("""
            INSERT INTO schema_migrations (version, description)
            VALUES (2, 'Organization and membership foundation: organizations, memberships, audit events');
        """)

    def _apply_migration_v3(self, cur: sqlite3.Cursor) -> None:
        """Migration 3: Organization invitations and invitation lookup indexes."""
        cur.execute("""
            CREATE TABLE IF NOT EXISTS organization_invitations (
                id TEXT PRIMARY KEY,
                organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
                normalized_email TEXT NOT NULL,
                invited_role TEXT NOT NULL,
                token_hash TEXT UNIQUE NOT NULL,
                invited_by TEXT NOT NULL REFERENCES users(id),
                status TEXT NOT NULL DEFAULT 'PENDING',
                expires_at TIMESTAMP NOT NULL,
                accepted_at TIMESTAMP NULL,
                revoked_at TIMESTAMP NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_invitations_token_hash ON organization_invitations(token_hash);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_invitations_org_id ON organization_invitations(organization_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_invitations_email ON organization_invitations(normalized_email);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_invitations_status ON organization_invitations(status);")

        cur.execute("""
            INSERT INTO schema_migrations (version, description)
            VALUES (3, 'Secure invitation system: organization_invitations table and lookup indexes');
        """)

    # =========================================================================
    # USER OPERATIONS
    # =========================================================================

    def create_user(
        self,
        user_id: str,
        username: str,
        email: str,
        password_hash: str,
        role: str = "OPERATOR"
    ) -> User:
        """Inserts a new user with normalized identity fields."""
        norm_username = username.strip().lower()
        norm_email = email.strip().lower()
        now_iso = datetime.now(timezone.utc).isoformat()

        with self.transaction() as cur:
            cur.execute("""
                INSERT INTO users (
                    id, username, email, password_hash, role, is_active,
                    failed_login_attempts, locked_until, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 1, 0, NULL, ?, ?)
            """, (user_id, norm_username, norm_email, password_hash, role, now_iso, now_iso))

        return self.get_user_by_id(user_id)  # type: ignore

    def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Retrieves a user by ID."""
        with self.transaction() as cur:
            cur.execute("SELECT * FROM users WHERE id = ?;", (user_id,))
            row = cur.fetchone()
            if not row:
                return None
            return self._row_to_user(row)

    def get_user_by_identity(self, identity: str) -> Optional[User]:
        """Retrieves a user by normalized username OR normalized email."""
        norm_id = identity.strip().lower()
        with self.transaction() as cur:
            cur.execute(
                "SELECT * FROM users WHERE username = ? OR email = ?;",
                (norm_id, norm_id)
            )
            row = cur.fetchone()
            if not row:
                return None
            return self._row_to_user(row)

    def record_login_failure(
        self,
        user_id: str,
        max_attempts: int = 5,
        lockout_minutes: int = 15
    ) -> Tuple[int, Optional[datetime]]:
        """
        Atomically increments failed_login_attempts in the database and sets locked_until
        if the threshold is reached or exceeded.
        If a previous lockout has expired, resets the counter to 1 and clears the expired lockout.
        Uses BEGIN IMMEDIATE write transaction to prevent lost updates under concurrency.

        Returns:
            Tuple of (new_failed_attempts: int, locked_until: Optional[datetime])
        """
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()
        lockout_until = now + timedelta(minutes=lockout_minutes)
        lockout_iso = lockout_until.isoformat()

        with self.transaction() as cur:
            cur.execute(
                "SELECT failed_login_attempts, locked_until FROM users WHERE id = ?;",
                (user_id,)
            )
            row = cur.fetchone()
            if not row:
                return 0, None

            current_failed = int(row["failed_login_attempts"])
            current_locked = self._parse_dt(row["locked_until"])

            if current_locked and current_locked <= now:
                # Previous lockout has expired; start fresh attempt counter
                new_failed = 1
                locked_dt = None
                new_locked_iso = None
            else:
                new_failed = current_failed + 1
                if new_failed >= max_attempts:
                    locked_dt = lockout_until
                    new_locked_iso = lockout_iso
                else:
                    locked_dt = current_locked
                    new_locked_iso = current_locked.isoformat() if current_locked else None

            cur.execute("""
                UPDATE users
                SET failed_login_attempts = ?, locked_until = ?, updated_at = ?
                WHERE id = ?;
            """, (new_failed, new_locked_iso, now_iso, user_id))

            return new_failed, locked_dt

    def update_login_failure(
        self,
        user_id: str,
        failed_attempts: int,
        locked_until: Optional[datetime]
    ) -> None:
        """Updates failed login attempts counter and lockout timestamp."""
        now_iso = datetime.now(timezone.utc).isoformat()
        locked_iso = locked_until.isoformat() if locked_until else None
        with self.transaction() as cur:
            cur.execute("""
                UPDATE users
                SET failed_login_attempts = ?, locked_until = ?, updated_at = ?
                WHERE id = ?;
            """, (failed_attempts, locked_iso, now_iso, user_id))

    def reset_login_lockout(self, user_id: str) -> None:
        """Resets failed login attempts counter and removes lockout upon successful login."""
        now_iso = datetime.now(timezone.utc).isoformat()
        with self.transaction() as cur:
            cur.execute("""
                UPDATE users
                SET failed_login_attempts = 0, locked_until = NULL, updated_at = ?
                WHERE id = ?;
            """, (now_iso, user_id))

    # =========================================================================
    # SESSION OPERATIONS
    # =========================================================================

    def create_session(
        self,
        session_id: str,
        user_id: str,
        token_hash: str,
        expires_at: datetime,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> SessionRecord:
        """Persists a new active authentication session record with hashed token."""
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()
        exp_iso = expires_at.isoformat()
        with self.transaction() as cur:
            cur.execute("""
                INSERT INTO authentication_sessions (
                    id, user_id, token_hash, ip_address, user_agent,
                    created_at, last_activity_at, expires_at, is_revoked
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0);
            """, (session_id, user_id, token_hash, ip_address, user_agent, now_iso, now_iso, exp_iso))

        return SessionRecord(
            id=session_id,
            user_id=user_id,
            token_hash=token_hash,
            ip_address=ip_address,
            user_agent=user_agent,
            created_at=now,
            last_activity_at=now,
            expires_at=expires_at,
            is_revoked=False
        )

    def get_session_by_token_hash(self, token_hash: str) -> Optional[SessionRecord]:
        """Retrieves an active session record by its SHA-256 token hash."""
        with self.transaction() as cur:
            cur.execute(
                "SELECT * FROM authentication_sessions WHERE token_hash = ?;",
                (token_hash,)
            )
            row = cur.fetchone()
            if not row:
                return None
            return self._row_to_session(row)

    def update_session_activity(self, session_id: str, now: datetime) -> None:
        """Updates last_activity_at for sliding session validity."""
        with self.transaction() as cur:
            cur.execute(
                "UPDATE authentication_sessions SET last_activity_at = ? WHERE id = ?;",
                (now.isoformat(), session_id)
            )

    def revoke_session_by_hash(self, token_hash: str) -> bool:
        """Revokes a session by marking is_revoked = 1."""
        with self.transaction() as cur:
            cur.execute(
                "UPDATE authentication_sessions SET is_revoked = 1 WHERE token_hash = ?;",
                (token_hash,)
            )
            return cur.rowcount > 0

    def revoke_all_user_sessions(self, user_id: str) -> int:
        """Revokes all active sessions for a given user (anti-fixation & logout everywhere)."""
        with self.transaction() as cur:
            cur.execute(
                "UPDATE authentication_sessions SET is_revoked = 1 WHERE user_id = ? AND is_revoked = 0;",
                (user_id,)
            )
            return cur.rowcount

    # =========================================================================
    # ORGANIZATION OPERATIONS
    # =========================================================================

    def create_organization(
        self,
        org_id: str,
        name: str,
        slug: str,
        created_by: str,
        description: Optional[str] = None,
        status: str = "ACTIVE"
    ) -> Organization:
        """Persists a new organization."""
        now_iso = datetime.now(timezone.utc).isoformat()
        with self.transaction() as cur:
            cur.execute("""
                INSERT INTO organizations (
                    id, name, slug, description, status, created_at, updated_at, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """, (org_id, name, slug, description, status, now_iso, now_iso, created_by))

        return self.get_organization_by_id(org_id)  # type: ignore

    def get_organization_by_id(self, org_id: str) -> Optional[Organization]:
        """Retrieves an organization by ID."""
        with self.transaction() as cur:
            cur.execute("SELECT * FROM organizations WHERE id = ?;", (org_id,))
            row = cur.fetchone()
            if not row:
                return None
            return self._row_to_organization(row)

    def get_organization_by_slug(self, slug: str) -> Optional[Organization]:
        """Retrieves an organization by normalized slug."""
        norm_slug = slug.strip().lower()
        with self.transaction() as cur:
            cur.execute("SELECT * FROM organizations WHERE slug = ?;", (norm_slug,))
            row = cur.fetchone()
            if not row:
                return None
            return self._row_to_organization(row)

    def list_all_organizations(self) -> List[Organization]:
        """Lists all organizations on the platform."""
        with self.transaction() as cur:
            cur.execute("SELECT * FROM organizations ORDER BY name ASC;")
            rows = cur.fetchall()
            return [self._row_to_organization(row) for row in rows]

    def list_organizations_for_user(self, user_id: str, status: Optional[str] = None) -> List[Organization]:
        """Lists all organizations where a user has an active membership."""
        with self.transaction() as cur:
            if status:
                cur.execute("""
                    SELECT o.* FROM organizations o
                    JOIN organization_memberships m ON o.id = m.organization_id
                    WHERE m.user_id = ? AND m.status = 'ACTIVE' AND o.status = ?
                    ORDER BY o.name ASC;
                """, (user_id, status))
            else:
                cur.execute("""
                    SELECT o.* FROM organizations o
                    JOIN organization_memberships m ON o.id = m.organization_id
                    WHERE m.user_id = ? AND m.status = 'ACTIVE' AND o.status != 'ARCHIVED'
                    ORDER BY o.name ASC;
                """, (user_id,))
            rows = cur.fetchall()
            return [self._row_to_organization(row) for row in rows]

    def update_organization(
        self,
        org_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        status: Optional[str] = None
    ) -> Optional[Organization]:
        """Updates organization fields dynamically."""
        updates = []
        params = []
        if name is not None:
            updates.append("name = ?")
            params.append(name)
        if description is not None:
            updates.append("description = ?")
            params.append(description)
        if status is not None:
            updates.append("status = ?")
            params.append(status)

        if not updates:
            return self.get_organization_by_id(org_id)

        now_iso = datetime.now(timezone.utc).isoformat()
        updates.append("updated_at = ?")
        params.append(now_iso)

        params.append(org_id)
        with self.transaction() as cur:
            cur.execute(f"""
                UPDATE organizations
                SET {', '.join(updates)}
                WHERE id = ?;
            """, tuple(params))

        return self.get_organization_by_id(org_id)

    # =========================================================================
    # MEMBERSHIP OPERATIONS
    # =========================================================================

    def create_membership(
        self,
        membership_id: str,
        organization_id: str,
        user_id: str,
        role: str,
        status: str = "ACTIVE",
        joined_at: Optional[datetime] = None
    ) -> OrganizationMembership:
        """Creates an organization membership."""
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()
        joined_iso = (joined_at or now).isoformat() if status == "ACTIVE" else None

        with self.transaction() as cur:
            cur.execute("""
                INSERT INTO organization_memberships (
                    id, organization_id, user_id, role, status, joined_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """, (membership_id, organization_id, user_id, role, status, joined_iso, now_iso, now_iso))

        return self.get_membership_by_id(membership_id)  # type: ignore

    def get_membership(self, organization_id: str, user_id: str) -> Optional[OrganizationMembership]:
        """Retrieves a membership by organization ID and user ID."""
        with self.transaction() as cur:
            cur.execute("""
                SELECT * FROM organization_memberships
                WHERE organization_id = ? AND user_id = ?;
            """, (organization_id, user_id))
            row = cur.fetchone()
            if not row:
                return None
            return self._row_to_membership(row)

    def get_membership_by_id(self, membership_id: str) -> Optional[OrganizationMembership]:
        """Retrieves a membership by ID."""
        with self.transaction() as cur:
            cur.execute("SELECT * FROM organization_memberships WHERE id = ?;", (membership_id,))
            row = cur.fetchone()
            if not row:
                return None
            return self._row_to_membership(row)

    def list_organization_members(self, organization_id: str) -> List[Dict[str, Any]]:
        """Lists all members of an organization with user identity details."""
        with self.transaction() as cur:
            cur.execute("""
                SELECT m.*, u.username, u.email, u.is_active as user_is_active
                FROM organization_memberships m
                JOIN users u ON m.user_id = u.id
                WHERE m.organization_id = ?
                ORDER BY m.created_at ASC;
            """, (organization_id,))
            rows = cur.fetchall()
            result = []
            for row in rows:
                result.append({
                    "membership": self._row_to_membership(row),
                    "username": row["username"],
                    "email": row["email"],
                    "user_is_active": bool(row["user_is_active"])
                })
            return result

    def list_user_memberships(self, user_id: str, status: Optional[str] = None) -> List[OrganizationMembership]:
        """Lists all memberships belonging to a user."""
        with self.transaction() as cur:
            if status:
                cur.execute("""
                    SELECT * FROM organization_memberships
                    WHERE user_id = ? AND status = ?
                    ORDER BY created_at ASC;
                """, (user_id, status))
            else:
                cur.execute("""
                    SELECT * FROM organization_memberships
                    WHERE user_id = ?
                    ORDER BY created_at ASC;
                """, (user_id,))
            rows = cur.fetchall()
            return [self._row_to_membership(row) for row in rows]

    def update_membership(
        self,
        membership_id: str,
        role: Optional[str] = None,
        status: Optional[str] = None
    ) -> Optional[OrganizationMembership]:
        """Updates a membership's role or status."""
        updates = []
        params = []
        if role is not None:
            updates.append("role = ?")
            params.append(role)
        if status is not None:
            updates.append("status = ?")
            params.append(status)

        if not updates:
            return self.get_membership_by_id(membership_id)

        now_iso = datetime.now(timezone.utc).isoformat()
        updates.append("updated_at = ?")
        params.append(now_iso)

        params.append(membership_id)
        with self.transaction() as cur:
            cur.execute(f"""
                UPDATE organization_memberships
                SET {', '.join(updates)}
                WHERE id = ?;
            """, tuple(params))

        return self.get_membership_by_id(membership_id)

    def delete_membership(self, membership_id: str) -> bool:
        """Deletes a membership record."""
        with self.transaction() as cur:
            cur.execute("DELETE FROM organization_memberships WHERE id = ?;", (membership_id,))
            return cur.rowcount > 0

    def count_active_org_admins(self, organization_id: str) -> int:
        """Counts the number of active ORG_ADMIN members in an organization."""
        with self.transaction() as cur:
            cur.execute("""
                SELECT COUNT(*) FROM organization_memberships
                WHERE organization_id = ? AND role = 'ORG_ADMIN' AND status = 'ACTIVE';
            """, (organization_id,))
            return cur.fetchone()[0]

    # =========================================================================
    # AUDIT OPERATIONS
    # =========================================================================

    def create_audit_event(
        self,
        event_id: str,
        organization_id: str,
        actor_user_id: str,
        action: str,
        target_type: str,
        target_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> OrganizationAuditEvent:
        """Records an organization administrative audit event."""
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()
        meta_json = json.dumps(metadata or {})

        with self.transaction() as cur:
            cur.execute("""
                INSERT INTO organization_audit_events (
                    id, organization_id, actor_user_id, action, target_type, target_id, metadata, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """, (event_id, organization_id, actor_user_id, action, target_type, target_id, meta_json, now_iso))

        return OrganizationAuditEvent(
            id=event_id,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            metadata=metadata or {},
            created_at=now
        )

    def list_audit_events(self, organization_id: str, limit: int = 50) -> List[OrganizationAuditEvent]:
        """Lists recent audit events for an organization."""
        with self.transaction() as cur:
            cur.execute("""
                SELECT * FROM organization_audit_events
                WHERE organization_id = ?
                ORDER BY created_at DESC
                LIMIT ?;
            """, (organization_id, limit))
            rows = cur.fetchall()
            return [self._row_to_audit_event(row) for row in rows]

    # =========================================================================
    # INVITATION OPERATIONS
    # =========================================================================

    def create_invitation(
        self,
        invitation_id: str,
        organization_id: str,
        normalized_email: str,
        invited_role: str,
        token_hash: str,
        invited_by: str,
        expires_at: datetime
    ) -> OrganizationInvitation:
        """Persists a new invitation with hashed token."""
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()
        exp_iso = expires_at.isoformat()

        with self.transaction() as cur:
            cur.execute("""
                INSERT INTO organization_invitations (
                    id, organization_id, normalized_email, invited_role, token_hash,
                    invited_by, status, expires_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'PENDING', ?, ?, ?);
            """, (invitation_id, organization_id, normalized_email, invited_role, token_hash, invited_by, exp_iso, now_iso, now_iso))

        return self.get_invitation_by_id(invitation_id)  # type: ignore

    def get_invitation_by_id(self, invitation_id: str) -> Optional[OrganizationInvitation]:
        """Retrieves an invitation by ID."""
        with self.transaction() as cur:
            cur.execute("SELECT * FROM organization_invitations WHERE id = ?;", (invitation_id,))
            row = cur.fetchone()
            if not row:
                return None
            return self._row_to_invitation(row)

    def get_invitation_by_token_hash(self, token_hash: str) -> Optional[OrganizationInvitation]:
        """Retrieves an invitation by token hash."""
        with self.transaction() as cur:
            cur.execute("SELECT * FROM organization_invitations WHERE token_hash = ?;", (token_hash,))
            row = cur.fetchone()
            if not row:
                return None
            return self._row_to_invitation(row)

    def get_pending_invitation(self, organization_id: str, normalized_email: str) -> Optional[OrganizationInvitation]:
        """Retrieves an active PENDING non-expired invitation for an organization and email."""
        now_iso = datetime.now(timezone.utc).isoformat()
        with self.transaction() as cur:
            cur.execute("""
                SELECT * FROM organization_invitations
                WHERE organization_id = ? AND normalized_email = ? AND status = 'PENDING' AND expires_at > ?;
            """, (organization_id, normalized_email, now_iso))
            row = cur.fetchone()
            if not row:
                return None
            return self._row_to_invitation(row)

    def list_organization_invitations(
        self,
        organization_id: str,
        status: Optional[str] = None
    ) -> List[OrganizationInvitation]:
        """Lists invitations for an organization, optionally filtered by status."""
        with self.transaction() as cur:
            if status:
                cur.execute("""
                    SELECT * FROM organization_invitations
                    WHERE organization_id = ? AND status = ?
                    ORDER BY created_at DESC;
                """, (organization_id, status))
            else:
                cur.execute("""
                    SELECT * FROM organization_invitations
                    WHERE organization_id = ?
                    ORDER BY created_at DESC;
                """, (organization_id,))
            rows = cur.fetchall()
            return [self._row_to_invitation(row) for row in rows]

    def update_invitation_status(
        self,
        invitation_id: str,
        status: str,
        timestamp_field: Optional[str] = None
    ) -> Optional[OrganizationInvitation]:
        """Updates invitation status and sets corresponding timestamp field."""
        now_iso = datetime.now(timezone.utc).isoformat()
        updates = ["status = ?", "updated_at = ?"]
        params = [status, now_iso]

        if timestamp_field == "accepted_at":
            updates.append("accepted_at = ?")
            params.append(now_iso)
        elif timestamp_field == "revoked_at":
            updates.append("revoked_at = ?")
            params.append(now_iso)

        params.append(invitation_id)
        with self.transaction() as cur:
            cur.execute(f"""
                UPDATE organization_invitations
                SET {', '.join(updates)}
                WHERE id = ?;
            """, tuple(params))

        return self.get_invitation_by_id(invitation_id)

    def atomic_accept_invitation(
        self,
        invitation_id: str,
        membership_id: str,
        user_id: str,
        organization_id: str,
        role: str
    ) -> bool:
        """
        Atomically transitions invitation status to ACCEPTED and creates the
        corresponding organization membership within a single write transaction.
        Guarantees single-use acceptance and prevents duplicate memberships.
        """
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()

        with self.transaction() as cur:
            # 1. Verify invitation is still PENDING and not expired
            cur.execute(
                "SELECT status, expires_at FROM organization_invitations WHERE id = ?;",
                (invitation_id,)
            )
            row = cur.fetchone()
            if not row:
                return False

            if row["status"] != "PENDING":
                return False

            exp_dt = self._parse_dt(row["expires_at"])
            if exp_dt and exp_dt <= now:
                # Mark as expired
                cur.execute(
                    "UPDATE organization_invitations SET status = 'EXPIRED', updated_at = ? WHERE id = ?;",
                    (now_iso, invitation_id)
                )
                return False

            # 2. Check if membership already exists
            cur.execute(
                "SELECT id FROM organization_memberships WHERE organization_id = ? AND user_id = ?;",
                (organization_id, user_id)
            )
            if cur.fetchone():
                # Already a member, update invitation to ACCEPTED to consume it
                cur.execute(
                    "UPDATE organization_invitations SET status = 'ACCEPTED', accepted_at = ?, updated_at = ? WHERE id = ?;",
                    (now_iso, now_iso, invitation_id)
                )
                return True

            # 3. Create membership
            cur.execute("""
                INSERT INTO organization_memberships (
                    id, organization_id, user_id, role, status, joined_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'ACTIVE', ?, ?, ?);
            """, (membership_id, organization_id, user_id, role, now_iso, now_iso, now_iso))

            # 4. Mark invitation as ACCEPTED
            cur.execute("""
                UPDATE organization_invitations
                SET status = 'ACCEPTED', accepted_at = ?, updated_at = ?
                WHERE id = ?;
            """, (now_iso, now_iso, invitation_id))

            return True

    # =========================================================================
    # INTERNAL CONVERTERS
    # =========================================================================

    @staticmethod
    def _parse_dt(val: Any) -> Optional[datetime]:
        """Safely parses timestamp string or datetime object into UTC datetime."""
        if val is None:
            return None
        if isinstance(val, datetime):
            if val.tzinfo is None:
                return val.replace(tzinfo=timezone.utc)
            return val
        try:
            # Parse ISO or SQLite format
            dt = datetime.fromisoformat(str(val))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            return None

    def _row_to_user(self, row: sqlite3.Row) -> User:
        return User(
            id=row["id"],
            username=row["username"],
            email=row["email"],
            password_hash=row["password_hash"],
            role=row["role"],
            is_active=bool(row["is_active"]),
            failed_login_attempts=int(row["failed_login_attempts"]),
            locked_until=self._parse_dt(row["locked_until"]),
            created_at=self._parse_dt(row["created_at"]) or datetime.now(timezone.utc),
            updated_at=self._parse_dt(row["updated_at"]) or datetime.now(timezone.utc)
        )

    def _row_to_session(self, row: sqlite3.Row) -> SessionRecord:
        return SessionRecord(
            id=row["id"],
            user_id=row["user_id"],
            token_hash=row["token_hash"],
            ip_address=row["ip_address"],
            user_agent=row["user_agent"],
            created_at=self._parse_dt(row["created_at"]) or datetime.now(timezone.utc),
            last_activity_at=self._parse_dt(row["last_activity_at"]) or datetime.now(timezone.utc),
            expires_at=self._parse_dt(row["expires_at"]) or datetime.now(timezone.utc),
            is_revoked=bool(row["is_revoked"])
        )

    def _row_to_organization(self, row: sqlite3.Row) -> Organization:
        return Organization(
            id=row["id"],
            name=row["name"],
            slug=row["slug"],
            description=row["description"],
            status=row["status"],
            created_at=self._parse_dt(row["created_at"]) or datetime.now(timezone.utc),
            updated_at=self._parse_dt(row["updated_at"]) or datetime.now(timezone.utc),
            created_by=row["created_by"]
        )

    def _row_to_membership(self, row: sqlite3.Row) -> OrganizationMembership:
        return OrganizationMembership(
            id=row["id"],
            organization_id=row["organization_id"],
            user_id=row["user_id"],
            role=row["role"],
            status=row["status"],
            joined_at=self._parse_dt(row["joined_at"]),
            created_at=self._parse_dt(row["created_at"]) or datetime.now(timezone.utc),
            updated_at=self._parse_dt(row["updated_at"]) or datetime.now(timezone.utc)
        )

    def _row_to_audit_event(self, row: sqlite3.Row) -> OrganizationAuditEvent:
        try:
            meta = json.loads(row["metadata"]) if row["metadata"] else {}
        except Exception:
            meta = {}
        return OrganizationAuditEvent(
            id=row["id"],
            organization_id=row["organization_id"],
            actor_user_id=row["actor_user_id"],
            action=row["action"],
            target_type=row["target_type"],
            target_id=row["target_id"],
            metadata=meta,
            created_at=self._parse_dt(row["created_at"]) or datetime.now(timezone.utc)
        )

    def _row_to_invitation(self, row: sqlite3.Row) -> OrganizationInvitation:
        return OrganizationInvitation(
            id=row["id"],
            organization_id=row["organization_id"],
            normalized_email=row["normalized_email"],
            invited_role=row["invited_role"],
            token_hash=row["token_hash"],
            invited_by=row["invited_by"],
            status=row["status"],
            expires_at=self._parse_dt(row["expires_at"]) or datetime.now(timezone.utc),
            accepted_at=self._parse_dt(row["accepted_at"]),
            revoked_at=self._parse_dt(row["revoked_at"]),
            created_at=self._parse_dt(row["created_at"]) or datetime.now(timezone.utc),
            updated_at=self._parse_dt(row["updated_at"]) or datetime.now(timezone.utc)
        )
