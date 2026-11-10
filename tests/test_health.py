from fastapi.testclient import TestClient


def test_health_and_openapi(client: TestClient) -> None:
    assert client.get("/health/live").status_code == 200
    assert client.get("/health/ready").status_code == 200
    assert client.get("/docs").status_code == 200
    schema = client.get("/openapi.json").json()
    assert "/api/v1/bookings" in schema["paths"]
    assert "/api/v1/auth/token" in schema["paths"]


def test_request_ids_and_logs_do_not_expose_credentials(client: TestClient) -> None:
    import logging
    from uuid import UUID

    from room_booking.core.logging import JsonFormatter

    records: list[logging.LogRecord] = []

    class Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    handler = Capture()
    logger = logging.getLogger("room_booking.http")
    logger.addHandler(handler)
    try:
        response = client.post(
            "/api/v1/auth/register?secret=query-secret-marker",
            json={"email": "invalid-email", "password": "password-secret-marker"},
            headers={"Authorization": "Bearer token-secret-marker"},
        )
        assert response.status_code == 422
        UUID(response.headers["x-request-id"])
        assert "password-secret-marker" not in response.text
        assert records
        output = "\n".join(JsonFormatter().format(record) for record in records)
        assert response.headers["x-request-id"] in output
        for secret in ("query-secret-marker", "password-secret-marker", "token-secret-marker"):
            assert secret not in output
    finally:
        logger.removeHandler(handler)
