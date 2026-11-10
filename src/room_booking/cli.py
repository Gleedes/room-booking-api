import argparse
from getpass import getpass

from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from room_booking.core.db import get_engine
from room_booking.core.security import hash_password
from room_booking.users.models import User


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage Room Booking API")
    commands = parser.add_subparsers(dest="command", required=True)
    admin = commands.add_parser("create-admin", help="Create an administrator")
    admin.add_argument("--email", required=True)
    args = parser.parse_args()
    try:
        email = str(TypeAdapter(EmailStr).validate_python(args.email)).lower()
    except ValidationError:
        parser.exit(1, "Invalid email address\n")
    password = getpass("Password (12–128 characters): ")
    if not 12 <= len(password) <= 128:
        parser.exit(1, "Password must contain 12–128 characters\n")
    if password != getpass("Confirm password: "):
        parser.exit(1, "Passwords do not match\n")
    with Session(get_engine()) as session:
        if session.scalar(select(User).where(User.email == email)) is not None:
            parser.exit(1, "An account with this email already exists\n")
        session.add(User(email=email, password_hash=hash_password(password), role="admin"))
        try:
            session.commit()
        except IntegrityError as exc:
            session.rollback()
            if (
                getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
                == "uq_users_email"
            ):
                parser.exit(1, "An account with this email already exists\n")
            raise
    print("Administrator created.")


if __name__ == "__main__":
    main()
