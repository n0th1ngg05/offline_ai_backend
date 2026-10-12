from collections.abc import AsyncGenerator
from pathlib import Path

import asyncpg
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

async_engine = create_async_engine(
    settings.ASYNC_DATABASE_URL,
    echo=False,
    future=True,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def ensure_db_schema() -> None:
    """Ensures the `offlineai` schema, tables, seed data, and configured
    Super Admin account (from .env) exist on startup."""
    import asyncio
    from app.core.security import hash_password

    init_sql_path = Path(__file__).resolve().parent.parent.parent / "sql" / "init.sql"
    conn = None
    last_err = None
    for attempt in range(1, 11):
        try:
            conn = await asyncpg.connect(
                user=settings.POSTGRES_USER,
                password=settings.POSTGRES_PASSWORD,
                host=settings.POSTGRES_SERVER,
                port=settings.POSTGRES_PORT,
                database=settings.POSTGRES_DB,
            )
            break
        except Exception as exc:
            last_err = exc
            print(f"[Startup] Waiting for PostgreSQL ({attempt}/10): {exc}")
            await asyncio.sleep(1.5)

    if conn is None:
        raise RuntimeError(f"Could not connect to PostgreSQL after 10 attempts: {last_err}")

    try:
        if init_sql_path.exists():
            exists = await conn.fetchval(
                "SELECT EXISTS ("
                "  SELECT 1 FROM information_schema.tables "
                "  WHERE table_schema = 'offlineai' AND table_name = 'role_permissions'"
                ")"
            )
            if not exists:
                print("[Startup] Initializing database schema and seed data from sql/init.sql...")
                sql_text = init_sql_path.read_text(encoding="utf-8")
                await conn.execute(sql_text)
                print("[Startup] Database schema initialized successfully.")

        # Ensure the Super Admin configured in .env exists in offlineai.users
        admin_email = (settings.SUPER_ADMIN_EMAIL or "").strip().lower()
        admin_password = settings.SUPER_ADMIN_PASSWORD or ""
        if admin_email and admin_password:
            existing_admin = await conn.fetchval(
                "SELECT id FROM offlineai.users WHERE LOWER(email) = $1",
                admin_email,
            )
            if not existing_admin:
                hashed = hash_password(admin_password)
                await conn.execute(
                    """
                    INSERT INTO offlineai.users
                        (email, hashed_password, first_name, last_name, user_type, status, is_first_login)
                    VALUES ($1, $2, $3, $4, 'super_admin', 'ACTIVE', FALSE)
                    ON CONFLICT (email) DO NOTHING
                    """,
                    admin_email,
                    hashed,
                    (settings.SUPER_ADMIN_FIRST_NAME or "Super").strip(),
                    (settings.SUPER_ADMIN_LAST_NAME or "Admin").strip(),
                )
                print(f"[Startup] Seeded initial Super Admin from .env: {admin_email}")
    finally:
        await conn.close()

