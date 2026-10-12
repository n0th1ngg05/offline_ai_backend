"""
OTP generation, Redis storage/TTL, verification, and resend rate-limiting.
Nothing in this file knows about email or HTTP — it only deals with
generating codes and tracking them in Redis under purpose-scoped keys, so a
leaked/guessed OTP from one flow (e.g. login) can't be replayed in another
(e.g. forgot-password). app/services/auth_service.py calls into this and
into mailer_service.py separately and ties them together.
"""

import secrets
from enum import Enum

from app.core.config import settings
from app.core.redis import get_redis_client


class OtpPurpose(str, Enum):
    LOGIN = "login"
    FORGOT_PASSWORD = "forgot_password"
    STUDENT_LOGIN = "student_login"


def _otp_key(purpose: OtpPurpose, email: str) -> str:
    return f"otp:{purpose.value}:{email.lower()}"


def _attempts_key(purpose: OtpPurpose, email: str) -> str:
    return f"otp_attempts:{purpose.value}:{email.lower()}"


def _cooldown_key(purpose: OtpPurpose, email: str) -> str:
    return f"otp_cooldown:{purpose.value}:{email.lower()}"


def _login_session_key(email: str) -> str:
    return f"otp_login_session:{email.lower()}"


def generate_otp_code() -> str:
    """Generates a random numeric code of OTP_LENGTH digits, matching the
    frontend's /^\\d{6}$/ validation regex exactly (for the default length
    of 6). Uses `secrets`, not `random`, since this is a security-sensitive
    value."""
    digits = "0123456789"
    return "".join(secrets.choice(digits) for _ in range(settings.OTP_LENGTH))


async def start_login_session(email: str) -> None:
    """Records in Redis that the user's password was verified in Step 1
    (login). Required by both resend_login_otp() and verify_otp(LOGIN) so
    calling /resend-otp directly without first passing password auth cannot
    mint or verify a login OTP (prevents 2FA -> 1FA bypass)."""
    client = get_redis_client()
    await client.set(_login_session_key(email), "1", ex=settings.OTP_EXPIRE_SECONDS)


async def has_login_session(email: str) -> bool:
    client = get_redis_client()
    return bool(await client.exists(_login_session_key(email)))


async def clear_login_session(email: str) -> None:
    client = get_redis_client()
    await client.delete(_login_session_key(email))


async def is_in_cooldown(purpose: OtpPurpose, email: str) -> bool:
    """True if an OTP was issued for this email+purpose too recently to
    allow another send/resend yet (matches the frontend's own 25s resend
    cooldown UI — see OtpVerification.jsx's RESEND_SECONDS)."""
    client = get_redis_client()
    return bool(await client.exists(_cooldown_key(purpose, email)))


async def issue_otp(purpose: OtpPurpose, email: str) -> str:
    """Generates a new OTP, stores it in Redis with TTL, resets the
    wrong-attempt counter, and sets a short cooldown to block immediate
    resend spam. Returns the plaintext code so the caller (auth_service.py)
    can hand it to mailer_service.py to actually send. Overwrites any
    previous pending OTP for this email+purpose."""
    client = get_redis_client()
    code = generate_otp_code()

    await client.set(_otp_key(purpose, email), code, ex=settings.OTP_EXPIRE_SECONDS)
    await client.delete(_attempts_key(purpose, email))
    await client.set(
        _cooldown_key(purpose, email), "1", ex=settings.OTP_RESEND_COOLDOWN_SECONDS
    )

    return code


async def revoke_otp(purpose: OtpPurpose, email: str) -> None:
    """Rolls back the OTP, attempt counter, and resend cooldown in Redis if
    sending the email fails, so a transient SMTP error doesn't leave the
    user locked behind a 30-second 429 cooldown with no email delivered."""
    client = get_redis_client()
    await client.delete(
        _otp_key(purpose, email),
        _attempts_key(purpose, email),
        _cooldown_key(purpose, email),
    )


async def verify_otp(purpose: OtpPurpose, email: str, submitted_code: str) -> bool:
    """Checks the submitted code against what's stored in Redis for this
    email+purpose. Tracks wrong attempts and invalidates the OTP entirely
    after OTP_MAX_ATTEMPTS wrong guesses (prevents brute-forcing a 6-digit
    code within its TTL window). On success, deletes the OTP and cooldown
    so it can't be reused (single-use, same spirit as the password-reset
    token)."""
    if purpose == OtpPurpose.LOGIN and not await has_login_session(email):
        return False

    client = get_redis_client()
    otp_key = _otp_key(purpose, email)
    attempts_key = _attempts_key(purpose, email)
    cooldown_key = _cooldown_key(purpose, email)

    stored_code = await client.get(otp_key)
    if stored_code is None:
        return False  # expired, never issued, or already consumed

    attempts = await client.incr(attempts_key)
    if attempts == 1:
        # First attempt on this key — set the attempts counter to expire
        # alongside the OTP itself, so it doesn't linger in Redis forever.
        await client.expire(attempts_key, settings.OTP_EXPIRE_SECONDS)

    if attempts > settings.OTP_MAX_ATTEMPTS:
        keys_to_delete = [otp_key, attempts_key]
        if purpose == OtpPurpose.LOGIN:
            keys_to_delete.append(_login_session_key(email))
        await client.delete(*keys_to_delete)
        return False

    if secrets.compare_digest(stored_code, submitted_code):
        keys_to_delete = [otp_key, attempts_key, cooldown_key]
        if purpose == OtpPurpose.LOGIN:
            keys_to_delete.append(_login_session_key(email))
        await client.delete(*keys_to_delete)
        return True

    if attempts >= settings.OTP_MAX_ATTEMPTS:
        keys_to_delete = [otp_key, attempts_key]
        if purpose == OtpPurpose.LOGIN:
            keys_to_delete.append(_login_session_key(email))
        await client.delete(*keys_to_delete)

    return False
