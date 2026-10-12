from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDMixin


class UserStatus:
    """Native Postgres enum values — uppercase, matching what offline_ai's
    OfflineUser mirror model already expects when it compares
    `user.status != "ACTIVE"` as a raw string (see that repo's
    app/core/security.py). Not a Python enum class deliberately — kept as
    plain string constants so SQLAlchemy's Enum(..., native_enum=True) maps
    cleanly to the Postgres-native `offlineai.user_status` type created in
    sql/init.sql, without the lowercase-vs-uppercase mismatch that repo's
    OWN public.users table has relative to its mirror of this table."""

    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    DELETED = "DELETED"


# user_type is intentionally a plain String, not a DB-level enum — the set
# of roles is expected to grow in future phases (school_admin, teacher,
# student, etc. already named in the frontend's src/utils/roles.js) and a
# plain string avoids a migration every time a new role is introduced.
# Validity of the value is enforced at the Pydantic schema layer
# (app/schemas/auth.py) and application logic, not a DB constraint, for
# this reason.


class User(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "users"
    __table_args__ = {"schema": "offlineai"}

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(Text, nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    username: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True)
    country_code: Mapped[str | None] = mapped_column(String(10), default="+91", nullable=True)
    phone_number: Mapped[str | None] = mapped_column(String(30), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(30), unique=True, nullable=True)
    gender: Mapped[str | None] = mapped_column(String(20), nullable=True)

    user_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    status: Mapped[str] = mapped_column(
        Enum(
            "ACTIVE",
            "INACTIVE",
            "DELETED",
            name="user_status",
            schema="offlineai",
            native_enum=True,
        ),
        default=UserStatus.ACTIVE,
        nullable=False,
    )

    is_first_login: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    profile_picture_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("offlineai.users.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()
