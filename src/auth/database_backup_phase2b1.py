"""
CrowdPatrol 2.0 — Dedicated Authentication Database Layer
Transaction-safe SQLite database manager with WAL mode, foreign keys,
schema versioning, and parameterized queries.
Designed for zero-credential logging and seamless migration to PostgreSQL.
"""

import os
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


class AuthDatabase:
    """
    Manages persistent SQLite storage for user accounts and authentication sessions.
    Thread-safe connection handling, explicit transaction isolation, and schema migrations.
    """

    SCHEMA_VERSION = 1

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
