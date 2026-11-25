"""
CrowdPatrol 2.0 — Secure Authentication Module
"""

from src.auth.crypto import hash_password, verify_password, generate_session_token, hash_session_token
from src.auth.database import AuthDatabase, User, SessionRecord
from src.auth.service import AuthService, GENERIC_AUTH_ERROR
from src.auth.provisioning import (
    seed_initial_users_if_empty,
    provision_initial_admin,
    is_production_mode,
    is_dev_seed_allowed,
)

__all__ = [
    "hash_password",
    "verify_password",
    "generate_session_token",
    "hash_session_token",
    "AuthDatabase",
    "User",
    "SessionRecord",
    "AuthService",
    "GENERIC_AUTH_ERROR",
    "seed_initial_users_if_empty",
    "provision_initial_admin",
    "is_production_mode",
    "is_dev_seed_allowed",
]
