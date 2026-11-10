from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from room_booking.bookings import repository
from room_booking.bookings.models import Booking
from room_booking.bookings.schemas import BookingCreate
from room_booking.core.errors import AppError
from room_booking.users.models import User


def create_booking(session: Session, payload: BookingCreate, user: User) -> Booking:
    if payload.starts_at <= datetime.now(UTC):
        raise AppError(422, "Booking must start in the future")
    # Room updates acquire this same lock so deactivation cannot race a new booking.
    room = repository.lock_room(session, payload.room_id)
    if room is None:
        raise AppError(404, "Room not found")
    if not room.is_active:
        raise AppError(409, "Room is inactive")
    booking = repository.add_booking(session, payload, user.id)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        if (
            getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
            == "ex_bookings_room_time"
        ):
            raise AppError(409, "Room is already booked for this interval") from exc
        raise
    session.refresh(booking)
    return booking


def get_booking(session: Session, booking_id: UUID, user: User) -> Booking:
    booking = repository.find_booking(session, booking_id)
    if booking is None or (booking.user_id != user.id and user.role != "admin"):
        raise AppError(404, "Booking not found")
    return booking


def cancel_booking(session: Session, booking_id: UUID, user: User) -> Booking:
    booking = repository.find_booking(session, booking_id, for_update=True)
    if booking is None or (booking.user_id != user.id and user.role != "admin"):
        raise AppError(404, "Booking not found")
    booking.status = "cancelled"
    session.commit()
    session.refresh(booking)
    return booking


def list_bookings(
    session: Session, user: User, *, limit: int, offset: int
) -> tuple[list[Booking], int]:
    return repository.list_bookings(
        session, user_id=None if user.role == "admin" else user.id, limit=limit, offset=offset
    )
