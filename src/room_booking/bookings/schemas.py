from datetime import UTC, datetime
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, field_validator, model_validator

AwareTimestamp = Annotated[datetime, AwareDatetime()]


class BookingCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    room_id: UUID
    starts_at: AwareTimestamp
    ends_at: AwareTimestamp

    @field_validator("starts_at", "ends_at")
    @classmethod
    def normalize_utc(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_interval(self) -> Self:
        if self.starts_at >= self.ends_at:
            raise ValueError("starts_at must be before ends_at")
        return self


class BookingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    room_id: UUID
    user_id: UUID
    starts_at: datetime
    ends_at: datetime
    status: Literal["confirmed", "cancelled"]
    created_at: datetime

    @field_validator("starts_at", "ends_at", "created_at")
    @classmethod
    def normalize_utc(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)


class BookingPage(BaseModel):
    items: list[BookingRead]
    total: int
    limit: int
    offset: int
