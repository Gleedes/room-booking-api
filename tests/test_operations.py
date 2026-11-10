from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from pydantic import ValidationError
from sqlalchemy import Engine, inspect, select
from sqlalchemy.orm import Session


def test_create_admin_cli_hashes_password_and_rejects_duplicates(
    db_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from room_booking import cli
    from room_booking.core.security import verify_password
    from room_booking.users.models import User

    password = "cli-test-password-never-a-real-secret"
    monkeypatch.setattr(
        "sys.argv", ["room-booking", "create-admin", "--email", "Admin@Example.com"]
    )
    monkeypatch.setattr(cli, "get_engine", lambda: db_engine)
    monkeypatch.setattr(cli, "getpass", lambda _prompt: password)
    cli.main()
    with Session(db_engine) as session:
        admin = session.scalar(select(User).where(User.email == "admin@example.com"))
        assert admin is not None and admin.role == "admin"
        assert admin.password_hash != password
        assert verify_password(password, admin.password_hash)
    output = capsys.readouterr()
    assert "Administrator created" in output.out
    assert password not in output.out + output.err
    with pytest.raises(SystemExit) as exit_info:
        cli.main()
    assert exit_info.value.code == 1
    with Session(db_engine) as session:
        assert len(session.scalars(select(User)).all()) == 1


def test_create_admin_cli_rejects_password_mismatch(
    db_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from room_booking import cli
    from room_booking.users.models import User

    monkeypatch.setattr(
        "sys.argv", ["room-booking", "create-admin", "--email", "admin@example.com"]
    )
    monkeypatch.setattr(cli, "get_engine", lambda: db_engine)
    passwords = iter(["long-enough-test-password", "different-test-password"])
    monkeypatch.setattr(cli, "getpass", lambda _prompt: next(passwords))
    with pytest.raises(SystemExit) as exit_info:
        cli.main()
    assert exit_info.value.code == 1
    with Session(db_engine) as session:
        assert session.scalar(select(User)) is None


def test_settings_require_strong_secret_and_hide_it_in_representation() -> None:
    from room_booking.core.config import Settings

    secret = "test-signing-key-with-at-least-32-characters"
    settings = Settings(
        database_url="postgresql+psycopg://localhost/booking_test", jwt_secret=secret
    )
    assert secret not in repr(settings)
    with pytest.raises(ValidationError):
        Settings(database_url="postgresql+psycopg://localhost/booking_test", jwt_secret="weak")
    with pytest.raises(ValidationError):
        Settings(
            database_url="postgresql+psycopg://localhost/booking_test",
            jwt_secret=secret,
            access_token_expire_minutes=0,
        )


def test_migrations_can_downgrade_and_recreate_schema(db_engine: Engine) -> None:
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.set_main_option(
        "sqlalchemy.url",
        db_engine.url.render_as_string(hide_password=False).replace("%", "%%"),
    )
    try:
        command.downgrade(config, "base")
        assert not {"users", "rooms", "bookings"}.intersection(inspect(db_engine).get_table_names())
    finally:
        # Restore even on assertion failure so later tests still get an intact test schema.
        command.upgrade(config, "head")
    assert {"users", "rooms", "bookings"} <= set(inspect(db_engine).get_table_names())
    command.check(config)
