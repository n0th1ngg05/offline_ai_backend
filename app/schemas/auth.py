"""
Pydantic request models matching the frontend's exact field names, traced
directly from src/services/api/auth.api.js and auth.action.js. Response
shapes are NOT modeled as Pydantic here — app/core/response.py's
success_response() builds the envelope directly from plain dicts returned
by auth_service.py, since the frontend's expected response shape is a
loose, evolving envelope rather than a strict contract worth over-typing.
"""

import re
import uuid
from pydantic import BaseModel, EmailStr, Field, field_validator

MAX_BCRYPT_PASSWORD_BYTES = 72


def _validate_bcrypt_byte_length(password: str) -> str:
    if len(password.encode("utf-8")) > MAX_BCRYPT_PASSWORD_BYTES:
        raise ValueError("Password cannot exceed 72 bytes.")
    return password


def _validate_strong_password(password: str) -> str:
    _validate_bcrypt_byte_length(password)
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters long.")
    if not re.search(r"[A-Z]", password):
        raise ValueError("Password must contain at least one uppercase letter.")
    if not re.search(r"[a-z]", password):
        raise ValueError("Password must contain at least one lowercase letter.")
    if not re.search(r"\d", password):
        raise ValueError("Password must contain at least one number.")
    if not re.search(r"[^A-Za-z0-9]", password):
        raise ValueError("Password must contain at least one special character.")
    return password


class LoginRequest(BaseModel):
    identifier: EmailStr
    password: str = Field(min_length=1, max_length=MAX_BCRYPT_PASSWORD_BYTES)
    remember_me: bool = True

    @field_validator("password")
    @classmethod
    def validate_password_bytes(cls, value: str) -> str:
        return _validate_bcrypt_byte_length(value)


class VerifyOtpRequest(BaseModel):
    """Matches what OtpVerification.jsx actually sends: the full login
    context (identifier, password, remember_me) spread with otp. password
    and remember_me are accepted but unused by auth_service.verify_login_otp
    (password was already checked in the login() step) — kept here only so
    FastAPI doesn't reject the request for extra fields."""

    identifier: EmailStr
    otp: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")
    password: str | None = None
    remember_me: bool | None = None


class ResendOtpRequest(BaseModel):
    """Matches OtpVerification.jsx's getResendPayload() — all fields
    optional since it filters out empty/undefined ones before sending.
    Only `email` is populated for the Super Admin login flow (no phone/
    role/flow in that context)."""

    email: EmailStr | None = None
    phone: str | None = None
    role: str | None = None
    flow: str | None = None


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class VerifyForgotPasswordRequest(BaseModel):
    email: EmailStr
    otp: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class ResetPasswordRequest(BaseModel):
    reset_token: str = Field(min_length=1)
    new_password: str = Field(min_length=8, max_length=MAX_BCRYPT_PASSWORD_BYTES)

    @field_validator("new_password")
    @classmethod
    def validate_new_password_strength(cls, value: str) -> str:
        return _validate_strong_password(value)


class ChangePasswordRequest(BaseModel):
    current_password: str | None = None
    old_password: str | None = None
    new_password: str = Field(min_length=8, max_length=MAX_BCRYPT_PASSWORD_BYTES)

    @field_validator("new_password")
    @classmethod
    def validate_new_password_strength(cls, value: str) -> str:
        return _validate_strong_password(value)


class StudentRequestOtpRequest(BaseModel):
    country_code: str = "+91"
    phone: str = Field(min_length=7, max_length=15, pattern=r"^\d{7,15}$")


class StudentVerifyOtpRequest(BaseModel):
    country_code: str = "+91"
    phone: str = Field(min_length=7, max_length=15, pattern=r"^\d{7,15}$")
    otp: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class StudentSelectRequest(BaseModel):
    guardian_token: str = Field(min_length=1)
    student_id: uuid.UUID


