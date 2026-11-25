"""
CrowdPatrol Demo - Authentication, Profile Settings & History Ledger Module.
Provides secure scrypt password hashing, session authentication, user registration,
per-account camera configuration persistence, and an isolated alert history ledger.
"""

import os
import sqlite3
import hashlib
import hmac
import secrets
import re
import json
import time
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

_DB_WRITE_LOCK = threading.Lock()

DEFAULT_AUTH_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "demo_auth.db"

DEFAULT_CAMERA_SLOTS = [
    {
        "id": "CAM-01",
        "name": "Main Sidewalk / Entrance",
        "source_type": "video",
        "source": "data/videos/youtube_crowd_test.mp4",
        "device_name": None,
        "enabled": True
    },
    {
        "id": "CAM-02",
        "name": "Overhead Dense Zone",
        "source_type": "video",
        "source": "data/videos/dense_crowd_test.mp4",
        "device_name": None,
        "enabled": True
    },
    {
        "id": "CAM-03",
        "name": "Street Crossing Plaza",
        "source_type": "video",
        "source": "data/videos/real_crowd_video_1.mp4",
        "device_name": None,
        "enabled": True
    },
    {
        "id": "CAM-04",
        "name": "Perimeter Gate",
        "source_type": "video",
        "source": "data/videos/real_crowd_video_2.mp4",
        "device_name": None,
        "enabled": True
    }
]

def get_db_path() -> Path:
    """Returns absolute path to the demo authentication SQLite database."""
    db_path = DEFAULT_AUTH_DB_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return db_path

def get_db_connection(db_path: Optional[Path] = None, timeout: float = 30.0) -> sqlite3.Connection:
    """
    Opens an SQLite connection with WAL mode, busy timeout, and foreign keys enabled.
    """
    path = Path(db_path or get_db_path()).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=timeout)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA busy_timeout=30000;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn

def hash_password(password: str, salt: Optional[bytes] = None) -> Tuple[str, str]:
    """
    Hashes password using secure scrypt key derivation.
    Returns (hex_hash, hex_salt).
    """
    if salt is None:
        salt = secrets.token_bytes(16)
    # scrypt with n=16384, r=8, p=1
    derived = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=16384,
        r=8,
        p=1,
        maxmem=32 * 1024 * 1024
    )
    return derived.hex(), salt.hex()

def verify_password(password: str, stored_hash_hex: str, salt_hex: str) -> bool:
    """Verifies candidate password against stored scrypt hash using constant-time comparison."""
    try:
        salt = bytes.fromhex(salt_hex)
        candidate_hash, _ = hash_password(password, salt=salt)
        return hmac.compare_digest(candidate_hash, stored_hash_hex)
    except Exception:
        return False

def init_auth_db(db_path: Optional[Path] = None):
    """Initializes the SQLite schema for authentication, user profiles, cameras, and ledger."""
    path = Path(db_path or get_db_path()).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = get_db_connection(path)
    cursor = conn.cursor()
    
    # 1. Users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS demo_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL COLLATE NOCASE,
            email TEXT UNIQUE COLLATE NOCASE,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'Administrator',
            created_at TEXT NOT NULL
        )
    """)

    # Check if email column exists in existing demo_users table (migration safety)
    cursor.execute("PRAGMA table_info(demo_users)")
    cols = [c[1] for c in cursor.fetchall()]
    if "email" not in cols:
        cursor.execute("ALTER TABLE demo_users ADD COLUMN email TEXT COLLATE NOCASE")
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_demo_users_email ON demo_users(email)")

    # 2. Per-user camera configurations table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_camera_configs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            slot_id TEXT NOT NULL,
            name TEXT NOT NULL,
            source_type TEXT NOT NULL,
            source TEXT NOT NULL,
            device_name TEXT,
            enabled INTEGER NOT NULL DEFAULT 1,
            detection_mode TEXT NOT NULL DEFAULT 'person',
            updated_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES demo_users (id) ON DELETE CASCADE,
            UNIQUE(user_id, slot_id)
        )
    """)

    # 3. Per-user historical alert ledger table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_alert_ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            alert_id TEXT NOT NULL,
            camera_id TEXT NOT NULL,
            camera_name TEXT NOT NULL,
            risk_level TEXT NOT NULL,
            risk_score REAL NOT NULL,
            reason TEXT NOT NULL,
            primary_risk_zone TEXT DEFAULT 'A1',
            status TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            acknowledged INTEGER DEFAULT 0,
            acknowledged_by TEXT,
            FOREIGN KEY (user_id) REFERENCES demo_users (id) ON DELETE CASCADE
        )
    """)

    # Create indices for fast lookup
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ucc_user ON user_camera_configs(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ual_user ON user_alert_ledger(user_id, timestamp)")

    conn.commit()
    conn.close()

def user_count(db_path: Optional[Path] = None) -> int:
    """Returns total number of registered users."""
    path = db_path or get_db_path()
    if not path.exists():
        return 0
    conn = sqlite3.connect(path)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM demo_users")
    count = cursor.fetchone()[0]
    conn.close()
    return count

def validate_email(email: str) -> bool:
    """Validates basic email format."""
    pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    return bool(re.match(pattern, email.strip()))

def register_user(
    username: str,
    email: str,
    password: str,
    role: str = "Operator",
    db_path: Optional[Path] = None
) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    Registers a new user account with isolated profile settings and email notifications.
    Returns (success, message, user_dict).
    """
    username = username.strip()
    email = email.strip().lower()

    if not username:
        return False, "Username cannot be blank.", None
    if len(username) < 3:
        return False, "Username must be at least 3 characters long.", None
    if not email or not validate_email(email):
        return False, "Please enter a valid email address.", None
    if not password or len(password) < 6:
        return False, "Password must be at least 6 characters long.", None

    path = db_path or get_db_path()
    init_auth_db(path)

    pwd_hash, salt = hash_password(password)
    now = datetime.now().isoformat()

    conn = sqlite3.connect(path)
    cursor = conn.cursor()
    try:
        # Check uniqueness
        cursor.execute("SELECT id FROM demo_users WHERE username = ?", (username,))
        if cursor.fetchone():
            return False, f"Username '{username}' is already taken.", None

        cursor.execute("SELECT id FROM demo_users WHERE email = ?", (email,))
        if cursor.fetchone():
            return False, f"Email '{email}' is already registered.", None

        cursor.execute("""
            INSERT INTO demo_users (username, email, password_hash, salt, role, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (username, email, pwd_hash, salt, role, now))
        new_user_id = cursor.lastrowid
        conn.commit()

        # Seed initial camera configuration for this user
        _seed_user_cameras_internal(cursor, new_user_id)
        conn.commit()

        user_info = {
            "id": new_user_id,
            "username": username,
            "email": email,
            "role": role
        }
        return True, "Account created successfully!", user_info

    except Exception as e:
        return False, f"Registration failed: {str(e)}", None
    finally:
        conn.close()

def provision_user(
    username: str,
    password: str,
    role: str = "Administrator",
    email: Optional[str] = None,
    db_path: Optional[Path] = None
) -> bool:
    """
    Creates or updates an administrator/user record with hashed credentials.
    Returns True if successfully provisioned.
    """
    username = username.strip()
    if not username or not password:
        return False

    if email is None:
        email = "shreyaskeyboardtutorials@gmail.com" if username.lower() == "admin" else f"{username.lower()}@crowdpatrol.internal"

    path = db_path or get_db_path()
    init_auth_db(path)
    
    pwd_hash, salt = hash_password(password)
    now = datetime.now().isoformat()

    conn = sqlite3.connect(path)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO demo_users (username, email, password_hash, salt, role, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(username) DO UPDATE SET
                email=excluded.email,
                password_hash=excluded.password_hash,
                salt=excluded.salt,
                role=excluded.role
        """, (username, email, pwd_hash, salt, role, now))
        user_id = cursor.lastrowid
        if not user_id:
            cursor.execute("SELECT id FROM demo_users WHERE username = ?", (username,))
            row = cursor.fetchone()
            if row:
                user_id = row[0]
        
        if user_id:
            _seed_user_cameras_internal(cursor, user_id)
        conn.commit()
        return True
    except Exception as e:
        print(f"Provision error: {e}")
        return False
    finally:
        conn.close()

def authenticate_user(login_identifier: str, password: str, db_path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """
    Authenticates by username OR email and password against the database.
    Returns user dictionary if valid, None if invalid.
    """
    identifier = login_identifier.strip()
    if not identifier or not password:
        return None

    path = db_path or get_db_path()
    if not path.exists():
        return None

    init_auth_db(path)
    conn = sqlite3.connect(path)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, username, email, password_hash, salt, role 
        FROM demo_users 
        WHERE username = ? OR email = ?
    """, (identifier, identifier.lower()))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    user_id, uname, email_addr, stored_hash, salt, role = row
    if verify_password(password, stored_hash, salt):
        return {
            "id": user_id,
            "username": uname,
            "email": email_addr or "shreyaskeyboardtutorials@gmail.com",
            "role": role
        }
    return None

def _seed_user_cameras_internal(cursor: sqlite3.Cursor, user_id: int):
    """Internal helper to insert default 4-slot CCTV configuration for a given user if not present."""
    now = datetime.now().isoformat()
    for cam in DEFAULT_CAMERA_SLOTS:
        cursor.execute("""
            INSERT OR IGNORE INTO user_camera_configs 
            (user_id, slot_id, name, source_type, source, device_name, enabled, detection_mode, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            cam["id"],
            cam["name"],
            cam["source_type"],
            str(cam["source"]),
            cam.get("device_name"),
            1 if cam.get("enabled", True) else 0,
            "person",
            now
        ))

def get_user_camera_configs(user_id: int, db_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """
    Loads saved camera configurations for a specific user.
    Falls back to defaults and seeds them if user has none saved.
    """
    path = db_path or get_db_path()
    init_auth_db(path)
    conn = get_db_connection(path)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT slot_id, name, source_type, source, device_name, enabled, detection_mode
        FROM user_camera_configs
        WHERE user_id = ?
        ORDER BY slot_id ASC
    """, (user_id,))
    rows = cursor.fetchall()
    
    if not rows:
        _seed_user_cameras_internal(cursor, user_id)
        conn.commit()
        cursor.execute("""
            SELECT slot_id, name, source_type, source, device_name, enabled, detection_mode
            FROM user_camera_configs
            WHERE user_id = ?
            ORDER BY slot_id ASC
        """, (user_id,))
        rows = cursor.fetchall()

    conn.close()

    configs = []
    for r in rows:
        configs.append({
            "id": r[0],
            "name": r[1],
            "source_type": r[2],
            "source": int(r[3]) if str(r[3]).isdigit() else r[3],
            "device_name": r[4],
            "enabled": bool(r[5]),
            "detection_mode": r[6]
        })
    return configs

def save_user_camera_configs(user_id: int, cameras: List[Dict[str, Any]], db_path: Optional[Path] = None) -> bool:
    """
    Saves a list of camera configuration dicts for a specific user account.
    """
    path = db_path or get_db_path()
    init_auth_db(path)
    conn = get_db_connection(path)
    cursor = conn.cursor()
    now = datetime.now().isoformat()

    try:
        for cam in cameras:
            slot_id = cam.get("id")
            name = cam.get("name", slot_id)
            source_type = cam.get("source_type", "video")
            source = str(cam.get("source", ""))
            device_name = cam.get("device_name")
            enabled = 1 if cam.get("enabled", True) else 0
            det_mode = cam.get("detection_mode", "person")

            cursor.execute("""
                INSERT INTO user_camera_configs 
                (user_id, slot_id, name, source_type, source, device_name, enabled, detection_mode, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, slot_id) DO UPDATE SET
                    name=excluded.name,
                    source_type=excluded.source_type,
                    source=excluded.source,
                    device_name=excluded.device_name,
                    enabled=excluded.enabled,
                    detection_mode=excluded.detection_mode,
                    updated_at=excluded.updated_at
            """, (user_id, slot_id, name, source_type, source, device_name, enabled, det_mode, now))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error saving user camera configs: {e}")
        return False
    finally:
        conn.close()

def log_user_alert_event(
    user_id: int,
    alert_id: str,
    camera_id: str,
    camera_name: str,
    risk_level: str,
    risk_score: float,
    reason: str,
    primary_risk_zone: str = "A1",
    status: str = "ACTIVE",
    timestamp: Optional[str] = None,
    acknowledged: bool = False,
    acknowledged_by: Optional[str] = None,
    db_path: Optional[Path] = None
) -> bool:
    """
    Logs an alert event into the user's isolated history ledger with thread-safe write locking and retry.
    """
    path = db_path or get_db_path()
    init_auth_db(path)
    ts = timestamp or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    max_attempts = 5
    for attempt in range(max_attempts):
        with _DB_WRITE_LOCK:
            conn = None
            try:
                conn = get_db_connection(path, timeout=30.0)
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO user_alert_ledger 
                    (user_id, alert_id, camera_id, camera_name, risk_level, risk_score, reason, primary_risk_zone, status, timestamp, acknowledged, acknowledged_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    user_id,
                    alert_id,
                    camera_id,
                    camera_name,
                    risk_level,
                    float(risk_score),
                    reason,
                    primary_risk_zone,
                    status,
                    ts,
                    1 if acknowledged else 0,
                    acknowledged_by
                ))
                conn.commit()
                return True
            except sqlite3.OperationalError as oe:
                if "locked" in str(oe).lower() and attempt < max_attempts - 1:
                    time.sleep(0.05 * (attempt + 1))
                    continue
                print(f"Error logging user alert: {oe}")
                return False
            except Exception as e:
                print(f"Error logging user alert: {e}")
                return False
            finally:
                if conn:
                    try:
                        conn.close()
                    except Exception:
                        pass
    return False

def get_user_alert_ledger(user_id: int, limit: int = 50, db_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """
    Retrieves the chronological history ledger of alerts for a specific user.
    """
    path = db_path or get_db_path()
    if not path.exists():
        return []

    conn = get_db_connection(path)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, alert_id, camera_id, camera_name, risk_level, risk_score, reason, primary_risk_zone, status, timestamp, acknowledged, acknowledged_by
        FROM user_alert_ledger
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT ?
    """, (user_id, limit))
    rows = cursor.fetchall()
    conn.close()

    events = []
    for r in rows:
        events.append({
            "id": r[0],
            "alert_id": r[1],
            "camera_id": r[2],
            "camera_name": r[3],
            "risk_level": r[4],
            "risk_score": r[5],
            "reason": r[6],
            "primary_risk_zone": r[7],
            "status": r[8],
            "timestamp": r[9],
            "acknowledged": bool(r[10]),
            "acknowledged_by": r[11]
        })
    return events

def update_user_alert_status(
    user_id: int,
    alert_id: str,
    status: str,
    acknowledged: Optional[bool] = None,
    acknowledged_by: Optional[str] = None,
    db_path: Optional[Path] = None
) -> bool:
    """
    Updates status and acknowledgement fields for a user's alert strictly scoped to user_id.
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    try:
        if acknowledged is not None:
            cursor.execute("""
                UPDATE user_alert_ledger
                SET status = ?, acknowledged = ?, acknowledged_by = ?
                WHERE user_id = ? AND alert_id = ?
            """, (status, 1 if acknowledged else 0, acknowledged_by, user_id, alert_id))
        else:
            cursor.execute("""
                UPDATE user_alert_ledger
                SET status = ?
                WHERE user_id = ? AND alert_id = ?
            """, (status, user_id, alert_id))
        updated = cursor.rowcount > 0
        conn.commit()
        return updated
    except Exception as e:
        print(f"Error updating user alert status: {e}")
        return False
    finally:
        conn.close()
