# Room Booking API

[![CI](https://github.com/Gleedes/room-booking-api/actions/workflows/ci.yml/badge.svg)](https://github.com/Gleedes/room-booking-api/actions/workflows/ci.yml)

A meeting room reservation API with user/admin roles, availability search and cancellation. PostgreSQL exclusion constraints prevent overlapping bookings, including concurrent requests. Adjacent reservations are allowed.

**Stack:** Python 3.14, FastAPI, Pydantic 2, SQLAlchemy 2, PostgreSQL 18, Alembic, uv, Docker, pytest, Ruff, mypy and GitHub Actions.

## Run

Install [Docker Desktop](https://docs.docker.com/desktop/setup/install/mac-install/) and Python 3.14, then:

```sh
git clone https://github.com/Gleedes/room-booking-api.git
cd room-booking-api
python3 scripts/init_env.py
docker compose up --build -d
docker compose exec api python -m room_booking.cli create-admin --email admin@example.com
```

Open [Swagger UI](http://localhost:8000/docs). Sign in using `POST /api/v1/auth/token` (the `username` field is your email), or Swagger's **Authorize** button. An administrator creates rooms; users search and book them. Passwords must contain 12–128 characters. Access tokens expire after 30 minutes; sign in again to renew.

```sh
curl -X POST localhost:8000/api/v1/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"email":"user@example.com","password":"a-long-example-password"}'
curl -X POST localhost:8000/api/v1/auth/token \
  -d 'username=user@example.com&password=a-long-example-password'
# Set TOKEN to the returned access_token; ROOM_ID to an existing room UUID.
curl localhost:8000/api/v1/rooms -H "Authorization: Bearer $TOKEN"
# Replace dates with a future interval. Include Z or an explicit timezone offset.
curl -X POST localhost:8000/api/v1/bookings \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"room_id":"ROOM_ID","starts_at":"2030-01-01T10:00:00Z","ends_at":"2030-01-01T11:00:00Z"}'
curl -X POST localhost:8000/api/v1/bookings/BOOKING_ID/cancel \
  -H "Authorization: Bearer $TOKEN"
```

Lists use `limit`/`offset`. Availability search accepts `min_capacity` and a paired `starts_at`/`ends_at`. Times are returned in UTC. Deactivating a room prevents new bookings and preserves existing ones. Cancellation is repeatable and retains history.

## Checks

```sh
# Isolated, temporary PostgreSQL database; does not modify application data.
docker compose --profile test run --build --rm tests
docker compose --profile test stop test-db
```

With [uv](https://docs.astral.sh/uv/), local checks are:

```sh
uv sync --locked
uv run ruff check .
uv run ruff format --check .
uv run mypy src
# TEST_DATABASE_URL must point to a disposable PostgreSQL database ending in _test.
TEST_DATABASE_URL='postgresql+psycopg://user:password@localhost:5432/booking_test' uv run pytest
uv run alembic check
```

Feature modules separate HTTP schemas/routes, business operations and database queries. Business operations own transactions; Alembic owns the schema. `/health/live` and `/health/ready` expose health checks. `.env` contains generated local secrets and is never committed. `docker compose down` preserves database data; adding `-v` deletes it.

This version runs locally: no frontend, email delivery, password recovery or cloud deployment. Public hosting additionally requires HTTPS, login abuse protection, backups and deployment-specific secret management.
