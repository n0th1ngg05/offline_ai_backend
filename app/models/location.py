from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDMixin


class State(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "states"
    __table_args__ = {"schema": "offlineai"}

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", nullable=False)


class District(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "districts"
    __table_args__ = (
        UniqueConstraint("state_id", "code", name="uq_districts_state_code"),
        {"schema": "offlineai"},
    )

    state_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("offlineai.states.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", nullable=False)


class Ulb(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "ulbs"
    __table_args__ = (
        UniqueConstraint("district_id", "code", name="uq_ulbs_district_code"),
        {"schema": "offlineai"},
    )

    district_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("offlineai.districts.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", nullable=False)


class Ward(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "wards"
    __table_args__ = (
        UniqueConstraint("ulb_id", "code", name="uq_wards_ulb_code"),
        {"schema": "offlineai"},
    )

    ulb_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("offlineai.ulbs.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", nullable=False)
