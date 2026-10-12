"""
Raw user-table DB queries ONLY. No business logic (that's auth_service.py),
no HTTP/FastAPI objects (that's api/v1/auth.py). Every other file that
needs user data goes through functions here rather than querying User
directly — this is the single place to change if the users table or query
patterns change.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserStatus


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(
        select(User).where(User.email == email.lower(), User.deleted_at.is_(None))
    )
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    result = await db.execute(
        select(User).where(User.id == user_id, User.deleted_at.is_(None))
    )
    return result.scalar_one_or_none()


async def update_user_password(db: AsyncSession, user: User, new_hashed_password: str) -> None:
    user.hashed_password = new_hashed_password
    user.is_first_login = False
    await db.commit()
    await db.refresh(user)


async def mark_login(db: AsyncSession, user: User) -> None:
    from datetime import datetime, timezone

    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(user)


def is_active(user: User) -> bool:
    return user.status == UserStatus.ACTIVE
