"""
CrowdPatrol 2.0 — Cryptographic & Password Security Engine
OWASP ASVS v4.0 Level 2 compliant password hashing and token management.
Implements:
- Scrypt password hashing via standard library `hashlib.scrypt` (RFC 7914).
- Constant-time password verification via `hmac.compare_digest`.
- High-entropy cryptographic session token generation (256-bit).
- Secure token hashing (SHA-256) for zero-knowledge session storage.
"""

import os
import hmac
import hashlib
import secrets
from typing import Tuple


# Scrypt Recommended Parameters (RFC 7914 / OWASP)
# N=16384 (2^14 CPU/memory cost), r=8 (1024 bytes block), p=1 (parallelization)
SCRYPT_N = 16384
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_KEY_LEN = 64  # 512-bit output key
SALT_BYTES = 16      # 128-bit cryptographically secure random salt


def hash_password(password: str) -> str:
    """
    Hashes a password using Scrypt with a secure random salt.
    Returns encoded string: $scrypt$N=16384,r=8,p=1$<salt_hex>$<key_hex>
    """
    if not password or not isinstance(password, str):
        raise ValueError("Password must be a non-empty string.")

    salt = secrets.token_bytes(SALT_BYTES)
    key = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        maxmem=0,
        dklen=SCRYPT_KEY_LEN
    )
    return f"$scrypt$N={SCRYPT_N},r={SCRYPT_R},p={SCRYPT_P}${salt.hex()}${key.hex()}"


def verify_password(password: str, encoded_hash: str) -> bool:
    """
    Verifies a password against an encoded Scrypt hash using constant-time comparison.
    Never raises an exception on invalid format; returns False securely.
    """
    if not password or not encoded_hash or not isinstance(encoded_hash, str):
        return False

    try:
        parts = encoded_hash.split("$")
        # Expected format: ['', 'scrypt', 'N=16384,r=8,p=1', '<salt_hex>', '<key_hex>']
        if len(parts) != 5 or parts[1] != "scrypt":
            return False

        # Parse parameters
        params = dict(item.split("=") for item in parts[2].split(","))
        n = int(params.get("N", SCRYPT_N))
        r = int(params.get("r", SCRYPT_R))
        p = int(params.get("p", SCRYPT_P))

        salt = bytes.fromhex(parts[3])
        expected_key = bytes.fromhex(parts[4])

        computed_key = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=n,
            r=r,
            p=p,
            maxmem=0,
            dklen=len(expected_key)
        )

        # Constant-time comparison prevents timing side-channels
        return hmac.compare_digest(computed_key, expected_key)
    except Exception:
        return False


def generate_session_token() -> str:
    """
    Generates a cryptographically secure 256-bit URL-safe session token.
    Used as the bearer credential returned to the authenticated client.
    """
    return secrets.token_urlsafe(32)


def hash_session_token(token: str) -> str:
    """
    Computes SHA-256 hash of a session token for secure database persistence.
    Prevents session hijacking even if the database storage is compromised.
    """
    if not token or not isinstance(token, str):
        raise ValueError("Token must be a non-empty string.")
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
