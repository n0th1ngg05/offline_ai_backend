"""
Login/verify/forgot-password/reset-password BUSINESS LOGIC. Orchestrates
user_service (DB), otp_service (Redis OTP), mailer_service (SMTP), and
core.security (hashing/JWT) — contains no FastAPI Request/Response objects
and no direct DB/Redis queries of its own. Plain Python functions taking a
DB session + typed args, raising AppError on any expected failure, and
returning plain dicts/values for the router (app/api/v1/auth.py) to wrap in
the response envelope.
"""

import asyncio
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import get_redis_client
from app.core.response import AppError
from app.core.security import (
    TokenError,
    TokenPurpose,
    create_access_token,
    create_password_reset_token,
    decode_token,
    hash_password,
    verify_password,
    DUMMY_PASSWORD_HASH,
)
from app.models.user import User
from app.services import user_service
from app.services.mailer_service import send_email
from app.services.otp_service import (
    OtpPurpose,
    clear_login_session,
    has_login_session,
    is_in_cooldown,
    issue_otp,
    revoke_otp,
    start_login_session,
    verify_otp,
)

_background_tasks: set[asyncio.Task] = set()


def _otp_email_body(code: str, *, purpose_label: str) -> str:
    return (
        f"Your one-time verification code is: {code}\n\n"
        f"This code is for {purpose_label} and expires in a few minutes.\n"
        f"If you did not request this, you can safely ignore this email."
    )


async def _send_otp_email_in_background(
    *, purpose: OtpPurpose, to: str, subject: str, body: str
) -> None:
    """Sends an OTP email off the request path (used by forgot-password so
    response latency doesn't reveal whether the email exists) and rolls back
    the Redis OTP + cooldown keys if SMTP delivery fails."""
    try:
        await send_email(to=to, subject=subject, body=body)
    except Exception as exc:
        print(f"[SMTP ERROR] Failed to send {purpose.value} OTP to {to}: {exc!r}")
        await revoke_otp(purpose, to)


from sqlalchemy import func, select
from app.models.assignments import RolePermission, UserSchool
from app.models.school import School


async def _build_user_public_data(
    db: AsyncSession, user: User, *, access_token: str | None = None
) -> dict:
    """Shapes a User row into the `data` object the frontend expects back
    from login/verify/me responses — see auth.reducer.js's getPayloadUser(),
    including assigned schools and role permissions."""
    us_rows = (
        await db.execute(
            select(UserSchool, School)
            .join(School, School.id == UserSchool.school_id)
            .where(
                UserSchool.user_id == user.id,
                UserSchool.is_deleted.is_(False),
                School.is_deleted.is_(False),
            )
            .order_by(School.name.asc())
        )
    ).all()

    schools_list = []
    for us, sch in us_rows:
        sch_obj = {
            "id": str(sch.id),
            "school_id": str(sch.id),
            "relation_id": str(us.id),
            "name": sch.name,
            "code": sch.udise_code,
            "udise_code": sch.udise_code,
            "status": sch.status,
        }
        schools_list.append({**sch_obj, "school": sch_obj})

    primary_school = schools_list[0]["school"] if schools_list else None

    rp = (
        await db.execute(
            select(RolePermission).where(
                func.lower(RolePermission.role_name) == user.user_type.lower()
            )
        )
    ).scalar_one_or_none()
    perms = list(rp.permission_codes or []) if rp else []

    data = {
        "id": str(user.id),
        "first_name": user.first_name,
        "last_name": user.last_name,
        "full_name": user.full_name,
        "email": user.email,
        "country_code": user.country_code or "+91",
        "phone_number": user.phone_number or user.phone,
        "phone": user.phone or user.phone_number,
        "gender": user.gender,
        "user_type": user.user_type,
        "role": user.user_type,
        "status": user.status,
        "is_first_login": user.is_first_login,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "profile_picture_url": user.profile_picture_url,
        "schools": schools_list,
        "school": primary_school,
        "assigned_schools": [s["school"] for s in schools_list],
        "school_assignments": schools_list,
        "permissions": perms,
    }
    if access_token:
        data["access_token"] = access_token
    return data



async def login(db: AsyncSession, *, identifier: str, password: str) -> dict:
    """Step 1 of login: validate email+password. On success, issues an OTP
    and emails it — does NOT issue a JWT yet (OTP verification, via
    verify_login_otp() below, is what issues the token). Always runs a
    password comparison even for an unknown email, to avoid leaking account
    existence via response timing."""
    email = identifier.strip().lower()
    user = await user_service.get_user_by_email(db, email)

    hash_to_check = user.hashed_password if user else DUMMY_PASSWORD_HASH
    password_valid = verify_password(password, hash_to_check)

    if not user or not password_valid:
        raise AppError("Invalid email or password.", status_code=401)

    if not user_service.is_active(user):
        raise AppError("This account is inactive. Contact an administrator.", status_code=403)

    if await is_in_cooldown(OtpPurpose.LOGIN, email):
        raise AppError(
            "An OTP was already sent recently. Please wait before requesting another.",
            status_code=429,
        )

    await start_login_session(email)
    code = await issue_otp(OtpPurpose.LOGIN, email)
    try:
        await send_email(
            to=email,
            subject="Your login verification code",
            body=_otp_email_body(code, purpose_label="logging in"),
        )
    except Exception as exc:
        await revoke_otp(OtpPurpose.LOGIN, email)
        await clear_login_session(email)
        raise AppError(
            "Failed to send verification email. Please try again shortly.",
            status_code=503,
        ) from exc

    return {"verification_required": True}


async def resend_login_otp(db: AsyncSession, *, email: str) -> None:
    email = email.strip().lower()

    # Require proof that Step 1 (password verification in login()) already
    # succeeded for this email. Without an active login session, silently
    # no-op so an unauthenticated caller can neither bypass the password
    # factor by minting a LOGIN OTP nor enumerate accounts via 429/timing.
    if not await has_login_session(email):
        return

    user = await user_service.get_user_by_email(db, email)
    if not user or not user_service.is_active(user):
        await clear_login_session(email)
        return

    if await is_in_cooldown(OtpPurpose.LOGIN, email):
        raise AppError(
            "Please wait before requesting another OTP.", status_code=429
        )

    await start_login_session(email)
    code = await issue_otp(OtpPurpose.LOGIN, email)
    try:
        await send_email(
            to=email,
            subject="Your login verification code",
            body=_otp_email_body(code, purpose_label="logging in"),
        )
    except Exception as exc:
        await revoke_otp(OtpPurpose.LOGIN, email)
        raise AppError(
            "Failed to send verification email. Please try again shortly.",
            status_code=503,
        ) from exc


async def verify_login_otp(db: AsyncSession, *, identifier: str, otp: str) -> dict:
    """Step 2 of login: verify the OTP sent in login(). On success, issues
    the real access JWT and returns the user's public data for the
    frontend's Redux store. Does NOT re-check the password here — password
    was already validated in login() before the OTP was even sent (and
    enforced via the Redis login session in verify_otp)."""
    email = identifier.strip().lower()
    user = await user_service.get_user_by_email(db, email)
    if not user:
        raise AppError("Invalid or expired OTP.", status_code=401)

    otp_valid = await verify_otp(OtpPurpose.LOGIN, email, otp)
    if not otp_valid:
        raise AppError("Invalid or expired OTP.", status_code=401)

    if not user_service.is_active(user):
        raise AppError("This account is inactive. Contact an administrator.", status_code=403)

    await user_service.mark_login(db, user)

    access_token = create_access_token(user_id=user.id, user_type=user.user_type)
    return await _build_user_public_data(db, user, access_token=access_token)



async def forgot_password_request(db: AsyncSession, *, email: str) -> None:
    """Sends an OTP to the given email IF it corresponds to a real,
    active account — but always returns success regardless, so the
    response itself never reveals whether the email exists (the frontend
    doesn't branch on response content here anyway, see
    ForgotPasswordPage.jsx's handleRequestCode, it just advances to the
    next step unconditionally on HTTP success)."""
    email = email.strip().lower()
    user = await user_service.get_user_by_email(db, email)

    if not user or not user_service.is_active(user):
        return  # silently no-op — do not leak existence

    if await is_in_cooldown(OtpPurpose.FORGOT_PASSWORD, email):
        # Still don't leak existence via a different error — just no-op
        # again rather than raising, since raising here WOULD leak
        # "this email exists and already has a pending OTP."
        return

    code = await issue_otp(OtpPurpose.FORGOT_PASSWORD, email)
    task = asyncio.create_task(
        _send_otp_email_in_background(
            purpose=OtpPurpose.FORGOT_PASSWORD,
            to=email,
            subject="Your password reset code",
            body=_otp_email_body(code, purpose_label="resetting your password"),
        )
    )
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


async def forgot_password_verify(db: AsyncSession, *, email: str, otp: str) -> dict:
    """Verifies the forgot-password OTP and, on success, issues a
    short-lived, single-purpose reset token (NOT a login JWT) that
    reset_password() below requires."""
    email = email.strip().lower()
    user = await user_service.get_user_by_email(db, email)
    if not user:
        raise AppError("Invalid or expired code.", status_code=401)

    otp_valid = await verify_otp(OtpPurpose.FORGOT_PASSWORD, email, otp)
    if not otp_valid:
        raise AppError("Invalid or expired code.", status_code=401)

    reset_token, _jti = create_password_reset_token(user_id=user.id)
    return {"reset_token": reset_token}


async def reset_password(db: AsyncSession, *, reset_token: str, new_password: str) -> None:
    """Validates the reset token (signature, expiry, purpose, and
    single-use via a Redis marker keyed by the token's jti), then updates
    the user's password."""
    try:
        payload = decode_token(reset_token, expected_purpose=TokenPurpose.PASSWORD_RESET)
    except TokenError as exc:
        raise AppError(str(exc), status_code=401) from exc

    jti = payload.get("jti")
    user_id = payload.get("sub")
    if not jti or not user_id:
        raise AppError("Invalid reset token.", status_code=401)

    client = get_redis_client()
    used_key = f"used_reset_token:{jti}"
    already_used = await client.exists(used_key)
    if already_used:
        raise AppError("This reset link has already been used.", status_code=401)

    user = await user_service.get_user_by_id(db, uuid.UUID(user_id))
    if not user or not user_service.is_active(user):
        raise AppError("Invalid reset token.", status_code=401)

    if verify_password(new_password, user.hashed_password):
        raise AppError(
            "New password cannot be the same as your current password.",
            status_code=400,
        )

    new_hashed = hash_password(new_password)
    await user_service.update_user_password(db, user, new_hashed)

    # Mark the token's jti as used, TTL matching the token's own remaining
    # lifetime so this Redis key doesn't outlive the token it's protecting
    # against reuse of (no point keeping it after the token would've
    # expired naturally anyway).
    from app.core.config import settings

    await client.set(used_key, "1", ex=settings.JWT_RESET_TOKEN_EXPIRE_MINUTES * 60)


async def get_me(db: AsyncSession, *, user_id: uuid.UUID) -> dict:
    user = await user_service.get_user_by_id(db, user_id)
    if not user:
        raise AppError("User not found.", status_code=404)
    return await _build_user_public_data(db, user)


async def change_password(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    current_password: str | None,
    new_password: str,
) -> None:
    user = await user_service.get_user_by_id(db, user_id)
    if not user or not user_service.is_active(user):
        raise AppError("User not found.", status_code=404)

    if current_password and not verify_password(current_password, user.hashed_password):
        raise AppError("Current password is incorrect.", status_code=400)

    if verify_password(new_password, user.hashed_password):
        raise AppError(
            "New password cannot be the same as your current password.",
            status_code=400,
        )

    new_hashed = hash_password(new_password)
    await user_service.update_user_password(db, user, new_hashed)


def _normalize_guardian_phone(country_code: str, phone: str) -> tuple[str, str, str]:
    cc = (country_code or "+91").strip()
    if not cc.startswith("+"):
        cc = f"+{cc}"
    digits = "".join(ch for ch in (phone or "").strip() if ch.isdigit())
    return cc, digits, f"{cc}{digits}"


async def _find_students_by_guardian_phone(
    db: AsyncSession, *, country_code: str, phone: str
) -> list[tuple[User, object]]:
    from sqlalchemy import or_
    from app.models.assignments import StudentProfile

    cc, digits, combined = _normalize_guardian_phone(country_code, phone)
    cc_bare = cc.lstrip("+")

    rows = (
        await db.execute(
            select(User, StudentProfile)
            .join(StudentProfile, StudentProfile.user_id == User.id)
            .where(
                User.is_deleted.is_(False),
                StudentProfile.is_deleted.is_(False),
                or_(
                    StudentProfile.guardian_phone == digits,
                    StudentProfile.guardian_phone == combined,
                    User.phone_number == digits,
                    User.phone == digits,
                    User.phone == combined,
                ),
            )
            .order_by(User.first_name.asc())
        )
    ).all()

    matched: list[tuple[User, StudentProfile]] = []
    for u, sp in rows:
        sp_cc = (sp.guardian_country_code or u.country_code or "+91").strip().lstrip("+")
        if sp_cc == cc_bare or sp.guardian_phone == combined or u.phone == combined:
            matched.append((u, sp))

    return matched or list(rows)


async def student_request_otp(db: AsyncSession, *, country_code: str, phone: str) -> None:
    cc, digits, key = _normalize_guardian_phone(country_code, phone)
    matches = await _find_students_by_guardian_phone(db, country_code=cc, phone=digits)
    if not matches:
        raise AppError(
            "No active student account found for this guardian phone number.",
            status_code=404,
        )

    active_matches = [(u, sp) for u, sp in matches if user_service.is_active(u)]
    if not active_matches:
        raise AppError(
            "The student account associated with this number is inactive.",
            status_code=403,
        )

    if await is_in_cooldown(OtpPurpose.STUDENT_LOGIN, key):
        raise AppError(
            "An OTP was already sent recently. Please wait before requesting another.",
            status_code=429,
        )

    code = await issue_otp(OtpPurpose.STUDENT_LOGIN, key)
    print(f"[STUDENT OTP] Guardian {key} -> OTP: {code}")

    # Send OTP to guardian email if available
    guardian_emails = {
        (sp.guardian_email or u.email or "").strip().lower()
        for u, sp in active_matches
        if (sp.guardian_email or u.email)
    }
    real_emails = [
        e for e in guardian_emails if e and not e.endswith("@offline.local")
    ]
    for target_email in real_emails:
        task = asyncio.create_task(
            _send_otp_email_in_background(
                purpose=OtpPurpose.STUDENT_LOGIN,
                to=target_email,
                subject="Your Student Login verification code",
                body=_otp_email_body(code, purpose_label=f"student login ({key})"),
            )
        )
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)


async def student_verify_otp(
    db: AsyncSession, *, country_code: str, phone: str, otp: str
) -> dict:
    from app.core.security import create_guardian_token
    from app.services.student_service import _serialize_students

    cc, digits, key = _normalize_guardian_phone(country_code, phone)
    otp_valid = await verify_otp(OtpPurpose.STUDENT_LOGIN, key, otp)
    if not otp_valid:
        raise AppError("Invalid or expired OTP.", status_code=401)

    matches = await _find_students_by_guardian_phone(db, country_code=cc, phone=digits)
    active_users = [u for u, _sp in matches if user_service.is_active(u)]
    if not active_users:
        raise AppError("No active student account found.", status_code=404)

    serialized = await _serialize_students(db, active_users)
    guardian_token = create_guardian_token(country_code=cc, phone=digits)
    return {
        "guardian_token": guardian_token,
        "students": serialized,
    }


async def student_select_child(
    db: AsyncSession, *, guardian_token: str, student_id: uuid.UUID
) -> dict:
    from app.services.student_service import _serialize_students

    try:
        payload = decode_token(guardian_token, expected_purpose=TokenPurpose.GUARDIAN_SELECT)
    except TokenError as exc:
        raise AppError(str(exc), status_code=401) from exc

    cc = payload.get("country_code") or "+91"
    digits = payload.get("phone") or ""
    matches = await _find_students_by_guardian_phone(db, country_code=cc, phone=digits)
    target_user = next((u for u, _sp in matches if u.id == student_id), None)
    if not target_user or not user_service.is_active(target_user):
        raise AppError("Selected student is not associated with this guardian.", status_code=403)

    await user_service.mark_login(db, target_user)
    access_token = create_access_token(user_id=target_user.id, user_type=target_user.user_type)
    base_data = await _build_user_public_data(db, target_user, access_token=access_token)
    student_serialized = await _serialize_students(db, [target_user])
    if student_serialized:
        base_data["student"] = student_serialized[0]
        base_data["profile"] = student_serialized[0].get("profile")
        if student_serialized[0].get("school"):
            base_data["school"] = student_serialized[0]["school"]
            base_data["schools"] = [student_serialized[0]["school"]]
    return base_data


