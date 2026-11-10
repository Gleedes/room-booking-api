from datetime import datetime
from uuid import UUID

from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from room_booking.rooms.models import Room


def get_room(session: Session, room_id: UUID, *, for_update: bool = False) -> Room | None:
    statement = select(Room).where(Room.id == room_id)
    if for_update:
        statement = statement.with_for_update()
    return session.scalar(statement)


def add_room(session: Session, room: Room) -> None:
    session.add(room)


def list_rooms(
    session: Session,
    *,
    min_capacity: int | None,
    starts_at: datetime | None,
    ends_at: datetime | None,
    limit: int,
    offset: int,
) -> tuple[list[Room], int]:
    filters: list[ColumnElement[bool]] = [Room.is_active.is_(True)]
    if min_capacity is not None:
        filters.append(Room.capacity >= min_capacity)
    if starts_at is not None and ends_at is not None:
        from room_booking.bookings.models import Booking

        # Half-open intervals let one booking start when the previous one ends.
        conflict = exists().where(
            Booking.room_id == Room.id,
            Booking.status == "confirmed",
            Booking.starts_at < ends_at,
            Booking.ends_at > starts_at,
        )
        filters.append(~conflict)
    total = session.scalar(select(func.count()).select_from(Room).where(*filters)) or 0
    statement = (
        select(Room).where(*filters).order_by(Room.name, Room.id).limit(limit).offset(offset)
    )
    return list(session.scalars(statement)), total
