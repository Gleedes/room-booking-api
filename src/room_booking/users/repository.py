from sqlalchemy import select
from sqlalchemy.orm import Session

from room_booking.users.models import User


def find_by_email(session: Session, email: str) -> User | None:
    return session.scalar(select(User).where(User.email == email))


def add_user(session: Session, email: str, password_hash: str, role: str = "user") -> User:
    user = User(email=email, password_hash=password_hash, role=role)
    session.add(user)
    return user
