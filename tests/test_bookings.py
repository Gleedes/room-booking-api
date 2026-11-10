from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta, timezone
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from conftest import Account
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


def booking_payload(
    room_id: str, start: datetime | None = None, end: datetime | None = None
) -> dict[str, str]:
    start = start or datetime.now(UTC) + timedelta(days=1)
    end = end or start + timedelta(hours=1)
    return {"room_id": room_id, "starts_at": start.isoformat(), "ends_at": end.isoformat()}


def test_create_read_and_cancel_booking(
    client: TestClient,
    user: Account,
    room_factory: Callable[..., dict],
) -> None:
    room = room_factory()
    # Input offsets are accepted, while API timestamps have a single UTC representation.
    start = (datetime.now(UTC) + timedelta(days=1)).astimezone(timezone(timedelta(hours=3)))
    payload = booking_payload(room["id"], start)
    created = client.post("/api/v1/bookings", json=payload, headers=user.headers)
    assert created.status_code == 201, created.text
    booking = created.json()
    assert booking["status"] == "confirmed"
    assert booking["user_id"] == user.id
    assert datetime.fromisoformat(booking["starts_at"]).utcoffset() == timedelta(0)
    assert (
        client.get(f"/api/v1/bookings/{booking['id']}", headers=user.headers).json()["id"]
        == booking["id"]
    )
    page = client.get("/api/v1/bookings", headers=user.headers).json()
    assert page["total"] == 1 and page["items"][0]["id"] == booking["id"]
    for _ in range(2):
        cancelled = client.post(f"/api/v1/bookings/{booking['id']}/cancel", headers=user.headers)
        assert cancelled.status_code == 200
        assert cancelled.json()["status"] == "cancelled"
    assert client.get("/api/v1/bookings", headers=user.headers).json()["total"] == 1
    assert client.post("/api/v1/bookings", json=payload, headers=user.headers).status_code == 201


def test_booking_ownership_and_admin_access(
    client: TestClient,
    user: Account,
    admin: Account,
    account_factory: Callable[..., Account],
    room_factory: Callable[..., dict],
) -> None:
    other = account_factory()
    room = room_factory()
    booking = client.post(
        "/api/v1/bookings", json=booking_payload(room["id"]), headers=user.headers
    ).json()
    assert client.get("/api/v1/bookings", headers=other.headers).json()["total"] == 0
    assert client.get("/api/v1/bookings", headers=admin.headers).json()["total"] == 1
    for path in [f"/api/v1/bookings/{booking['id']}", f"/api/v1/bookings/{uuid4()}"]:
        assert client.get(path, headers=other.headers).status_code == 404
        assert client.post(f"{path}/cancel", headers=other.headers).status_code == 404
    assert client.get(f"/api/v1/bookings/{booking['id']}", headers=admin.headers).status_code == 200
    assert (
        client.post(f"/api/v1/bookings/{booking['id']}/cancel", headers=admin.headers).status_code
        == 200
    )


def test_overlaps_conflict_but_adjacent_intervals_are_allowed(
    client: TestClient,
    user: Account,
    room_factory: Callable[..., dict],
) -> None:
    room = room_factory()
    other_room = room_factory()
    start = datetime.now(UTC) + timedelta(days=1)
    end = start + timedelta(hours=1)
    assert (
        client.post(
            "/api/v1/bookings", json=booking_payload(room["id"], start, end), headers=user.headers
        ).status_code
        == 201
    )
    for overlap_start, overlap_end in [
        (start, end),
        (start - timedelta(minutes=30), end),
        (start + timedelta(minutes=15), end - timedelta(minutes=15)),
    ]:
        response = client.post(
            "/api/v1/bookings",
            json=booking_payload(room["id"], overlap_start, overlap_end),
            headers=user.headers,
        )
        assert response.status_code == 409, response.text
    assert (
        client.post(
            "/api/v1/bookings",
            json=booking_payload(room["id"], end, end + timedelta(hours=1)),
            headers=user.headers,
        ).status_code
        == 201
    )
    assert (
        client.post(
            "/api/v1/bookings",
            json=booking_payload(other_room["id"], start, end),
            headers=user.headers,
        ).status_code
        == 201
    )


def test_invalid_booking_dates_and_missing_room(
    client: TestClient,
    user: Account,
    room_factory: Callable[..., dict],
) -> None:
    room = room_factory()
    start = datetime.now(UTC) + timedelta(days=1)
    for overrides in [
        {"starts_at": (start - timedelta(days=2)).isoformat()},
        {"ends_at": start.isoformat()},
        {"ends_at": (start - timedelta(minutes=1)).isoformat()},
        {"starts_at": "2030-01-01T10:00:00", "ends_at": "2030-01-01T11:00:00"},
    ]:
        payload = booking_payload(room["id"], start)
        payload.update(overrides)
        assert (
            client.post("/api/v1/bookings", json=payload, headers=user.headers).status_code == 422
        )
    assert (
        client.post(
            "/api/v1/bookings",
            json=booking_payload(str(uuid4())),
            headers=user.headers,
        ).status_code
        == 404
    )
    assert client.post("/api/v1/bookings", json=booking_payload(room["id"])).status_code == 401


def test_deactivation_preserves_bookings_and_blocks_new_ones(
    client: TestClient,
    user: Account,
    admin: Account,
    room_factory: Callable[..., dict],
) -> None:
    room = room_factory()
    start = datetime.now(UTC) + timedelta(days=1)
    booking = client.post(
        "/api/v1/bookings",
        json=booking_payload(room["id"], start),
        headers=user.headers,
    ).json()
    assert (
        client.patch(
            f"/api/v1/rooms/{room['id']}",
            json={"is_active": False},
            headers=admin.headers,
        ).status_code
        == 200
    )
    preserved = client.get(f"/api/v1/bookings/{booking['id']}", headers=user.headers)
    assert preserved.status_code == 200 and preserved.json()["status"] == "confirmed"
    assert (
        client.post(
            "/api/v1/bookings",
            json=booking_payload(room["id"], start + timedelta(days=1)),
            headers=user.headers,
        ).status_code
        == 409
    )


def test_simultaneous_requests_cannot_double_book(
    client: TestClient,
    user: Account,
    room_factory: Callable[..., dict],
    db_engine: Engine,
) -> None:
    from room_booking.bookings.models import Booking
    from room_booking.main import app

    room = room_factory()
    payload = booking_payload(room["id"])
    barrier = Barrier(2)

    def reserve() -> int:
        # Each client has its own request and DB session; neither session is shared across threads.
        with TestClient(app) as concurrent_client:
            barrier.wait(timeout=10)
            return concurrent_client.post(
                "/api/v1/bookings", json=payload, headers=user.headers
            ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: reserve(), range(2)))
    assert sorted(results) == [201, 409]
    with Session(db_engine) as session:
        bookings = session.scalars(select(Booking).where(Booking.room_id == UUID(room["id"]))).all()
        assert len(bookings) == 1


def test_database_rejects_overlap_even_without_api(
    client: TestClient,
    user: Account,
    room_factory: Callable[..., dict],
    db_engine: Engine,
) -> None:
    from room_booking.bookings.models import Booking

    room = room_factory()
    payload = booking_payload(room["id"])
    assert client.post("/api/v1/bookings", json=payload, headers=user.headers).status_code == 201
    with Session(db_engine) as session:
        session.add(
            Booking(
                room_id=UUID(room["id"]),
                user_id=UUID(user.id),
                starts_at=datetime.fromisoformat(payload["starts_at"]),
                ends_at=datetime.fromisoformat(payload["ends_at"]),
                status="confirmed",
            )
        )
        with pytest.raises(IntegrityError) as error:
            session.commit()
        assert getattr(error.value.orig, "sqlstate", None) == "23P01"
        session.rollback()


def test_booking_waits_for_concurrent_room_deactivation(
    client: TestClient,
    user: Account,
    room_factory: Callable[..., dict],
    db_engine: Engine,
) -> None:
    from time import monotonic, sleep

    from sqlalchemy import text

    from room_booking.bookings.models import Booking
    from room_booking.core.db import get_session
    from room_booking.main import app
    from room_booking.rooms.models import Room

    room = room_factory()
    original_override = app.dependency_overrides[get_session]

    def named_session():
        with Session(db_engine) as session:
            session.execute(text("SET LOCAL application_name = 'booking_deactivation_test'"))
            yield session

    app.dependency_overrides[get_session] = named_session
    try:
        with Session(db_engine) as deactivation:
            locked_room = deactivation.scalar(
                select(Room).where(Room.id == UUID(room["id"])).with_for_update()
            )
            assert locked_room is not None
            locked_room.is_active = False
            deactivation.flush()
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(
                    client.post,
                    "/api/v1/bookings",
                    json=booking_payload(room["id"]),
                    headers=user.headers,
                )
                try:
                    deadline = monotonic() + 10
                    blocked = False
                    while monotonic() < deadline and not future.done():
                        with db_engine.connect() as connection:
                            blocked = bool(
                                connection.scalar(
                                    text(
                                        "SELECT EXISTS (SELECT 1 FROM pg_stat_activity "
                                        "WHERE application_name = 'booking_deactivation_test' "
                                        "AND wait_event_type = 'Lock')"
                                    )
                                )
                            )
                        if blocked:
                            break
                        sleep(0.02)
                    assert blocked, "Booking must wait for the room update transaction to finish"
                finally:
                    deactivation.commit()
                response = future.result(timeout=10)
                assert response.status_code == 409, response.text
        with Session(db_engine) as session:
            assert (
                session.scalar(select(Booking).where(Booking.room_id == UUID(room["id"]))) is None
            )
    finally:
        app.dependency_overrides[get_session] = original_override
