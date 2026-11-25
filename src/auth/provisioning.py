"""
CrowdPatrol 2.0 — Administrative User Provisioning Utility
Controlled mechanism for creating initial administrators and operators.
Prevents unrestricted public registration and guards against silent credential seeding.
"""

import os
import sys
import argparse
import getpass
import logging
from typing import Optional
from src.auth.service import AuthService
from src.auth.database import AuthDatabase, User

logger = logging.getLogger("crowdpatrol.auth.provisioning")

DEFAULT_OPERATOR_USERNAME = "operator"
DEFAULT_OPERATOR_EMAIL = "operator@crowdpatrol.internal"
DEFAULT_OPERATOR_PASSWORD = "CrowdPatrol!2026Secure"

DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_EMAIL = "admin@crowdpatrol.internal"
DEFAULT_ADMIN_PASSWORD = "CrowdPatrol!Admin2026"


def is_production_mode() -> bool:
    """Returns True if the application is running in production mode."""
    return os.environ.get("CROWDPATROL_ENV", "development").strip().lower() == "production"


def is_dev_seed_allowed() -> bool:
    """Returns True ONLY if developer seeding is explicitly enabled via environment variable."""
    return os.environ.get("CROWDPATROL_ALLOW_DEV_SEED", "0").strip() == "1"


def seed_initial_users_if_empty(service: AuthService) -> bool:
    """
    Conditionally seeds initial development credentials for local prototype testing.

    Security Policies:
    1. Disabled by default. Only executes if CROWDPATROL_ALLOW_DEV_SEED=1.
    2. Strictly forbidden in production mode: if CROWDPATROL_ENV=production and
       CROWDPATROL_ALLOW_DEV_SEED=1, raises RuntimeError.
    3. Production mode without dev seed flag simply returns False.
    4. Idempotent: Does not recreate users if identities already exist.

    Returns:
        True if development seeding was performed, False otherwise.
    Raises:
        RuntimeError if called in production mode with developer seeding requested.
    """
    if is_production_mode():
        if is_dev_seed_allowed():
            logger.critical("SECURITY VIOLATION: Developer account seeding is strictly forbidden in production mode.")
            raise RuntimeError("Developer account seeding is strictly forbidden in production mode.")
        logger.info("Production mode active: Automatic developer seeding is disabled.")
        return False

    if not is_dev_seed_allowed():
        logger.info(
            "Automatic developer seeding is disabled by default. "
            "Set CROWDPATROL_ALLOW_DEV_SEED=1 in development environments to enable."
        )
        return False

    # Development mode with explicit permission
    try:
        seeded_any = False
        admin = service.db.get_user_by_identity(DEFAULT_ADMIN_USERNAME)
        if not admin:
            service.register_user(
                username=DEFAULT_ADMIN_USERNAME,
                email=DEFAULT_ADMIN_EMAIL,
                password=DEFAULT_ADMIN_PASSWORD,
                role="SUPER_ADMIN"
            )
            logger.info("Seeded initial development admin: %s", DEFAULT_ADMIN_USERNAME)
            seeded_any = True

        operator = service.db.get_user_by_identity(DEFAULT_OPERATOR_USERNAME)
        if not operator:
            service.register_user(
                username=DEFAULT_OPERATOR_USERNAME,
                email=DEFAULT_OPERATOR_EMAIL,
                password=DEFAULT_OPERATOR_PASSWORD,
                role="OPERATOR"
            )
            logger.info("Seeded initial development operator: %s", DEFAULT_OPERATOR_USERNAME)
            seeded_any = True

        return seeded_any
    except Exception as e:
        logger.warning("Error during development account seeding: %s", type(e).__name__)
        return False


def provision_initial_admin(
    service: AuthService,
    username: str,
    email: str,
    password: str,
    allow_subsequent_admin: bool = False
) -> User:
    """
    Safely provisions the initial system administrator.
    Verifies whether a SUPER_ADMIN already exists in the database to prevent duplicate initial administrators.

    Args:
        service: AuthService instance.
        username: Administrator username.
        email: Administrator email.
        password: Administrator password.
        allow_subsequent_admin: If True, bypasses the single-initial-admin guard.

    Returns:
        The newly provisioned User.
    Raises:
        ValueError if an administrator already exists and allow_subsequent_admin is False.
    """
    with service.db.transaction() as cur:
        cur.execute("SELECT COUNT(*) FROM users WHERE role = 'SUPER_ADMIN';")
        count = cur.fetchone()[0]

    if count > 0 and not allow_subsequent_admin:
        raise ValueError(
            "An administrator account already exists. Subsequent administrators must be created "
            "with explicit permission or via authenticated administrative workflows."
        )

    user = service.register_user(
        username=username,
        email=email,
        password=password,
        role="SUPER_ADMIN"
    )
    logger.info("Administrator '%s' provisioned successfully [ID: %s].", user.username, user.id)
    return user


def main():
    parser = argparse.ArgumentParser(description="CrowdPatrol 2.0 User Provisioning CLI")
    parser.add_argument("--create-admin", action="store_true", help="Provision the initial administrator")
    parser.add_argument("--create-user", action="store_true", help="Provision a new user")
    parser.add_argument("--username", type=str, help="Username (3-32 alphanumeric/underscore)")
    parser.add_argument("--email", type=str, help="User email address")
    parser.add_argument("--password", type=str, help="User password (prompted interactively if omitted)")
    parser.add_argument("--role", type=str, default="OPERATOR", choices=["SUPER_ADMIN", "AGENCY_ADMIN", "OPERATOR", "AUDITOR"], help="User role")
    parser.add_argument("--seed-defaults", action="store_true", help="Seed default development users (requires CROWDPATROL_ALLOW_DEV_SEED=1)")
    parser.add_argument("--force-subsequent", action="store_true", help="Allow creating additional SUPER_ADMIN if one already exists")

    args = parser.parse_args()
    service = AuthService()

    if args.seed_defaults:
        if is_production_mode():
            print("Error: Developer account seeding is strictly forbidden in production mode.", file=sys.stderr)
            sys.exit(1)
        if not is_dev_seed_allowed():
            print("Error: Automatic developer seeding requires CROWDPATROL_ALLOW_DEV_SEED=1 environment variable.", file=sys.stderr)
            sys.exit(1)
        result = seed_initial_users_if_empty(service)
        if result:
            print("Initial development users seeded successfully.")
        else:
            print("No users seeded (accounts already exist or seeding was skipped).")
        return

    if args.create_admin or args.create_user:
        username = args.username
        if not username:
            username = input("Enter username: ").strip()

        email = args.email
        if not email:
            email = input("Enter email: ").strip()

        password = args.password
        if not password:
            password = getpass.getpass("Enter password (min 8 characters): ")
            confirm = getpass.getpass("Confirm password: ")
            if password != confirm:
                print("Error: Passwords do not match.", file=sys.stderr)
                sys.exit(1)

        try:
            if args.create_admin:
                user = provision_initial_admin(
                    service=service,
                    username=username,
                    email=email,
                    password=password,
                    allow_subsequent_admin=args.force_subsequent
                )
                print(f"Administrator successfully provisioned: {user.username} ({user.email}) [Role: {user.role}]")
            else:
                user = service.register_user(
                    username=username,
                    email=email,
                    password=password,
                    role=args.role
                )
                print(f"User successfully created: {user.username} ({user.email}) [Role: {user.role}]")
        except Exception as e:
            print(f"Error provisioning user: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
