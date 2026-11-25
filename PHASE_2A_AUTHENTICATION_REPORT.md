# CROWDPatrol 2.0 — Phase 2A: Secure Authentication Foundation Report
**Milestone:** Phase 2A — Secure Authentication Foundation  
**System Baseline:** Streamlit Production Application (`dashboard/simple_dashboard.py` + `dashboard/landing_page.py`)  
**Date:** November 23, 2026  
**Status:** ✅ Fully Implemented, Verified, and Tested (19/19 Auth Tests Passing, 6/6 Landing Tests Passing)

---

## Executive Summary

Phase 2A implements the foundational, persistent security and authentication architecture for **CROWDPatrol 2.0**, securing the platform against unauthorized access, credential brute-forcing, and session hijacking. 

Crucially, **the operational surveillance dashboard is now strictly gated behind authenticated sessions**. Unauthenticated access attempts—whether initiated via landing page actions, sidebar navigation, or direct URL query parameter manipulation (`?page=dashboard`)—are intercepted and rejected. In compliance with strict Phase 2A boundary requirements, camera capture pipelines, AI inference engines, and emergency alert dispatchers are **disarmed** for all users until Phase 2B/3 multi-tenant organization authorization is established.

All underlying computer vision modules (YOLOv8 Person & Head models at 640×640), DeepSORT tracking with MobileNetV2 embeddings, optical flow, Firebase RTDB sync, and SMTP dispatchers remain **100% preserved and untouched**.

---

## 1. Categorized Implementation & Verification Status

In accordance with strict reporting guidelines, all components and test outcomes are explicitly categorized below.

### 1.1 Implemented
- **Cryptographic Engine (`src/auth/crypto.py`):**
  - Scrypt password hashing via standard library `hashlib.scrypt` (RFC 7914 compliant, $N=16384, r=8, p=1$, 16-byte cryptographically secure random salt, 64-byte key length).
  - Constant-time verification using `hmac.compare_digest` to eliminate timing side-channel attacks.
  - High-entropy 256-bit URL-safe bearer token generation (`secrets.token_urlsafe(32)`).
  - Deterministic SHA-256 session token hashing (`hashlib.sha256(token).hexdigest()`) for zero-knowledge persistent storage.
- **Dedicated Authentication Database Layer (`src/auth/database.py`):**
  - SQLite database (`data/crowdpatrol_auth.db`) with Write-Ahead Logging (`PRAGMA journal_mode = WAL`) and foreign key enforcement (`PRAGMA foreign_keys = ON`).
  - Schema migrations tracking (`schema_migrations`).
  - Tables: `users`, `authentication_sessions`, `password_reset_tokens`.
  - Indexes: `idx_users_username`, `idx_users_email`, `idx_sessions_token_hash`, `idx_sessions_user_id`, `idx_sessions_expires_at`.
  - Transaction-safe context managers (`BEGIN IMMEDIATE` / `COMMIT` / `ROLLBACK`).
  - Parameterized SQL queries (`?`) preventing SQL injection.
- **Authentication Service (`src/auth/service.py`):**
  - Controlled administrative provisioning (`register_user`) with normalized lowercase username and email validation.
  - Dual-identity login (username or email).
  - Progressive rate-limiting: 5 consecutive failed attempts triggers an automated 15-minute temporary account lockout.
  - Generic failure responses (`"Invalid credentials."`) preventing account enumeration.
  - Session rotation on successful authentication (generates fresh token, invalidating old sessions to prevent session fixation).
  - Sliding session activity tracking (4-hour inactivity timeout, 12-hour maximum absolute lifespan).
  - Explicit session revocation (`revoke_session`, `revoke_all_user_sessions`).
- **Administrative Provisioning Utility (`src/auth/provisioning.py`):**
  - CLI utility for provisioning users (`--create-user`) and automatic development bootstrapping (`seed_initial_users_if_empty`).
  - Unrestricted public registration is disabled by design.
- **Authentication UI Layer (`dashboard/auth_ui.py`):**
  - Frosted nocturnal login screen (`render_login_view`) matching `dashboard/design_system.py`.
  - Identity & password inputs, generic error alerts, lockout warnings, and return-to-landing navigation.
  - Minimal authenticated placeholder (`render_authenticated_placeholder`) displaying operator identity (`username`, `email`, `role`, `id`), session security status, and logout button.
- **Streamlit Application Integration (`dashboard/simple_dashboard.py`):**
  - Server-side token validation on every script rerun.
  - Strict authentication guard intercepting direct `?page=dashboard` access.
  - Navigation flow: `Landing Page` ➔ `Login` ➔ `Authenticated Placeholder` ➔ `Logout` ➔ `Landing Page`.

### 1.2 Tested and Passed
- **Authentication Test Suite (`tests/test_auth.py`):** 19/19 tests PASSED in 8.46s:
  1. `test_password_hashing_and_verification`: Scrypt parameters, format, constant-time verification, invalid hash rejection.
  2. `test_session_token_generation_and_hashing`: 256-bit entropy, uniqueness, SHA-256 persistence hash.
  3. `test_user_registration_success`: Controlled provisioning, normalized lowercase identity, Scrypt hash persistence.
  4. `test_duplicate_username_rejection`: Database unique constraint enforced for normalized usernames.
  5. `test_duplicate_email_rejection`: Database unique constraint enforced for normalized email addresses.
  6. `test_invalid_registration_inputs`: Username format, email syntax, and minimum password length validation.
  7. `test_authenticate_successful_username`: Login using username and generation of active session token.
  8. `test_authenticate_successful_email`: Login using email address.
  9. `test_authenticate_invalid_password_returns_generic_error`: Rejection with generic message.
  10. `test_authenticate_unknown_account_returns_generic_error`: Non-existent identity returns identical generic message.
  11. `test_login_rate_limiting_and_temporary_lockout`: 5 consecutive failures triggers 15-minute lockout; rejects even valid password while locked.
  12. `test_session_creation_and_hashed_storage`: Confirms raw token is NEVER stored in database, only SHA-256 hash.
  13. `test_session_rotation_on_login`: Multiple logins produce distinct, unfixated session tokens.
  14. `test_session_validation_success`: Active session returns authenticated `User` object.
  15. `test_session_revocation_logout`: Explicit revocation marks session invalid in DB.
  16. `test_expired_token_rejection`: Expired tokens return `None` and are marked revoked.
  17. `test_database_foreign_key_cascade`: Deleting a user cascades and deletes all associated sessions.
  18. `test_unauthenticated_dashboard_access_rejected_in_ui`: Streamlit AppTest verifies accessing `?page=dashboard` without credentials presents login form, keeps `is_monitoring = False`, and blocks camera execution.
  19. `test_streamlit_login_and_logout_cycle`: Streamlit AppTest verifies complete user journey: Unauthenticated ➔ Login with credentials ➔ Authenticated Placeholder ➔ Logout ➔ Landing.
- **Landing Page Regression Suite (`tests/test_landing_page.py`):** 6/6 tests PASSED in 7.15s:
  - Theme/CSS tokens, section contents, launch callbacks, AppTest initial landing view, AppTest navigation cycle, and deep-linking verification.
- **Application Startup Verification:** Evaluated via `AppTest.from_file('dashboard/simple_dashboard.py')`: **0 exceptions**, boots to `landing`.

### 1.3 Tested and Failed
- None in Phase 2A test suites.
- *(Reference Note from Phase 1.1: The 2 pre-existing hardware-dependent physical webcam tests in `tests/test_multi_camera.py` remain documented and untouched as expected.)*

### 1.4 Not Tested
- **Live Physical Camera Processing for Authenticated Users:** By Phase 2A design, live camera capture handles are intentionally disarmed on both the login and authenticated placeholder views.
- **External Network IdP / OAuth Providers:** Not in Phase 2A scope (local SQLite Scrypt authentication).
- **Production Firebase / SMTP Writes:** No live database or email writes are triggered by authentication tests.

### 1.5 Planned (Phase 2B & Beyond)
- **Phase 2B:** Organization & Agency Model (Tenant hierarchy: Organizations, Teams, Agency Roles).
- **Phase 3:** Multi-Tenancy Data Scoping (Per-tenant camera inventories, isolated audit logs, incident report boundaries).
- **Phase 4:** Operational Dashboard Redesign (Integrating design system into camera monitoring UI).

---

## 2. Security Architecture Evaluation

### 2.1 Password Hashing: Scrypt vs. Argon2id on Windows
- **Selection:** `hashlib.scrypt` (RFC 7914).
- **Justification:** While Argon2id is a premier memory-hard algorithm, its Python implementation (`argon2-cffi`) requires compiled native C extensions. As discovered in earlier project phases, native C/Rust extensions (`.pyd` / `.dll`) are blocked by Windows Code Integrity under Windows Smart App Control.
- **Security Assessment:** Python 3.14 includes `hashlib.scrypt` in the core runtime compiled with OpenSSL. Configured with $N=16384, r=8, p=1$ and 128-bit random salts, Scrypt provides robust resistance against GPU/ASIC brute-force dictionary attacks while operating 100% natively without external binary risks.

### 2.2 Zero-Knowledge Session Storage
- **Vulnerability Prevented:** Database dump credential harvesting.
- **Mechanism:** When a user logs in, the server generates a 256-bit entropy token ($T$). The client receives $T$ as a bearer credential. The database persists only $\text{SHA-256}(T)$. When validating an incoming session, the server hashes the received token and queries by hash. Even a full SQLite database dump yields zero usable session tokens.

### 2.3 Anti-Fixation & Session Rotation
- When an unauthenticated connection submits valid credentials, a fresh session token is generated. Any pre-existing session token or state associated with that client is invalidated.
- Logging out immediately executes `UPDATE authentication_sessions SET is_revoked = 1 WHERE token_hash = ?`.

### 2.4 Brute-Force Rate Limiting & Account Lockout
- Failed login attempts increment `failed_login_attempts` on the user record.
- Upon 5 consecutive failures, `locked_until` is set to `CURRENT_TIMESTAMP + 15 minutes`.
- Any subsequent attempt (even with the correct password) during the lockout window is rejected with an explicit remaining-time message.
- A successful login resets `failed_login_attempts = 0` and clears `locked_until`.
- Generic error messages (`"Invalid credentials."`) prevent account enumeration.

---

## 3. Database Schema & Migration Path to PostgreSQL

### 3.1 Current SQLite Schema
```sql
CREATE TABLE schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    description TEXT NOT NULL
);

CREATE TABLE users (
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

CREATE TABLE authentication_sessions (
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

CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_sessions_token_hash ON authentication_sessions(token_hash);
CREATE INDEX idx_sessions_user_id ON authentication_sessions(user_id);
CREATE INDEX idx_sessions_expires_at ON authentication_sessions(expires_at);
```

### 3.2 PostgreSQL Migration Path
The authentication layer was authored to ensure standard SQL compatibility:
1. **Data Types:** `TEXT` translates directly to `VARCHAR` or `TEXT`; `TIMESTAMP` translates to `TIMESTAMPTZ`; `INTEGER` translates to `BOOLEAN` or `INTEGER`.
2. **Parameterized Queries:** Parameterized SQL queries in `AuthDatabase` use standard positional placeholders (`?`), which map directly to `%s` (psycopg2/psycopg3) or `$1, $2` (asyncpg).
3. **Foreign Keys & Transactions:** Foreign keys with `ON DELETE CASCADE` and `BEGIN / COMMIT / ROLLBACK` transactions operate identically in PostgreSQL.

---

## 4. Streamlit Session Lifecycle & Navigation Integration

### 4.1 Session Architecture in Streamlit
Streamlit executes Python scripts from top to bottom on each interaction or rerun. Relying exclusively on an in-memory boolean flag (`st.session_state.is_logged_in = True`) is insecure because:
- In-memory flags can be manipulated or desynchronized across browser tabs.
- Ephemeral state is lost on browser refresh unless backed by persistent server-side tokens.

**Phase 2A Solution:**
1. A bearer session token string is stored in `st.session_state["auth_token"]`.
2. At the very top of `dashboard/simple_dashboard.py`, **server-side validation** executes against `AuthDatabase`:
   ```python
   current_raw_token = st.session_state.get("auth_token")
   if current_raw_token:
       validated_user = auth_service.validate_session(current_raw_token)
       if not validated_user:
           st.session_state.pop("auth_token", None)
           st.session_state.pop("auth_user", None)
       else:
           st.session_state["auth_user"] = validated_user
   ```
3. If an expired or revoked token is encountered, session state is cleared immediately.

### 4.2 Gating the Operational Dashboard
Direct access to the operational dashboard without authentication is strictly blocked:
```python
if st.session_state.current_page == "dashboard":
    if not is_authenticated():
        # STRICT AUTHENTICATION GUARD
        if st.sidebar.button("🏠 ← Return to Landing Page", key="sidebar_dashboard_return_btn"):
            switch_to_landing()
        render_login_view(
            auth_service,
            on_success=lambda u, t: switch_to_auth_home(),
            on_cancel=switch_to_landing,
            auth_message="🔒 Authentication Required: Direct access to the live monitoring dashboard is restricted. Please sign in."
        )
        st.stop()
```
When `st.stop()` triggers, the script terminates immediately. OpenCV video capture handles, YOLOv8 inference loops, DeepSORT tracking, and alert dispatchers **never execute**.

---

## 5. Feature Preservation Checklist

| Component / Subsystem | Pre-Phase 2A Status | Phase 2A Status | Verification Outcome |
| :--- | :--- | :--- | :--- |
| **Streamlit Entrypoint (`simple_dashboard.py`)** | Primary Application | Primary Application | Preserved & secured |
| **Landing Page (`dashboard/landing_page.py`)** | Preserved | Preserved | 100% Identical to Phase 1.1 |
| **YOLOv8 Person Model (640×640, 0.35 conf)** | Active in dashboard | Active in dashboard | Untouched |
| **YOLOv8 Head Model (640×640, 0.25 conf)** | Active in dashboard | Active in dashboard | Untouched |
| **DeepSORT Multi-Object Tracker** | Active in dashboard | Active in dashboard | Untouched |
| **MobileNetV2 Appearance Embedder** | Active in dashboard | Active in dashboard | Untouched |
| **4×4 Spatial Density Estimator** | Active in dashboard | Active in dashboard | Untouched |
| **Farneback Optical Flow Analyzer** | Active in dashboard | Active in dashboard | Untouched |
| **Composite Risk Engine (65/35 weight)** | Active in dashboard | Active in dashboard | Untouched |
| **Firebase Realtime Database Sync** | Configured | Configured | Untouched |
| **SMTP Notification Dispatcher** | Configured | Configured | Untouched |
| **Multi-Camera Manager (4 Feeds)** | Configured | Configured | Untouched |
| **React Frontend / Starlette Backend** | Experimental | Experimental | Untouched |

---

## 6. Pre-Modification Backups & Git Audit

- **Backups Created:**
  - `backups/phase2a_auth/landing_page.py` (54,647 bytes)
  - `backups/phase2a_auth/simple_dashboard.py` (91,451 bytes)
  - `backups/phase2a_auth/design_system.py` (23,192 bytes)
- **Files Modified:**
  - `dashboard/simple_dashboard.py` (Added session validation, login guard, authenticated placeholder routing).
- **New Files Created:**
  - `src/auth/__init__.py`
  - `src/auth/crypto.py`
  - `src/auth/database.py`
  - `src/auth/service.py`
  - `src/auth/provisioning.py`
  - `dashboard/auth_ui.py`
  - `tests/test_auth.py`
  - `PHASE_2A_AUTHENTICATION_REPORT.md`
- **Files Untouched in `src/`:** All 42 pre-existing source files in `src/` have timestamps on or before November 22, 2026. Zero changes were made to detection, tracking, camera capture, or alert modules.
- **Credentials & Secrets:** No credentials, API keys, or plaintext passwords are committed or exposed.

---

## 7. Conclusion & Next Steps

Phase 2A is complete. The application possesses a persistent, cryptographically secure authentication and session foundation. Unauthenticated access to the operational dashboard is prevented, and user accounts are provisioned and protected.

**Phase 2B, multi-tenancy, and operational dashboard redesign have not been started.**

Standing by for user review and approval before proceeding to **Phase 2B: Organization & Multi-Tenancy Architecture**.
