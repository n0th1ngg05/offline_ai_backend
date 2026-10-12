from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDMixin


class UserSchool(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "user_schools"
    __table_args__ = (
        UniqueConstraint("user_id", "school_id", name="uq_user_schools"),
        {"schema": "offlineai"},
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("offlineai.users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    school_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("offlineai.schools.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(50), default="school_admin", nullable=False)


class TeacherQualification(UUIDMixin, Base):
    __tablename__ = "teacher_qualifications"
    __table_args__ = (
        UniqueConstraint("teacher_id", "qualification_id", name="uq_teacher_qualifications"),
        {"schema": "offlineai"},
    )

    teacher_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("offlineai.users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    qualification_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("offlineai.qualifications.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )


class TeacherAssignment(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "teacher_assignments"
    __table_args__ = (
        UniqueConstraint("teacher_id", "school_id", "class_id", "subject_id", name="uq_teacher_assignments"),
        {"schema": "offlineai"},
    )

    teacher_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("offlineai.users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
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
    subject_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("offlineai.subjects.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )


class ClassroomOperatorAssignment(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "classroom_operator_assignments"
    __table_args__ = (
        UniqueConstraint("operator_id", "school_id", "class_id", "section_id", name="uq_operator_assignments"),
        {"schema": "offlineai"},
    )

    operator_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("offlineai.users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
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


class StudentProfile(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "student_profiles"
    __table_args__ = {"schema": "offlineai"}

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("offlineai.users.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
    school_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("offlineai.schools.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    class_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("offlineai.classes.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    section_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("offlineai.sections.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )

    roll_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    academic_year: Mapped[str | None] = mapped_column(String(20), nullable=True)
    gender: Mapped[str | None] = mapped_column(String(20), nullable=True)
    dob: Mapped[date | None] = mapped_column(Date, nullable=True)

    guardian_first_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    guardian_last_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    guardian_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    guardian_country_code: Mapped[str | None] = mapped_column(String(10), default="+91", nullable=True)
    guardian_phone: Mapped[str | None] = mapped_column(String(30), nullable=True)


class RolePermission(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "role_permissions"
    __table_args__ = {"schema": "offlineai"}

    role_name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    readonly: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    permission_codes: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
