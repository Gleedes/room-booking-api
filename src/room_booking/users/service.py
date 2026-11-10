from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from room_booking.core.errors import AppError
from room_booking.core.security import (
    create_access_token,
    hash_password,
    verify_password,
    verify_unknown_password,
)
from room_booking.users import repository
from room_booking.users.models import User
from room_booking.users.schemas import UserCreate


def register(session: Session, payload: UserCreate) -> User:
    # Only the CLI can grant an administrator role.
    user = repository.add_user(session, str(payload.email), hash_password(payload.password))
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        if getattr(getattr(exc.orig, "diag", None), "constraint_name", None) == "uq_users_email":
            raise AppError(409, "An account with this email already exists") from exc
        raise
    session.refresh(user)
    return user


def authenticate(session: Session, email: str, password: str) -> str:
    user = repository.find_by_email(session, email.strip().lower())
    # Verify a dummy hash for unknown emails to keep login timing comparable.
    if user is None:
        verify_unknown_password(password)
        raise AppError(401, "Incorrect email or password")
    if not verify_password(password, user.password_hash):
        raise AppError(401, "Incorrect email or password")
    return create_access_token(user.id)
