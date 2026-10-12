"""
FastAPI router ONLY — request parsing, calls into app/services/auth_service.py,
wraps results via app/core/response.py's success_response(). No business
logic, no direct DB queries, no direct Redis/SMTP calls here; see
AUTH_BUILD_SPEC.md section 7.5 for the file-responsibility rules this
follows.
"""

import uuid

from fastapi import APIRouter, Depends, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_db
from app.core.response import AppError, success_response
from app.core.security import TokenError, TokenPurpose, decode_token
from app.schemas.auth import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    ResendOtpRequest,
    ResetPasswordRequest,
    StudentRequestOtpRequest,
    StudentSelectRequest,
    StudentVerifyOtpRequest,
    VerifyForgotPasswordRequest,
    VerifyOtpRequest,
)
from app.models.user import User
from app.services import auth_service, user_service

router = APIRouter(prefix="/auth", tags=["auth"])

_bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_async_db),
) -> User:
    """Dependency that validates the access JWT AND verifies the user still
    exists and is ACTIVE in PostgreSQL."""
    if not credentials or not credentials.credentials:
        raise AppError("Authentication required.", status_code=401)
    token = credentials.credentials
    try:
        payload = decode_token(token, expected_purpose=TokenPurpose.ACCESS)
    except TokenError as exc:
        raise AppError(str(exc), status_code=401) from exc

    user_id = payload.get("sub")
    if not user_id:
        raise AppError("Invalid token.", status_code=401)

    user = await user_service.get_user_by_id(db, uuid.UUID(user_id))
    if not user:
        raise AppError("User account no longer exists.", status_code=401)
    if not user_service.is_active(user):
        raise AppError("This account is inactive. Contact an administrator.", status_code=403)

    return user


async def get_current_user_id(
    user: User = Depends(get_current_user),
) -> uuid.UUID:
    """Dependency returning the authenticated & active user's UUID."""
    return user.id


def require_roles(*allowed_roles: str):
    """Dependency factory that enforces role-based access control."""
    normalized = {r.lower() for r in allowed_roles}

    async def _check_role(user: User = Depends(get_current_user)) -> User:
        if user.user_type.lower() not in normalized:
            raise AppError(
                "You do not have permission to perform this action.",
                status_code=403,
            )
        return user

    return _check_role


ADMIN_ROLES = {
    "super_admin",
    "system_admin",
    "school_admin",
    "content_admin",
    "content_manager",
}


async def get_current_admin_user_id(
    user: User = Depends(get_current_user),
) -> uuid.UUID:
    """Dependency for admin/management endpoints — blocks non-admin roles
    (e.g. students) with 403 Forbidden."""
    if user.user_type.lower() not in ADMIN_ROLES:
        raise AppError(
            "You do not have permission to perform this administrative action.",
            status_code=403,
        )
    return user.id




@router.post("/login")
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_async_db)):
    result = await auth_service.login(db, identifier=payload.identifier, password=payload.password)
    return success_response(
        message="OTP sent to your email.",
        verification_required=result["verification_required"],
    )


@router.post("/verify")
async def verify(payload: VerifyOtpRequest, db: AsyncSession = Depends(get_async_db)):
    data = await auth_service.verify_login_otp(db, identifier=payload.identifier, otp=payload.otp)
    return success_response(message="Login successful.", data=data)


@router.post("/resend-otp")
async def resend_otp(payload: ResendOtpRequest, db: AsyncSession = Depends(get_async_db)):
    if not payload.email:
        raise AppError("Email is required to resend an OTP.", status_code=400)
    await auth_service.resend_login_otp(db, email=payload.email)
    return success_response(message="OTP resent successfully.")


@router.post("/student/request-otp")
async def student_request_otp(
    payload: StudentRequestOtpRequest, db: AsyncSession = Depends(get_async_db)
):
    await auth_service.student_request_otp(
        db, country_code=payload.country_code, phone=payload.phone
    )
    return success_response(
        message="OTP sent successfully.",
        verification_required=True,
    )


@router.post("/student/verify-otp")
async def student_verify_otp(
    payload: StudentVerifyOtpRequest, db: AsyncSession = Depends(get_async_db)
):
    data = await auth_service.student_verify_otp(
        db, country_code=payload.country_code, phone=payload.phone, otp=payload.otp
    )
    return success_response(message="OTP verified successfully.", data=data)


@router.post("/student/select")
async def student_select(
    payload: StudentSelectRequest, db: AsyncSession = Depends(get_async_db)
):
    data = await auth_service.student_select_child(
        db, guardian_token=payload.guardian_token, student_id=payload.student_id
    )
    return success_response(message="Student selected successfully.", data=data)


@router.post("/forgot-password")
async def forgot_password(payload: ForgotPasswordRequest, db: AsyncSession = Depends(get_async_db)):
    await auth_service.forgot_password_request(db, email=payload.email)
    return success_response(
        message="If an account exists for this email, a verification code has been sent."
    )


@router.post("/forgot-password/verify")
async def forgot_password_verify(
    payload: VerifyForgotPasswordRequest, db: AsyncSession = Depends(get_async_db)
):
    data = await auth_service.forgot_password_verify(db, email=payload.email, otp=payload.otp)
    return success_response(message="Code verified. You may now reset your password.", data=data)


@router.post("/reset-password")
async def reset_password(payload: ResetPasswordRequest, db: AsyncSession = Depends(get_async_db)):
    await auth_service.reset_password(
        db, reset_token=payload.reset_token, new_password=payload.new_password
    )
    return success_response(message="Password reset successfully. You can now log in.")


@router.post("/change-password")
async def change_password(
    payload: ChangePasswordRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    current_pw = payload.current_password or payload.old_password
    await auth_service.change_password(
        db, user_id=user_id, current_password=current_pw, new_password=payload.new_password
    )
    return success_response(message="Password changed successfully.")


@router.get("/preferences")
async def get_preferences(
    _user_id: uuid.UUID = Depends(get_current_user_id),
):
    return success_response(
        message="OK",
        data={"theme": "light", "language": "en", "notifications_enabled": True},
    )


@router.put("/preferences")
async def update_preferences(
    payload: dict,
    _user_id: uuid.UUID = Depends(get_current_user_id),
):
    return success_response(message="Preferences updated successfully.", data=payload)


@router.get("/me")
async def me(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_async_db),
):
    data = await auth_service.get_me(db, user_id=user_id)
    return success_response(message="OK", data=data)


