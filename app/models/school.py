from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDMixin


class School(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "schools"
    __table_args__ = {"schema": "offlineai"}

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    udise_code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    country_code: Mapped[str | None] = mapped_column(String(10), default="+91", nullable=True)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)

    state_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("offlineai.states.id", ondelete="RESTRICT"),
        index=True,
        nullable=True,
    )
    district_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("offlineai.districts.id", ondelete="RESTRICT"),
        index=True,
        nullable=True,
    )
    ulb_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("offlineai.ulbs.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    ward_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("offlineai.wards.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )

    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", nullable=False)


class SchoolClassSection(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "school_class_sections"
    __table_args__ = (
        UniqueConstraint("school_id", "class_id", "section_id", name="uq_school_class_sections"),
        {"schema": "offlineai"},
    )

    school_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("offlineai.schools.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    class_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("offlineai.classes.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    section_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("offlineai.sections.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    custom_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    custom_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", nullable=False)
