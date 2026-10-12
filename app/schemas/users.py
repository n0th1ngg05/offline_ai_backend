"""
Pydantic request schemas for all User Management roles:
- School Admins (/api/v1/user/school)
- Content Admins (/api/v1/user/content)
- Generic Users (/api/v1/users)
- Teachers (/api/v1/user/teacher)
- Classroom Operators (/api/v1/user/class-room)
- Students (/api/v1/user/student)
- Role Permissions (/api/v1/role-permissions/{role_id})
"""

from __future__ import annotations

import re
import uuid
from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

MAX_BCRYPT_PASSWORD_BYTES = 72


class PasswordCheckMixin(BaseModel):
    model_config = ConfigDict(extra="allow")

    @field_validator("password", check_fields=False)
    @classmethod
    def validate_password_byte_length(cls, value: str | None) -> str | None:
        if value is not None and value.strip() != "":
            if len(value.encode("utf-8")) > MAX_BCRYPT_PASSWORD_BYTES:
                raise ValueError("Password cannot exceed 72 bytes.")
            if len(value) < 8:
                raise ValueError("Password must be at least 8 characters long.")
            if not re.search(r"[A-Z]", value):
                raise ValueError("Password must contain at least one uppercase letter.")
            if not re.search(r"[a-z]", value):
                raise ValueError("Password must contain at least one lowercase letter.")
            if not re.search(r"\d", value):
                raise ValueError("Password must contain at least one number.")
            if not re.search(r"[^A-Za-z0-9]", value):
                raise ValueError("Password must contain at least one special character.")
        return value


# ==============================================================================
# School Admin (/api/v1/user/school) & Content Admin (/api/v1/user/content)
# ==============================================================================

class SchoolAdminCreateRequest(PasswordCheckMixin):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(default="", max_length=100)
    email: EmailStr
    country_code: str | None = "+91"
    phone_number: str | None = None
    phone: str | None = None
    password: str | None = None
    status: str = "ACTIVE"
    school_ids: list[uuid.UUID] = Field(default_factory=list)


class SchoolAdminUpdateRequest(PasswordCheckMixin):
    first_name: str | None = None
    last_name: str | None = None
    email: EmailStr | None = None
    country_code: str | None = None
    phone_number: str | None = None
    phone: str | None = None
    password: str | None = None
    status: str | None = None
    school_ids: list[uuid.UUID] | None = None
    removed_relations: list[uuid.UUID] = Field(default_factory=list)


class ContentAdminCreateRequest(PasswordCheckMixin):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(default="", max_length=100)
    email: EmailStr
    country_code: str | None = "+91"
    phone_number: str | None = None
    phone: str | None = None
    password: str | None = None
    status: str = "ACTIVE"


class ContentAdminUpdateRequest(PasswordCheckMixin):
    first_name: str | None = None
    last_name: str | None = None
    email: EmailStr | None = None
    country_code: str | None = None
    phone_number: str | None = None
    phone: str | None = None
    password: str | None = None
    status: str | None = None


class GenericUserCreateRequest(PasswordCheckMixin):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(default="", max_length=100)
    email: EmailStr
    country_code: str | None = "+91"
    phone_number: str | None = None
    phone: str | None = None
    role_id: str | None = None
    user_type: str | None = None
    role: str | None = None
    password: str | None = None
    status: str = "ACTIVE"
    school_ids: list[uuid.UUID] = Field(default_factory=list)


class GenericUserUpdateRequest(PasswordCheckMixin):
    first_name: str | None = None
    last_name: str | None = None
    email: EmailStr | None = None
    country_code: str | None = None
    phone_number: str | None = None
    phone: str | None = None
    role_id: str | None = None
    user_type: str | None = None
    role: str | None = None
    password: str | None = None
    status: str | None = None
    school_ids: list[uuid.UUID] | None = None
    removed_relations: list[uuid.UUID] = Field(default_factory=list)


# ==============================================================================
# Teacher (/api/v1/user/teacher)
# ==============================================================================

class TeacherCreateRequest(PasswordCheckMixin):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(default="", max_length=100)
    email: EmailStr
    country_code: str | None = "+91"
    phone_number: str | None = None
    phone: str | None = None
    gender: str | None = None
    password: str | None = None
    status: str = "ACTIVE"
    qualification_ids: list[uuid.UUID] = Field(default_factory=list)
    assignments: list[dict[str, Any]] = Field(default_factory=list)


class TeacherUpdateRequest(PasswordCheckMixin):
    first_name: str | None = None
    last_name: str | None = None
    email: EmailStr | None = None
    country_code: str | None = None
    phone_number: str | None = None
    phone: str | None = None
    gender: str | None = None
    password: str | None = None
    status: str | None = None
    qualification_ids: list[uuid.UUID] | None = None
    removed_qualification_ids: list[uuid.UUID] = Field(default_factory=list)
    assignments: list[dict[str, Any]] | None = None
    removed_assignments: list[dict[str, Any]] = Field(default_factory=list)


# ==============================================================================
# Classroom Operator (/api/v1/user/class-room)
# ==============================================================================

class ClassroomOperatorCreateRequest(PasswordCheckMixin):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(default="", max_length=100)
    email: EmailStr
    country_code: str | None = "+91"
    phone_number: str | None = None
    phone: str | None = None
    password: str | None = None
    status: str = "ACTIVE"
    school_id: uuid.UUID | None = None
    assignments: list[dict[str, Any]] = Field(default_factory=list)


class ClassroomOperatorUpdateRequest(PasswordCheckMixin):
    first_name: str | None = None
    last_name: str | None = None
    email: EmailStr | None = None
    country_code: str | None = None
    phone_number: str | None = None
    phone: str | None = None
    password: str | None = None
    status: str | None = None
    school_id: uuid.UUID | None = None
    assignments: list[dict[str, Any]] | None = None
    removed_assignments: list[dict[str, Any]] = Field(default_factory=list)


# ==============================================================================
# Student (/api/v1/user/student)
# Supports both camelCase (sent by CreateStudentPage.helpers.js) and snake_case
# ==============================================================================

class StudentCreateRequest(PasswordCheckMixin):
    # Student name
    firstName: str | None = None
    lastName: str | None = None
    first_name: str | None = None
    last_name: str | None = None

    # Academic placement
    academicYear: str | None = None
    academic_year: str | None = None
    school_id: uuid.UUID
    class_id: uuid.UUID
    section_id: uuid.UUID
    rollNumber: str | None = None
    roll_number: str | None = None

    # Demographics & Contact
    gender: str | None = None
    dob: date | str | None = None
    studentCountryCode: str | None = "+91"
    student_country_code: str | None = None
    phoneNumber: str | None = None
    phone_number: str | None = None

    # Guardian info
    guardianFirstName: str | None = None
    guardianLastName: str | None = None
    guardian_first_name: str | None = None
    guardian_last_name: str | None = None
    countryCode: str | None = "+91"
    guardian_country_code: str | None = None
    guardianPhone: str | None = None
    guardian_phone: str | None = None
    email: str | None = None
    guardian_email: str | None = None

    status: str = "ACTIVE"
    password: str | None = None


class StudentUpdateRequest(PasswordCheckMixin):
    firstName: str | None = None
    lastName: str | None = None
    first_name: str | None = None
    last_name: str | None = None

    academicYear: str | None = None
    academic_year: str | None = None
    school_id: uuid.UUID | None = None
    class_id: uuid.UUID | None = None
    section_id: uuid.UUID | None = None
    rollNumber: str | None = None
    roll_number: str | None = None

    gender: str | None = None
    dob: date | str | None = None
    studentCountryCode: str | None = None
    student_country_code: str | None = None
    phoneNumber: str | None = None
    phone_number: str | None = None

    guardianFirstName: str | None = None
    guardianLastName: str | None = None
    guardian_first_name: str | None = None
    guardian_last_name: str | None = None
    countryCode: str | None = None
    guardian_country_code: str | None = None
    guardianPhone: str | None = None
    guardian_phone: str | None = None
    email: str | None = None
    guardian_email: str | None = None

    status: str | None = None
    password: str | None = None


# ==============================================================================
# Role Permissions (/api/v1/role-permissions/{role_id})
# ==============================================================================

class RolePermissionUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    permission_codes: list[str] = Field(default_factory=list)
    permissions: list[str] | None = None
