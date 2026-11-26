"""Create or manage application administrators from the trusted server console."""

import argparse
import sys
from getpass import getpass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pydantic import ValidationError  # noqa: E402
from sqlalchemy.exc import SQLAlchemyError  # noqa: E402

from app.core.exceptions import AppError  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.schemas.user import Registration  # noqa: E402
from app.services.admin import change_role, create_administrator  # noqa: E402


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("create", "grant", "revoke"))
    parser.add_argument("--username", help="New account username for create")
    parser.add_argument("--email", help="New account email for create")
    parser.add_argument("--identity", help="Existing username or email for grant/revoke")
    args = parser.parse_args(argv)
    if args.action == "create" and args.identity:
        parser.error("Use --username and --email with create")
    if args.action != "create" and (args.username or args.email):
        parser.error("Use --identity with grant/revoke")
    try:
        if args.action == "create":
            username = args.username or input("New administrator username: ").strip()
            email = args.email or input("Administrator email: ").strip()
            password = getpass("Administrator password (10-128 characters): ")
            confirmation = getpass("Confirm administrator password: ")
            if password != confirmation:
                print("Passwords did not match; no account was created.", file=sys.stderr)
                return 1
            payload = Registration(username=username, email=email, password=password)
            with SessionLocal() as db:
                user = create_administrator(db, payload)
                print(
                    f"Administrator created: {user.username}. Sign in with this separate account."
                )
        else:
            identity = args.identity or input("Existing username or email: ").strip()
            with SessionLocal() as db:
                role = "admin" if args.action == "grant" else "user"
                user = change_role(db, identity, role)
                print(f"Account role updated: {user.username} -> {role}. Refresh account details.")
        return 0
    except ValidationError:
        print(
            "Invalid account fields. Use a 3-32 character username, valid email, "
            "and 10-128 character password. No account was created.",
            file=sys.stderr,
        )
    except AppError as error:
        print(f"Administrator operation failed: {error.message}.", file=sys.stderr)
    except SQLAlchemyError:
        print(
            "Database operation failed. Check the connection and apply the latest "
            "Alembic migration before using this command.",
            file=sys.stderr,
        )
    except (EOFError, KeyboardInterrupt):
        print("Administrator operation cancelled.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
