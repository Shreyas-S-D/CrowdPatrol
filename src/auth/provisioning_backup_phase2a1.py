"""
CrowdPatrol 2.0 — Administrative User Provisioning Utility
Controlled mechanism for creating initial administrators and operators.
Prevents unrestricted public registration.
"""

import sys
import argparse
from typing import Optional
from src.auth.service import AuthService
from src.auth.database import AuthDatabase


DEFAULT_OPERATOR_USERNAME = "operator"
DEFAULT_OPERATOR_EMAIL = "operator@crowdpatrol.internal"
DEFAULT_OPERATOR_PASSWORD = "CrowdPatrol!2026Secure"

DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_EMAIL = "admin@crowdpatrol.internal"
DEFAULT_ADMIN_PASSWORD = "CrowdPatrol!Admin2026"


def seed_initial_users_if_empty(service: AuthService) -> None:
    """
    Seeds initial controlled user accounts if the database has zero users.
    Ensures safe local bootstrapping without open public registration.
    """
    try:
        # Check if admin already exists
        admin = service.db.get_user_by_identity(DEFAULT_ADMIN_USERNAME)
        if not admin:
            service.register_user(
                username=DEFAULT_ADMIN_USERNAME,
                email=DEFAULT_ADMIN_EMAIL,
                password=DEFAULT_ADMIN_PASSWORD,
                role="SUPER_ADMIN"
            )

        operator = service.db.get_user_by_identity(DEFAULT_OPERATOR_USERNAME)
        if not operator:
            service.register_user(
                username=DEFAULT_OPERATOR_USERNAME,
                email=DEFAULT_OPERATOR_EMAIL,
                password=DEFAULT_OPERATOR_PASSWORD,
                role="OPERATOR"
            )
    except Exception as e:
        # Don't fail if already created
        pass


def main():
    parser = argparse.ArgumentParser(description="CrowdPatrol 2.0 User Provisioning CLI")
    parser.add_argument("--create-user", action="store_true", help="Provision a new user")
    parser.add_argument("--username", type=str, help="Username (3-32 alphanumeric/underscore)")
    parser.add_argument("--email", type=str, help="User email address")
    parser.add_argument("--password", type=str, help="User password (min 8 characters)")
    parser.add_argument("--role", type=str, default="OPERATOR", choices=["SUPER_ADMIN", "AGENCY_ADMIN", "OPERATOR", "AUDITOR"], help="User role")
    parser.add_argument("--seed-defaults", action="store_true", help="Seed default development users")

    args = parser.parse_args()
    service = AuthService()

    if args.seed_defaults:
        seed_initial_users_if_empty(service)
        print("Initial development users seeded successfully.")
        return

    if args.create_user:
        if not args.username or not args.email or not args.password:
            print("Error: --username, --email, and --password are required.")
            sys.exit(1)
        try:
            user = service.register_user(
                username=args.username,
                email=args.email,
                password=args.password,
                role=args.role
            )
            print(f"User created successfully: {user.username} ({user.email}) [Role: {user.role}]")
        except Exception as e:
            print(f"Error provisioning user: {e}")
            sys.exit(1)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
