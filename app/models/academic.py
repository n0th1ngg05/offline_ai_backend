from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDMixin


class AcademicClass(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "classes"
    __table_args__ = {"schema": "offlineai"}

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    has_streams: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", nullable=False)


class Section(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "sections"
    __table_args__ = {"schema": "offlineai"}

    class_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("offlineai.classes.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", nullable=False)


class Stream(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "streams"
    __table_args__ = {"schema": "offlineai"}

    class_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("offlineai.classes.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", nullable=False)


class Qualification(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "qualifications"
    __table_args__ = {"schema": "offlineai"}

    name: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)
    code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", nullable=False)


class Subject(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "subjects"
    __table_args__ = {"schema": "offlineai"}

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    class_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("offlineai.classes.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )
    school_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("offlineai.schools.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", nullable=False)


class SubjectSection(UUIDMixin, Base):
    __tablename__ = "subject_sections"
    __table_args__ = (
        UniqueConstraint("subject_id", "section_id", name="uq_subject_sections"),
        {"schema": "offlineai"},
    )

    subject_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("offlineai.subjects.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    section_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("offlineai.sections.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )


class Chapter(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "chapters"
    __table_args__ = {"schema": "offlineai"}

    subject_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("offlineai.subjects.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", nullable=False)


class Topic(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "topics"
    __table_args__ = {"schema": "offlineai"}

    chapter_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("offlineai.chapters.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", nullable=False)
