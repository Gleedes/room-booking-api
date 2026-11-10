from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, func, text
from sqlalchemy.dialects.postgresql import ExcludeConstraint
from sqlalchemy.orm import Mapped, mapped_column

from room_booking.core.db import Base


class Booking(Base):
    __tablename__ = "bookings"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    room_id: Mapped[UUID] = mapped_column(ForeignKey("rooms.id", ondelete="RESTRICT"))
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(16), default="confirmed")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    __table_args__ = (
        CheckConstraint("starts_at < ends_at", name="ck_bookings_interval"),
        CheckConstraint("status IN ('confirmed', 'cancelled')", name="ck_bookings_status"),
        ExcludeConstraint(
            (room_id, "="),
            (func.tstzrange(starts_at, ends_at, "[)"), "&&"),
            where=text("status = 'confirmed'"),
            using="gist",
            name="ex_bookings_room_time",
        ),
        Index("ix_bookings_user_created", "user_id", "created_at"),
    )
