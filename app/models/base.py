from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base for all ORM models in this service."""

    pass


class UUIDMixin:
    """Native Postgres UUID primary key — NOT the String(36) style used by
    offline_ai's own tables (app/models/base.py there). This service's
    tables are meant to BE the real `offlineai.users` table that
    offline_ai's app/models/offlineai_core.py already reads as a read-only
    mirror, and that mirror declares `id = Column(UUID(as_uuid=True),
    primary_key=True)` — so this must match exactly, native UUID type, for
    that mirror to resolve against real data with zero changes on that
    side."""

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class SoftDeleteMixin:
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True, nullable=True
    )
    deleted_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), index=True, nullable=True
    )

    @hybrid_property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    @is_deleted.setter
    def is_deleted(self, value: bool) -> None:
        if value:
            if self.deleted_at is None:
                self.deleted_at = datetime.now(timezone.utc)
        else:
            self.deleted_at = None
            self.deleted_by = None

    @is_deleted.inplace.expression
    @classmethod
    def _is_deleted_expr(cls):
        return cls.deleted_at.is_not(None)

    def soft_delete(self, *, deleted_by: uuid.UUID) -> None:
        self.deleted_at = datetime.now(timezone.utc)
        self.deleted_by = deleted_by

    def restore(self) -> None:
        self.deleted_at = None
        self.deleted_by = None

