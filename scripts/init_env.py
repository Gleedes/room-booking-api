"""Generate local development secrets; never replace an existing environment file."""

import secrets
from pathlib import Path

path = Path(__file__).resolve().parents[1] / ".env"
password = secrets.token_hex(24)
try:
    with path.open("x") as env:
        path.chmod(0o600)
        env.write(
            f"POSTGRES_PASSWORD={password}\n"
            f"DATABASE_URL=postgresql+psycopg://booking:{password}@localhost:5432/booking\n"
            f"JWT_SECRET={secrets.token_hex(32)}\n"
        )
except FileExistsError:
    print(".env already exists; keeping existing configuration.")
else:
    print("Created .env with local secrets.")
