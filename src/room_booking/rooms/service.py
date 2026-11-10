from datetime import datetime
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from room_booking.core.errors import AppError
from room_booking.rooms import repository
from room_booking.rooms.models import Room
from room_booking.rooms.schemas import RoomCreate, RoomUpdate


def get_room(session: Session, room_id: UUID) -> Room:
    room = repository.get_room(session, room_id)
    if room is None:
        raise AppError(404, "Room not found")
    return room


def list_rooms(
    session: Session,
    *,
    min_capacity: int | None,
    starts_at: datetime | None,
    ends_at: datetime | None,
    limit: int,
    offset: int,
) -> tuple[list[Room], int]:
    if (starts_at is None) != (ends_at is None):
        raise AppError(422, "starts_at and ends_at must be provided together")
    if starts_at is not None and ends_at is not None and starts_at >= ends_at:
        raise AppError(422, "starts_at must be earlier than ends_at")
    return repository.list_rooms(
        session,
        min_capacity=min_capacity,
        starts_at=starts_at,
        ends_at=ends_at,
        limit=limit,
        offset=offset,
    )


def create_room(session: Session, data: RoomCreate) -> Room:
    room = Room(**data.model_dump())
    repository.add_room(session, room)
    _commit(session)
    session.refresh(room)
    return room


def update_room(session: Session, room_id: UUID, data: RoomUpdate) -> Room:
    # Booking creation locks the same row before checking whether a room is active.
    room = repository.get_room(session, room_id, for_update=True)
    if room is None:
        raise AppError(404, "Room not found")
    for name, value in data.model_dump(exclude_unset=True).items():
        setattr(room, name, value)
    _commit(session)
    session.refresh(room)
    return room


def _commit(session: Session) -> None:
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        constraint = getattr(getattr(error.orig, "diag", None), "constraint_name", None)
        if constraint == "uq_rooms_name":
            raise AppError(409, "A room with this name already exists") from error
        raise
