from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, status

from room_booking.bookings import service
from room_booking.bookings.models import Booking
from room_booking.bookings.schemas import BookingCreate, BookingPage, BookingRead
from room_booking.core.dependencies import CurrentUser, SessionDep

router = APIRouter(prefix="/bookings", tags=["Bookings"])


@router.post("", response_model=BookingRead, status_code=status.HTTP_201_CREATED)
def create_booking(payload: BookingCreate, session: SessionDep, user: CurrentUser) -> Booking:
    return service.create_booking(session, payload, user)


@router.get("", response_model=BookingPage)
def list_bookings(
    session: SessionDep,
    user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> BookingPage:
    items, total = service.list_bookings(session, user, limit=limit, offset=offset)
    return BookingPage(
        items=[BookingRead.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{booking_id}", response_model=BookingRead)
def get_booking(booking_id: UUID, session: SessionDep, user: CurrentUser) -> Booking:
    return service.get_booking(session, booking_id, user)


@router.post("/{booking_id}/cancel", response_model=BookingRead)
def cancel_booking(booking_id: UUID, session: SessionDep, user: CurrentUser) -> Booking:
    return service.cancel_booking(session, booking_id, user)
