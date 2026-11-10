from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from conftest import Account
from fastapi.testclient import TestClient


def test_room_management_requires_admin(
    client: TestClient,
    user: Account,
    admin: Account,
    room_factory: Callable[..., dict],
) -> None:
    payload = {"name": "Board room", "capacity": 10}
    assert client.post("/api/v1/rooms", json=payload).status_code == 401
    assert client.post("/api/v1/rooms", json=payload, headers=user.headers).status_code == 403
    room = room_factory()
    assert (
        client.patch(
            f"/api/v1/rooms/{room['id']}",
            json={"capacity": 12},
            headers=user.headers,
        ).status_code
        == 403
    )
    updated = client.patch(
        f"/api/v1/rooms/{room['id']}",
        json={"capacity": 12, "description": "Updated"},
        headers=admin.headers,
    )
    assert updated.status_code == 200
    assert updated.json()["capacity"] == 12
    assert updated.json()["description"] == "Updated"


def test_room_filtering_pagination_and_deactivation(
    client: TestClient,
    user: Account,
    admin: Account,
    room_factory: Callable[..., dict],
) -> None:
    room_factory(capacity=2)
    large = room_factory(capacity=12)
    room_factory(capacity=16)
    response = client.get(
        "/api/v1/rooms", params={"min_capacity": 10, "limit": 1}, headers=user.headers
    )
    assert response.status_code == 200
    page = response.json()
    assert page["total"] == 2 and len(page["items"]) == 1
    assert page["limit"] == 1 and page["offset"] == 0
    next_page = client.get(
        "/api/v1/rooms",
        params={"min_capacity": 10, "limit": 1, "offset": 1},
        headers=user.headers,
    ).json()
    assert next_page["items"][0]["id"] != page["items"][0]["id"]
    assert (
        client.patch(
            f"/api/v1/rooms/{large['id']}",
            json={"is_active": False},
            headers=admin.headers,
        ).status_code
        == 200
    )
    active = client.get("/api/v1/rooms", headers=user.headers).json()
    assert active["total"] == 2
    assert large["id"] not in [room["id"] for room in active["items"]]
    assert client.get(f"/api/v1/rooms/{large['id']}", headers=user.headers).status_code == 200


def test_room_validation(
    client: TestClient, admin: Account, room_factory: Callable[..., dict]
) -> None:
    for payload in [{"name": "Empty", "capacity": 0}, {"name": " ", "capacity": 5}]:
        assert client.post("/api/v1/rooms", json=payload, headers=admin.headers).status_code == 422
    existing = room_factory()
    assert (
        client.post(
            "/api/v1/rooms",
            json={"name": existing["name"], "capacity": 5},
            headers=admin.headers,
        ).status_code
        == 409
    )
    for params in [{"limit": 0}, {"offset": -1}, {"min_capacity": 0}]:
        assert client.get("/api/v1/rooms", params=params, headers=admin.headers).status_code == 422


def test_availability_search_matches_booking_boundaries(
    client: TestClient,
    user: Account,
    room_factory: Callable[..., dict],
) -> None:
    booked_room = room_factory()
    free_room = room_factory()
    start = datetime.now(UTC) + timedelta(days=1)
    end = start + timedelta(hours=1)
    assert (
        client.post(
            "/api/v1/bookings",
            headers=user.headers,
            json={
                "room_id": booked_room["id"],
                "starts_at": start.isoformat(),
                "ends_at": end.isoformat(),
            },
        ).status_code
        == 201
    )
    overlapping = client.get(
        "/api/v1/rooms",
        headers=user.headers,
        params={"starts_at": start.isoformat(), "ends_at": end.isoformat()},
    )
    assert overlapping.status_code == 200, overlapping.text
    assert [room["id"] for room in overlapping.json()["items"]] == [free_room["id"]]
    adjacent = client.get(
        "/api/v1/rooms",
        headers=user.headers,
        params={"starts_at": end.isoformat(), "ends_at": (end + timedelta(hours=1)).isoformat()},
    )
    assert adjacent.status_code == 200
    assert adjacent.json()["total"] == 2
    for params in [
        {"starts_at": start.isoformat()},
        {"ends_at": end.isoformat()},
        {"starts_at": end.isoformat(), "ends_at": start.isoformat()},
        {"starts_at": "2030-01-01T10:00:00", "ends_at": "2030-01-01T11:00:00"},
    ]:
        assert client.get("/api/v1/rooms", params=params, headers=user.headers).status_code == 422
