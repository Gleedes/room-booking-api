from alembic import context
from sqlalchemy import create_engine, pool

from room_booking.bookings.models import Booking  # noqa: F401
from room_booking.core.config import get_settings
from room_booking.core.db import Base
from room_booking.rooms.models import Room  # noqa: F401
from room_booking.users.models import User  # noqa: F401

config = context.config
target_metadata = Base.metadata
url = config.get_main_option("sqlalchemy.url") or get_settings().database_url

if context.is_offline_mode():
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = create_engine(url, poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()
