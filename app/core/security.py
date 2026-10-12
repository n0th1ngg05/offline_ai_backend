"""
Password hashing and JWT encode/decode helpers ONLY. No FastAPI
dependencies, no DB queries, no endpoint logic — those live in
app/services/auth_service.py (business logic) and app/api/v1/auth.py
(HTTP wiring). This file is pure, testable crypto/token utility functions.
"""

import uuid
from datetime import datetime, timedelta, timezone
from enum import Enum

import bcrypt
import jwt

from app.core.config import settings

BCRYPT_ROUNDS = 12
MAX_BCRYPT_PASSWORD_BYTES = 72


def hash_password(plain_password: str) -> str:
    password_bytes = plain_password.encode("utf-8")
    if len(password_bytes) > MAX_BCRYPT_PASSWORD_BYTES:
        raise ValueError("Password cannot exceed 72 bytes.")
    salt = bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    password_bytes = plain_password.encode("utf-8")
    if len(password_bytes) > MAX_BCRYPT_PASSWORD_BYTES:
        return False
    try:
        return bcrypt.checkpw(password_bytes, hashed_password.encode("utf-8"))
    except ValueError:
        return False


# A dummy hash used by auth_service.py to run a bcrypt comparison even when
# no user was found for a given email, so response timing doesn't reveal
# whether an account exists (same approach used elsewhere in this project's
# earlier Node build). This is a real bcrypt hash of an arbitrary string,
# never the hash of any real account's password.
DUMMY_PASSWORD_HASH = bcrypt.hashpw(b"not_a_real_password", bcrypt.gensalt(rounds=BCRYPT_ROUNDS)).decode(
    "utf-8"
)


class TokenPurpose(str, Enum):
    ACCESS = "access"
    PASSWORD_RESET = "password_reset"
    GUARDIAN_SELECT = "guardian_select"


def create_access_token(*, user_id: uuid.UUID, user_type: str) -> str:
    """Normal login JWT — issued after successful OTP verification.
    Carries `sub` (user id) and `user_type`, used by get_current_user to
    resolve the user and by the frontend's role-based routing."""
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "user_type": user_type,
        "purpose": TokenPurpose.ACCESS.value,
        "iat": now,
        "exp": expire,
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_password_reset_token(*, user_id: uuid.UUID) -> tuple[str, str]:
    """Short-lived, single-purpose token for the forgot-password flow.
    Returns (token, jti) — jti (JWT ID) is used by auth_service.py to mark
    the token as used in Redis after a successful reset, making it
    single-use even though JWTs are normally stateless."""
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.JWT_RESET_TOKEN_EXPIRE_MINUTES)
    jti = str(uuid.uuid4())
    payload = {
        "sub": str(user_id),
        "purpose": TokenPurpose.PASSWORD_RESET.value,
        "jti": jti,
        "iat": now,
        "exp": expire,
    }
    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token, jti


def create_guardian_token(*, country_code: str, phone: str) -> str:
    """Short-lived token issued after a guardian verifies their phone OTP on
    the Student Login page, allowing them to select one of their associated
    children via POST /api/v1/auth/student/select."""
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=15)
    payload = {
        "sub": f"{country_code}:{phone}",
        "country_code": country_code,
        "phone": phone,
        "purpose": TokenPurpose.GUARDIAN_SELECT.value,
        "iat": now,
        "exp": expire,
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


class TokenError(Exception):
    """Raised by decode_token() on any invalid/expired/wrong-purpose token.
    Caught at the service or router layer to produce a proper 401 response
    in the project's {success, message, errors} envelope shape."""

    pass


def decode_token(token: str, *, expected_purpose: TokenPurpose) -> dict:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise TokenError("Token has expired") from exc
    except jwt.PyJWTError as exc:
        raise TokenError("Invalid token") from exc

    if payload.get("purpose") != expected_purpose.value:
        raise TokenError("Token is not valid for this operation")

    return payload
