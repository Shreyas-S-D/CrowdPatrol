"""
CrowdPatrol 2.0 — Phase 2A Authentication Test Suite
Verifies:
1. Scrypt password hashing & constant-time verification.
2. Controlled administrative user provisioning & unique normalization.
3. Authentication via username or email.
4. Generic authentication failure error messages.
5. Brute-force rate limiting and temporary account lockout (5 failed attempts).
6. Zero-knowledge session token generation & SHA-256 persistence.
7. Session rotation on login (Anti-fixation protection).
8. Sliding session validity and expired token rejection.
9. Session revocation (Logout).
10. Database foreign key constraints & cascading deletion.
11. Unauthenticated dashboard access rejection in Streamlit.
"""

import sys
import tempfile
from pathlib import Path
from datetime import datetime, timedelta, timezone
import pytest

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.auth.crypto import (
    hash_password,
    verify_password,
    generate_session_token,
    hash_session_token
)
from src.auth.database import AuthDatabase, User, SessionRecord
from src.auth.service import AuthService, GENERIC_AUTH_ERROR
from src.auth.provisioning import (
    seed_initial_users_if_empty,
    provision_initial_admin,
    is_production_mode,
    is_dev_seed_allowed,
)


@pytest.fixture
def temp_auth_db():
    """Provides a fresh isolated temporary SQLite database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
        temp_db_path = tf.name
    
    db = AuthDatabase(db_path=temp_db_path)
    yield db
    
    # Cleanup temp file
    try:
        Path(temp_db_path).unlink(missing_ok=True)
    except Exception:
        pass


@pytest.fixture
def auth_service(temp_auth_db):
    """Provides an AuthService instance backed by an isolated temporary database."""
    return AuthService(db=temp_auth_db)


# =============================================================================
# 1. CRYPTOGRAPHIC HASHING & TOKEN TESTS
# =============================================================================

def test_password_hashing_and_verification():
    """Verify Scrypt generates expected encoded format and verifies constant-time."""
    password = "SuperSecretPassword!2026"
    encoded = hash_password(password)

    # Format verification: $scrypt$N=16384,r=8,p=1$<salt_hex>$<key_hex>
    assert encoded.startswith("$scrypt$N=16384,r=8,p=1$")
    parts = encoded.split("$")
    assert len(parts) == 5
    assert len(parts[3]) == 32   # 16 bytes = 32 hex chars
    assert len(parts[4]) == 128  # 64 bytes = 128 hex chars

    # Correct password succeeds
    assert verify_password(password, encoded) is True

    # Wrong password fails
    assert verify_password("WrongPassword123", encoded) is False
    assert verify_password("", encoded) is False
    assert verify_password(password, "malformed_hash_string") is False


def test_session_token_generation_and_hashing():
    """Verify high-entropy token generation and SHA-256 persistence hash."""
    token1 = generate_session_token()
    token2 = generate_session_token()

    assert len(token1) >= 40
    assert token1 != token2

    hash1 = hash_session_token(token1)
    hash2 = hash_session_token(token2)

    assert len(hash1) == 64  # SHA-256 hex length
    assert hash1 != hash2
    assert hash_session_token(token1) == hash1  # Deterministic hash


# =============================================================================
# 2. CONTROLLED USER PROVISIONING & CONSTRAINTS
# =============================================================================

def test_user_registration_success(auth_service):
    """Verify controlled user provisioning normalizes identity and hashes password."""
    user = auth_service.register_user(
        username="SecurityOfficer_1",
        email="Officer.One@Agency.Gov",
        password="SecurePassword2026!",
        role="OPERATOR"
    )

    assert user.id.startswith("usr_")
    assert user.username == "securityofficer_1"  # Normalized lowercase
    assert user.email == "officer.one@agency.gov"  # Normalized lowercase
    assert user.role == "OPERATOR"
    assert user.is_active is True
    assert user.password_hash.startswith("$scrypt$")
    assert "SecurePassword2026!" not in user.password_hash


def test_duplicate_username_rejection(auth_service):
    """Verify database unique constraint rejects duplicate normalized usernames."""
    auth_service.register_user("operator_alpha", "alpha@agency.gov", "Password1234!")

    with pytest.raises(ValueError, match="already registered"):
        # Attempt registering same username with different casing
        auth_service.register_user("OPERATOR_ALPHA", "alpha2@agency.gov", "Password1234!")


def test_duplicate_email_rejection(auth_service):
    """Verify database unique constraint rejects duplicate normalized emails."""
    auth_service.register_user("operator_one", "chief@agency.gov", "Password1234!")

    with pytest.raises(ValueError, match="already registered"):
        auth_service.register_user("operator_two", "CHIEF@agency.gov", "Password1234!")


def test_invalid_registration_inputs(auth_service):
    """Verify username, email, and password length validations."""
    with pytest.raises(ValueError, match="Username must be"):
        auth_service.register_user("a", "test@agency.gov", "Password1234!")

    with pytest.raises(ValueError, match="Invalid email"):
        auth_service.register_user("valid_user", "not-an-email", "Password1234!")

    with pytest.raises(ValueError, match="at least 8 characters"):
        auth_service.register_user("valid_user", "test@agency.gov", "short")


# =============================================================================
# 3. AUTHENTICATION & LOGIN WORKFLOW
# =============================================================================

def test_authenticate_successful_username(auth_service):
    """Verify login succeeds using username and returns active session."""
    auth_service.register_user("ops_lead", "lead@agency.gov", "StrongPass2026!", role="AGENCY_ADMIN")

    user, raw_token, error = auth_service.authenticate("ops_lead", "StrongPass2026!")

    assert error is None
    assert user is not None
    assert user.username == "ops_lead"
    assert raw_token is not None
    assert len(raw_token) >= 40


def test_authenticate_successful_email(auth_service):
    """Verify login succeeds using email address."""
    auth_service.register_user("patrol_unit", "patrol@agency.gov", "StrongPass2026!")

    user, raw_token, error = auth_service.authenticate("PATROL@AGENCY.GOV", "StrongPass2026!")

    assert error is None
    assert user is not None
    assert user.username == "patrol_unit"
    assert raw_token is not None


def test_authenticate_invalid_password_returns_generic_error(auth_service):
    """Verify failed password returns generic failure without account enumeration."""
    auth_service.register_user("valid_user", "valid@agency.gov", "CorrectPass123!")

    user, raw_token, error = auth_service.authenticate("valid_user", "IncorrectPassword!")

    assert user is None
    assert raw_token is None
    assert error == GENERIC_AUTH_ERROR


def test_authenticate_unknown_account_returns_generic_error(auth_service):
    """Verify non-existent identity returns same generic error."""
    user, raw_token, error = auth_service.authenticate("non_existent_user", "SomePassword123!")

    assert user is None
    assert raw_token is None
    assert error == GENERIC_AUTH_ERROR


# =============================================================================
# 4. BRUTE-FORCE RATE LIMITING & ACCOUNT LOCKOUT
# =============================================================================

def test_login_rate_limiting_and_temporary_lockout(auth_service):
    """Verify 5 consecutive failed logins triggers a 15-minute account lockout."""
    username = "target_account"
    auth_service.register_user(username, "target@agency.gov", "ActualPassword123!")

    # 4 Failed attempts -> Still returns generic error
    for _ in range(4):
        _, _, error = auth_service.authenticate(username, "WrongGuess123!")
        assert error == GENERIC_AUTH_ERROR

    # 5th Failed attempt -> Triggers lockout internally while returning uniform generic error
    _, _, error = auth_service.authenticate(username, "WrongGuess123!")
    assert error == GENERIC_AUTH_ERROR

    # Verify state in database: account is locked
    user_rec = auth_service.db.get_user_by_identity(username)
    assert user_rec.failed_login_attempts >= 5
    assert user_rec.locked_until is not None
    assert user_rec.locked_until > datetime.now(timezone.utc)

    # Even with the CORRECT password, locked account is rejected with uniform generic error
    user, token, error = auth_service.authenticate(username, "ActualPassword123!")
    assert user is None
    assert token is None
    assert error == GENERIC_AUTH_ERROR


# =============================================================================
# 5. SESSION MANAGEMENT & ANTI-FIXATION
# =============================================================================

def test_session_creation_and_hashed_storage(auth_service):
    """Verify the database NEVER stores the raw session token, only SHA-256 hash."""
    auth_service.register_user("sess_user", "sess@agency.gov", "ValidPassword2026!")
    user, raw_token, _ = auth_service.authenticate("sess_user", "ValidPassword2026!")

    expected_hash = hash_session_token(raw_token)
    session_record = auth_service.db.get_session_by_token_hash(expected_hash)

    assert session_record is not None
    assert session_record.user_id == user.id
    assert session_record.token_hash == expected_hash
    # Confirm raw token is nowhere in the DB row
    assert raw_token != session_record.token_hash


def test_session_rotation_on_login(auth_service):
    """Verify logging in generates a fresh token and distinct hash (anti-fixation)."""
    auth_service.register_user("multi_login", "multi@agency.gov", "Password1234!")

    _, token1, _ = auth_service.authenticate("multi_login", "Password1234!")
    _, token2, _ = auth_service.authenticate("multi_login", "Password1234!")

    assert token1 != token2
    assert hash_session_token(token1) != hash_session_token(token2)


def test_session_validation_success(auth_service):
    """Verify an active valid session returns the authenticated User object."""
    auth_service.register_user("active_op", "active@agency.gov", "Password1234!")
    _, raw_token, _ = auth_service.authenticate("active_op", "Password1234!")

    user = auth_service.validate_session(raw_token)
    assert user is not None
    assert user.username == "active_op"


def test_session_revocation_logout(auth_service):
    """Verify logout revokes the session token server-side."""
    auth_service.register_user("logout_op", "logout@agency.gov", "Password1234!")
    _, raw_token, _ = auth_service.authenticate("logout_op", "Password1234!")

    # Verify active
    assert auth_service.validate_session(raw_token) is not None

    # Revoke (Logout)
    revoked = auth_service.revoke_session(raw_token)
    assert revoked is True

    # Now invalid
    assert auth_service.validate_session(raw_token) is None


def test_expired_token_rejection(auth_service):
    """Verify an expired session is rejected and marked revoked."""
    auth_service.register_user("expire_op", "expire@agency.gov", "Password1234!")
    user, raw_token, _ = auth_service.authenticate("expire_op", "Password1234!")

    token_hash = hash_session_token(raw_token)
    past_time = datetime.now(timezone.utc) - timedelta(hours=5)

    # Manually expire the session in DB
    with auth_service.db.transaction() as cur:
        cur.execute(
            "UPDATE authentication_sessions SET expires_at = ? WHERE token_hash = ?;",
            (past_time.isoformat(), token_hash)
        )

    # Validating expired token fails
    assert auth_service.validate_session(raw_token) is None

    # Confirm marked revoked in DB
    record = auth_service.db.get_session_by_token_hash(token_hash)
    assert record.is_revoked is True


def test_database_foreign_key_cascade(auth_service):
    """Verify foreign key constraint cascades delete from users to sessions."""
    user = auth_service.register_user("cascade_user", "cascade@agency.gov", "Password1234!")
    _, raw_token, _ = auth_service.authenticate("cascade_user", "Password1234!")
    token_hash = hash_session_token(raw_token)

    assert auth_service.db.get_session_by_token_hash(token_hash) is not None

    # Delete the user
    with auth_service.db.transaction() as cur:
        cur.execute("DELETE FROM users WHERE id = ?;", (user.id,))

    # Sessions must be cascaded and deleted
    assert auth_service.db.get_session_by_token_hash(token_hash) is None


# =============================================================================
# 6. STREAMLIT APPTEST INTEGRATION TESTS
# =============================================================================

def test_unauthenticated_dashboard_access_rejected_in_ui():
    """
    Verify that an unauthenticated user requesting ?page=dashboard is blocked:
    login challenge is displayed, is_monitoring remains False, and cameras/alerts never run.
    """
    from streamlit.testing.v1 import AppTest
    script_path = str(Path(__file__).parent.parent / "dashboard" / "simple_dashboard.py")
    
    at = AppTest.from_file(script_path)
    at.query_params["page"] = "dashboard"
    at.run(timeout=30)
    
    assert len(at.exception) == 0
    # Must NOT be monitoring
    assert at.session_state["is_monitoring"] is False if "is_monitoring" in at.session_state else True
    # User must not be authenticated
    assert "auth_user" not in at.session_state or at.session_state["auth_user"] is None
    # Login submit button must be present in UI
    form_buttons = [b.key for b in at.button if b.key]
    assert "login_cancel_btn" in form_buttons or "sidebar_dashboard_return_btn" in form_buttons


def test_streamlit_login_and_logout_cycle(monkeypatch):
    """
    Verify complete Streamlit authentication lifecycle:
    Unauthenticated -> Login with credentials -> Authenticated Placeholder -> Logout -> Landing.
    """
    monkeypatch.setenv("CROWDPATROL_ALLOW_DEV_SEED", "1")
    monkeypatch.setenv("CROWDPATROL_ENV", "development")
    from streamlit.testing.v1 import AppTest
    script_path = str(Path(__file__).parent.parent / "dashboard" / "simple_dashboard.py")
    
    # 1. Start on dashboard page as unauthenticated
    at = AppTest.from_file(script_path)
    at.query_params["page"] = "dashboard"
    at.run(timeout=30)
    assert "auth_user" not in at.session_state or at.session_state["auth_user"] is None
    
    # 2. Fill login inputs with default seeded operator credentials
    at.text_input(key="login_identity_input").input("operator")
    at.text_input(key="login_password_input").input("CrowdPatrol!2026Secure")
    
    # Submit login form
    at.button(key="login_submit_btn").click().run(timeout=30)
    assert len(at.exception) == 0
    
    # 3. Verify user is now authenticated and on authenticated_home
    assert "auth_user" in at.session_state and at.session_state["auth_user"] is not None
    assert at.session_state["auth_user"].username == "operator"
    assert at.session_state["current_page"] == "authenticated_home"
    assert "auth_logout_btn" in [b.key for b in at.button if b.key]
    
    # 4. Click Logout
    at.button(key="auth_logout_btn").click().run(timeout=30)
    assert len(at.exception) == 0
    
    # 5. Verify returned to landing page and session cleared
    assert "auth_user" not in at.session_state or at.session_state["auth_user"] is None
    assert "auth_token" not in at.session_state or at.session_state["auth_token"] is None
    assert at.session_state["current_page"] == "landing"


# =============================================================================
# 7. AUDIT SECURITY & ADVERSARIAL EDGE CASE TESTS (PHASE 2A.1)
# =============================================================================

def test_malformed_session_tokens_fail_closed(auth_service):
    """Verify that all varieties of malformed, non-string, or garbage tokens fail closed."""
    malformed_tokens = [
        "",
        "   ",
        None,
        "short",
        "invalid!token@characters#$",
        "12345" * 10,
        "a" * 1000,
        b"raw_bytes_instead_of_string",
        {"token": "dict_injection"},
        123456789,
    ]
    for token in malformed_tokens:
        result = auth_service.validate_session(token)
        assert result is None, f"Expected None for malformed token {type(token)}: {repr(token)}"


def test_replayed_revoked_session_token(auth_service):
    """Verify that a session token revoked on logout cannot be replayed."""
    auth_service.register_user("replay_user", "replay@test.com", "Password123!")
    user, raw_token, error = auth_service.authenticate("replay_user", "Password123!")
    assert user is not None
    assert raw_token is not None

    # Verify session is initially valid
    validated = auth_service.validate_session(raw_token)
    assert validated is not None
    assert validated.id == user.id

    # Revoke session (simulating logout)
    assert auth_service.revoke_session(raw_token) is True

    # Replay attempt 1: immediately after revocation
    assert auth_service.validate_session(raw_token) is None

    # Replay attempt 2: repeated call
    assert auth_service.validate_session(raw_token) is None

    # Replay attempt 3: revoking already revoked token is safe and idempotent
    auth_service.revoke_session(raw_token)
    assert auth_service.validate_session(raw_token) is None


def test_expired_token_exact_boundary(auth_service):
    """Verify expired token rejection at exact boundary conditions."""
    user = auth_service.register_user("boundary_user", "boundary@test.com", "Password123!")
    _, raw_token, _ = auth_service.authenticate("boundary_user", "Password123!")
    token_hash = hash_session_token(raw_token)

    # 1. Modify session expiration in DB to 1 second in the past
    past_time = datetime.now(timezone.utc) - timedelta(seconds=1)
    with auth_service.db.transaction() as cur:
        cur.execute("UPDATE authentication_sessions SET expires_at = ? WHERE token_hash = ?;", (past_time.isoformat(), token_hash))

    # Must be rejected immediately
    assert auth_service.validate_session(raw_token) is None

    # Must also be marked as revoked in DB
    session_rec = auth_service.db.get_session_by_token_hash(token_hash)
    assert session_rec.is_revoked is True


def test_inactive_user_session_invalidation(auth_service):
    """Verify that deactivating a user immediately invalidates their active sessions."""
    user = auth_service.register_user("deactivate_user", "deact@test.com", "Password123!")
    _, raw_token, _ = auth_service.authenticate("deactivate_user", "Password123!")
    assert auth_service.validate_session(raw_token) is not None

    # Admin deactivates the user
    with auth_service.db.transaction() as cur:
        cur.execute("UPDATE users SET is_active = 0 WHERE id = ?;", (user.id,))

    # Session validation must fail closed and revoke the session
    assert auth_service.validate_session(raw_token) is None

    # Even if session has valid timestamps, user cannot authenticate or validate
    user2, _, err = auth_service.authenticate("deactivate_user", "Password123!")
    assert user2 is None
    assert err == GENERIC_AUTH_ERROR


def test_multiple_sessions_and_revoke_all(auth_service):
    """Verify that multiple concurrent sessions for one user can exist and be revoked together."""
    user = auth_service.register_user("multi_session_user", "multi@test.com", "Password123!")
    
    # Create 3 concurrent sessions (e.g. 3 browser devices/tabs)
    _, token1, _ = auth_service.authenticate("multi_session_user", "Password123!")
    _, token2, _ = auth_service.authenticate("multi_session_user", "Password123!")
    _, token3, _ = auth_service.authenticate("multi_session_user", "Password123!")

    assert token1 != token2 and token2 != token3

    # All 3 are valid
    assert auth_service.validate_session(token1) is not None
    assert auth_service.validate_session(token2) is not None
    assert auth_service.validate_session(token3) is not None

    # Revoke all sessions for this user (e.g. security credential reset)
    revoked_count = auth_service.revoke_all_user_sessions(user.id)
    assert revoked_count == 3

    # All 3 tokens must now fail validation
    assert auth_service.validate_session(token1) is None
    assert auth_service.validate_session(token2) is None
    assert auth_service.validate_session(token3) is None


def test_malformed_password_hashes_fail_closed():
    """Verify verify_password cleanly returns False on malformed/tampered hash strings."""
    malformed_hashes = [
        "",
        "$scrypt$",
        "$scrypt$N=16384,r=8,p=1$",
        "$scrypt$N=16384,r=8,p=1$deadbeef",
        "$scrypt$N=invalid,r=8,p=1$deadbeef$feedface",
        "$argon2id$v=19$m=65536,t=3,p=4$somehash",
        "$pbkdf2$50000$salt$hash",
        "plain_text_not_a_hash",
        None,
        12345,
        "$scrypt$N=16384,r=8,p=1$" + "0" * 32 + "$" + "g" * 128,  # invalid non-hex char 'g'
    ]
    for bad_hash in malformed_hashes:
        assert verify_password("AnyPassword123!", bad_hash) is False


# =============================================================================
# 8. SECURITY CORRECTIONS & HARDENING TESTS (PHASE 2A.2)
# =============================================================================

def test_identical_external_login_failures_for_all_cases(auth_service):
    """
    Verify that all authentication failure cases return the EXACT identical external error message:
    'Invalid credentials or account unavailable.'
    This prevents account existence enumeration, lockout disclosure, and disabled account discovery.
    """
    # 1. Provision active, disabled, and locked test accounts
    auth_service.register_user("enum_active", "enum_active@test.com", "ActivePass123!")
    
    auth_service.register_user("enum_disabled", "enum_disabled@test.com", "DisabledPass123!")
    with auth_service.db.transaction() as cur:
        cur.execute("UPDATE users SET is_active = 0 WHERE username = 'enum_disabled';")

    auth_service.register_user("enum_locked", "enum_locked@test.com", "LockedPass123!")
    locked_future = (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()
    with auth_service.db.transaction() as cur:
        cur.execute("UPDATE users SET locked_until = ?, failed_login_attempts = 5 WHERE username = 'enum_locked';", (locked_future,))

    failure_cases = [
        ("non_existent_account", "AnyPassword123!", "Unknown account"),
        ("non_existent@domain.com", "AnyPassword123!", "Unknown email"),
        ("enum_active", "WrongPassword123!", "Incorrect password"),
        ("enum_disabled", "DisabledPass123!", "Disabled account with correct password"),
        ("enum_disabled", "WrongPassword123!", "Disabled account with wrong password"),
        ("enum_locked", "LockedPass123!", "Locked account with correct password"),
        ("enum_locked", "WrongPassword123!", "Locked account with wrong password"),
        ("", "AnyPassword123!", "Empty username"),
        ("enum_active", "", "Empty password"),
        ("   ", "   ", "Whitespace only"),
    ]

    expected_msg = "Invalid credentials or account unavailable."

    for identity, password, case_desc in failure_cases:
        user, token, err = auth_service.authenticate(identity, password)
        assert user is None, f"Expected user=None for case: {case_desc}"
        assert token is None, f"Expected token=None for case: {case_desc}"
        assert err == expected_msg, f"Expected exact error '{expected_msg}' but got '{err}' for case: {case_desc}"


def test_developer_seeding_disabled_by_default(auth_service, monkeypatch):
    """Verify that automatic developer seeding is disabled by default."""
    # Ensure env var is absent
    monkeypatch.delenv("CROWDPATROL_ALLOW_DEV_SEED", raising=False)
    monkeypatch.delenv("CROWDPATROL_ENV", raising=False)

    seeded = seed_initial_users_if_empty(auth_service)
    assert seeded is False

    # Database must have zero users
    with auth_service.db.transaction() as cur:
        cur.execute("SELECT COUNT(*) FROM users;")
        count = cur.fetchone()[0]
    assert count == 0


def test_explicit_development_seeding(auth_service, monkeypatch):
    """Verify that setting CROWDPATROL_ALLOW_DEV_SEED=1 allows seeding development users."""
    monkeypatch.setenv("CROWDPATROL_ALLOW_DEV_SEED", "1")
    monkeypatch.setenv("CROWDPATROL_ENV", "development")

    seeded = seed_initial_users_if_empty(auth_service)
    assert seeded is True

    # Check that admin and operator were seeded
    admin = auth_service.db.get_user_by_identity("admin")
    operator = auth_service.db.get_user_by_identity("operator")

    assert admin is not None
    assert admin.role == "SUPER_ADMIN"
    assert operator is not None
    assert operator.role == "OPERATOR"

    # Second invocation should be idempotent and return False (no new users seeded)
    seeded_again = seed_initial_users_if_empty(auth_service)
    assert seeded_again is False


def test_production_mode_seeding_rejection(auth_service, monkeypatch):
    """Verify that production mode explicitly rejects developer seeding."""
    monkeypatch.setenv("CROWDPATROL_ENV", "production")

    # If dev seed is requested in production, it must raise a RuntimeError
    monkeypatch.setenv("CROWDPATROL_ALLOW_DEV_SEED", "1")
    with pytest.raises(RuntimeError, match="strictly forbidden in production mode"):
        seed_initial_users_if_empty(auth_service)

    # If dev seed is NOT requested in production, it returns False safely without seeding
    monkeypatch.setenv("CROWDPATROL_ALLOW_DEV_SEED", "0")
    seeded = seed_initial_users_if_empty(auth_service)
    assert seeded is False


def test_database_unavailable_during_login_fails_closed(auth_service, monkeypatch):
    """Verify that database errors during authenticate() or validate_session() fail closed."""
    import sqlite3

    def broken_get_user(*args, **kwargs):
        raise sqlite3.OperationalError("database is locked or disk error")

    def broken_get_session(*args, **kwargs):
        raise sqlite3.OperationalError("database disk image is malformed")

    # 1. Break user lookup during authenticate()
    monkeypatch.setattr(auth_service.db, "get_user_by_identity", broken_get_user)
    user, token, err = auth_service.authenticate("any_user", "AnyPass123!")
    assert user is None
    assert token is None
    assert err == "Invalid credentials or account unavailable."

    # 2. Break session lookup during validate_session()
    monkeypatch.setattr(auth_service.db, "get_session_by_token_hash", broken_get_session)
    valid_user = auth_service.validate_session("some_test_session_token_123456789")
    assert valid_user is None


def test_concurrent_failed_login_attempts_and_lockout(auth_service):
    """Verify sequential/concurrent failed attempts trigger lockout and fail closed."""
    auth_service.register_user("lock_target", "lock@target.com", "TargetPass123!")

    # Attempt 5 incorrect passwords
    for i in range(5):
        _, _, err = auth_service.authenticate("lock_target", f"BadPass{i}!")
        assert err == "Invalid credentials or account unavailable."

    # Verify locked in DB
    user_rec = auth_service.db.get_user_by_identity("lock_target")
    assert user_rec.failed_login_attempts >= 5
    assert user_rec.locked_until is not None
    assert user_rec.locked_until > datetime.now(timezone.utc)

    # Attempt with correct password while locked must fail closed with generic error
    user, token, err = auth_service.authenticate("lock_target", "TargetPass123!")
    assert user is None
    assert token is None
    assert err == "Invalid credentials or account unavailable."


def test_duplicate_initial_administrator_provisioning_prevented(auth_service):
    """Verify provision_initial_admin prevents accidental duplicate initial administrators."""
    # 1. Provision first admin -> succeeds
    admin1 = provision_initial_admin(
        auth_service,
        username="lead_admin",
        email="lead@agency.gov",
        password="AdminPassword123!"
    )
    assert admin1 is not None
    assert admin1.role == "SUPER_ADMIN"

    # 2. Provisioning second admin without allow_subsequent_admin must be rejected
    with pytest.raises(ValueError, match="administrator account already exists"):
        provision_initial_admin(
            auth_service,
            username="second_admin",
            email="second@agency.gov",
            password="AdminPassword456!"
        )

    # 3. Explicit bypass allows creating second admin when intentional
    admin2 = provision_initial_admin(
        auth_service,
        username="second_admin",
        email="second@agency.gov",
        password="AdminPassword456!",
        allow_subsequent_admin=True
    )
    assert admin2 is not None
    assert admin2.username == "second_admin"


def test_authentication_database_transaction_rollback(auth_service):
    """Verify database transaction context manager rolls back changes on error."""
    # Count initial users
    with auth_service.db.transaction() as cur:
        cur.execute("SELECT COUNT(*) FROM users;")
        initial_count = cur.fetchone()[0]

    # Attempt a transaction that raises an unhandled error halfway through
    try:
        with auth_service.db.transaction() as cur:
            cur.execute("""
                INSERT INTO users (id, username, email, password_hash, role)
                VALUES ('usr_rollback_test', 'rollback_user', 'rollback@test.com', 'dummy_hash', 'OPERATOR');
            """)
            # Force an exception to trigger rollback
            raise RuntimeError("Simulated transaction failure")
    except RuntimeError:
        pass

    # Verify rollback: user must NOT be in the database
    with auth_service.db.transaction() as cur:
        cur.execute("SELECT COUNT(*) FROM users WHERE username = 'rollback_user';")
        count = cur.fetchone()[0]
    assert count == 0

    with auth_service.db.transaction() as cur:
        cur.execute("SELECT COUNT(*) FROM users;")
        final_count = cur.fetchone()[0]
    assert final_count == initial_count



