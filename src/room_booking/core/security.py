from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from pwdlib import PasswordHash

from room_booking.core.config import get_settings

_password_hash = PasswordHash.recommended()
# Verify unknown accounts too, so a missing email does not skip the expensive password check.
_dummy_hash = _password_hash.hash("unavailable-account-password")


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return _password_hash.verify(password, hashed_password)


def verify_unknown_password(password: str) -> None:
    _password_hash.verify(password, _dummy_hash)


def create_access_token(user_id: UUID) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "sub": str(user_id),
            "iat": now,
            "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
        },
        settings.jwt_secret.get_secret_value(),
        algorithm="HS256",
    )
