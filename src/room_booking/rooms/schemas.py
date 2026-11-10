from datetime import UTC, datetime
from typing import Annotated, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_serializer, model_validator

RoomName = Annotated[str, Field(min_length=1, max_length=100)]
RoomDescription = Annotated[str, Field(max_length=2000)]
RoomCapacity = Annotated[int, Field(gt=0, strict=True)]


class RoomCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: RoomName
    description: RoomDescription = ""
    capacity: RoomCapacity


class RoomUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: RoomName | None = None
    description: RoomDescription | None = None
    capacity: RoomCapacity | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def reject_explicit_null(self) -> Self:
        for name in self.model_fields_set:
            if getattr(self, name) is None:
                raise ValueError(f"{name} must not be null")
        return self


class RoomRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str
    capacity: int
    is_active: bool
    created_at: datetime

    @field_serializer("created_at")
    def serialize_created_at(self, value: datetime) -> datetime:
        return value.astimezone(UTC)


class RoomPage(BaseModel):
    items: list[RoomRead]
    total: int
    limit: int
    offset: int
