from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from room_booking.bookings.models import Booking
from room_booking.bookings.schemas import BookingCreate
from room_booking.rooms.models import Room


def lock_room(session: Session, room_id: UUID) -> Room | None:
    return session.scalar(select(Room).where(Room.id == room_id).with_for_update())


def add_booking(session: Session, payload: BookingCreate, user_id: UUID) -> Booking:
    booking = Booking(
        room_id=payload.room_id,
        user_id=user_id,
        starts_at=payload.starts_at,
        ends_at=payload.ends_at,
    )
    session.add(booking)
    return booking


def find_booking(session: Session, booking_id: UUID, *, for_update: bool = False) -> Booking | None:
    query = select(Booking).where(Booking.id == booking_id)
    if for_update:
        query = query.with_for_update()
    return session.scalar(query)


def list_bookings(
    session: Session, *, user_id: UUID | None, limit: int, offset: int
) -> tuple[list[Booking], int]:
    query = select(Booking)
    count_query = select(func.count()).select_from(Booking)
    if user_id is not None:
        query = query.where(Booking.user_id == user_id)
        count_query = count_query.where(Booking.user_id == user_id)
    items = list(
        session.scalars(
            query.order_by(Booking.created_at.desc(), Booking.id).limit(limit).offset(offset)
        )
    )
    return items, session.scalar(count_query) or 0
