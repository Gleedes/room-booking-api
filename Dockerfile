FROM ghcr.io/astral-sh/uv:0.13.7 AS uv
FROM python:3.14-slim AS base
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 UV_LINK_MODE=copy
WORKDIR /app
COPY --from=uv /uv /uvx /bin/
COPY pyproject.toml uv.lock README.md ./
COPY src ./src

FROM base AS test
RUN uv sync --frozen
ENV PATH="/app/.venv/bin:$PATH"
COPY alembic.ini ./
COPY migrations ./migrations
COPY tests ./tests
CMD ["pytest", "-q"]

FROM base AS builder
RUN uv sync --frozen --no-dev --no-editable

FROM python:3.14-slim AS runtime
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PATH="/app/.venv/bin:$PATH"
WORKDIR /app
RUN groupadd --system app && useradd --system --gid app --no-create-home app
COPY --from=builder /app/.venv ./.venv
COPY alembic.ini ./
COPY migrations ./migrations
USER app
EXPOSE 8000
CMD ["uvicorn", "room_booking.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
