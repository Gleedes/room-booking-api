import os
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from conftest import Account
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session


def test_registration_login_and_profile(client: TestClient, db_engine: Engine) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "Alice@Example.com", "password": "correct-horse-battery-staple"},
    )
    assert response.status_code == 201, response.text
    profile = response.json()
    assert profile["email"] == "alice@example.com"
    assert profile["role"] == "user"
    assert "password" not in profile and "password_hash" not in profile

    from room_booking.core.security import verify_password
    from room_booking.users.models import User

    with Session(db_engine) as session:
        stored_user = session.scalar(select(User).where(User.email == "alice@example.com"))
        assert stored_user is not None
        assert stored_user.password_hash.startswith("$argon2")
        assert verify_password("correct-horse-battery-staple", stored_user.password_hash)

    login = client.post(
        "/api/v1/auth/token",
        data={"username": "ALICE@example.com", "password": "correct-horse-battery-staple"},
    )
    assert login.status_code == 200, login.text
    assert login.json()["token_type"] == "bearer"
    token = login.json()["access_token"]
    claims = jwt.decode(token, os.environ["JWT_SECRET"], algorithms=["HS256"])
    assert 1790 <= claims["exp"] - datetime.now(UTC).timestamp() <= 1800
    me = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["id"] == profile["id"]


def test_duplicate_email_is_case_insensitive(client: TestClient) -> None:
    for email, expected in [("alice@example.com", 201), ("Alice@EXAMPLE.COM", 409)]:
        response = client.post(
            "/api/v1/auth/register", json={"email": email, "password": "a-long-enough-password"}
        )
        assert response.status_code == expected, response.text


def test_registration_cannot_assign_admin_role(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "attacker@example.com",
            "password": "a-long-enough-password",
            "role": "admin",
        },
    )
    assert response.status_code == 422


def test_password_and_email_validation(client: TestClient) -> None:
    for payload in [
        {"email": "not-an-email", "password": "a-long-enough-password"},
        {"email": "valid@example.com", "password": "short"},
    ]:
        assert client.post("/api/v1/auth/register", json=payload).status_code == 422


def test_wrong_password_and_unknown_user_have_same_response(
    client: TestClient, user: Account
) -> None:
    responses = [
        client.post("/api/v1/auth/token", data={"username": email, "password": "wrong-password"})
        for email in (user.email, "missing@example.com")
    ]
    assert [response.status_code for response in responses] == [401, 401]
    assert responses[0].json() == responses[1].json()


def test_reject_missing_bad_and_expired_tokens(client: TestClient, user: Account) -> None:
    expired = jwt.encode(
        {
            "sub": user.id,
            "iat": datetime.now(UTC) - timedelta(hours=1),
            "exp": datetime.now(UTC) - timedelta(seconds=1),
        },
        os.environ["JWT_SECRET"],
        algorithm="HS256",
    )
    wrong_signature = jwt.encode(
        {"sub": user.id, "iat": datetime.now(UTC), "exp": datetime.now(UTC) + timedelta(minutes=5)},
        "different-secret-that-is-long-enough-for-hs256",
        algorithm="HS256",
    )
    for headers in [
        {},
        {"Authorization": "Bearer nonsense"},
        {"Authorization": f"Bearer {expired}"},
        {"Authorization": f"Bearer {wrong_signature}"},
    ]:
        response = client.get("/api/v1/users/me", headers=headers)
        assert response.status_code == 401
        assert response.headers["www-authenticate"].lower() == "bearer"


def test_token_for_deleted_user_is_rejected(
    client: TestClient, user: Account, db_engine: Engine
) -> None:
    from room_booking.users.models import User

    with Session(db_engine) as session:
        stored_user = session.get(User, UUID(user.id))
        assert stored_user is not None
        session.delete(stored_user)
        session.commit()
    assert client.get("/api/v1/users/me", headers=user.headers).status_code == 401


def test_roles_are_read_from_database(
    client: TestClient,
    account_factory: Callable[..., Account],
    db_engine: Engine,
) -> None:
    from room_booking.users.models import User

    former_admin = account_factory(role="admin")
    with Session(db_engine) as session:
        stored_user = session.get(User, UUID(former_admin.id))
        assert stored_user is not None
        stored_user.role = "user"
        session.commit()
    response = client.post(
        "/api/v1/rooms",
        json={"name": "Unauthorized", "capacity": 4},
        headers=former_admin.headers,
    )
    assert response.status_code == 403
