import os
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class Account:
    id: str
    email: str
    token: str

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}


@pytest.fixture(scope="session")
def db_engine() -> Iterator[Engine]:
    raw_url = os.environ.get("TEST_DATABASE_URL")
    if not raw_url:
        raise pytest.UsageError(
            "Set TEST_DATABASE_URL to a dedicated PostgreSQL database ending in _test"
        )
    url = make_url(raw_url)
    if url.get_backend_name() != "postgresql" or not (url.database or "").endswith("_test"):
        raise pytest.UsageError(
            "Tests only run against a PostgreSQL database whose name ends in _test"
        )

    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("DATABASE_URL", raw_url)
        patch.setenv("JWT_SECRET", "test-only-secret-with-at-least-32-characters")
        from room_booking.core.config import get_settings

        get_settings.cache_clear()
        config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
        config.set_main_option("sqlalchemy.url", raw_url.replace("%", "%%"))
        command.upgrade(config, "head")
        engine = create_engine(raw_url, pool_pre_ping=True)
        try:
            yield engine
        finally:
            engine.dispose()
            get_settings.cache_clear()


@pytest.fixture(autouse=True)
def clean_database(db_engine: Engine) -> Iterator[None]:
    with db_engine.begin() as connection:
        connection.execute(text("TRUNCATE TABLE bookings, rooms, users CASCADE"))
    yield


@pytest.fixture
def client(db_engine: Engine) -> Iterator[TestClient]:
    from room_booking.core.db import get_session
    from room_booking.main import app

    def test_session() -> Iterator[Session]:
        with Session(db_engine) as session:
            yield session

    app.dependency_overrides[get_session] = test_session
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def account_factory(db_engine: Engine) -> Callable[..., Account]:
    from room_booking.core.security import create_access_token, hash_password
    from room_booking.users.models import User

    def create_account(role: str = "user", email: str | None = None) -> Account:
        user = User(
            email=email or f"user-{uuid4().hex}@example.com",
            password_hash=hash_password("correct-horse-battery-staple"),
            role=role,
        )
        with Session(db_engine) as session:
            session.add(user)
            session.commit()
            return Account(str(user.id), user.email, create_access_token(user.id))

    return create_account


@pytest.fixture
def user(account_factory: Callable[..., Account]) -> Account:
    return account_factory()


@pytest.fixture
def admin(account_factory: Callable[..., Account]) -> Account:
    return account_factory(role="admin")


@pytest.fixture
def room_factory(client: TestClient, admin: Account) -> Callable[..., dict]:
    def create_room(**overrides: object) -> dict:
        payload = {"name": f"Room {uuid4().hex[:8]}", "capacity": 6, "description": "Meeting room"}
        payload.update(overrides)
        response = client.post("/api/v1/rooms", json=payload, headers=admin.headers)
        assert response.status_code == 201, response.text
        return response.json()

    return create_room
