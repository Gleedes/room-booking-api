"""Create users, rooms and reservations with database-enforced conflict protection."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ExcludeConstraint

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("email", name="uq_users_email"),
        sa.CheckConstraint("role IN ('user', 'admin')", name="ck_users_role"),
    )
    op.create_table(
        "rooms",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("name", name="uq_rooms_name"),
        sa.CheckConstraint("capacity > 0", name="ck_rooms_capacity"),
    )
    op.create_table(
        "bookings",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "room_id", sa.Uuid(), sa.ForeignKey("rooms.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("starts_at < ends_at", name="ck_bookings_interval"),
        sa.CheckConstraint("status IN ('confirmed', 'cancelled')", name="ck_bookings_status"),
        ExcludeConstraint(
            ("room_id", "="),
            (sa.text("tstzrange(starts_at, ends_at, '[)')"), "&&"),
            where=sa.text("status = 'confirmed'"),
            using="gist",
            name="ex_bookings_room_time",
        ),
    )
    op.create_index("ix_bookings_user_created", "bookings", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_table("bookings")
    op.drop_table("rooms")
    op.drop_table("users")
