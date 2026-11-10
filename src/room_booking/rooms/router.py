from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from pydantic import AwareDatetime

from room_booking.core.dependencies import CurrentUser, SessionDep, require_admin
from room_booking.rooms import service
from room_booking.rooms.schemas import RoomCreate, RoomPage, RoomRead, RoomUpdate

AwareTimestamp = Annotated[datetime, AwareDatetime()]

router = APIRouter(prefix="/rooms", tags=["rooms"])


@router.get("", response_model=RoomPage)
def list_rooms(
    session: SessionDep,
    _user: CurrentUser,
    min_capacity: Annotated[int | None, Query(ge=1)] = None,
    starts_at: Annotated[AwareTimestamp | None, Query()] = None,
    ends_at: Annotated[AwareTimestamp | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> RoomPage:
    rooms, total = service.list_rooms(
        session,
        min_capacity=min_capacity,
        starts_at=starts_at,
        ends_at=ends_at,
        limit=limit,
        offset=offset,
    )
    return RoomPage(
        items=[RoomRead.model_validate(room) for room in rooms],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{room_id}", response_model=RoomRead)
def get_room(room_id: UUID, session: SessionDep, _user: CurrentUser) -> RoomRead:
    return RoomRead.model_validate(service.get_room(session, room_id))


@router.post(
    "",
    response_model=RoomRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
)
def create_room(data: RoomCreate, session: SessionDep) -> RoomRead:
    return RoomRead.model_validate(service.create_room(session, data))


@router.patch("/{room_id}", response_model=RoomRead, dependencies=[Depends(require_admin)])
def update_room(room_id: UUID, data: RoomUpdate, session: SessionDep) -> RoomRead:
    return RoomRead.model_validate(service.update_room(session, room_id, data))
