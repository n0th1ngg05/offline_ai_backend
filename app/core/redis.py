import redis.asyncio as redis

from app.core.config import settings

_redis_client: redis.Redis | None = None


def get_redis_client() -> redis.Redis:
    """Returns a lazily-created, process-wide async Redis client. Used by
    otp_service.py for OTP storage/TTL/rate-limiting and by auth_service.py
    for single-use reset-token tracking. Not request-scoped like the DB
    session — a single pooled client is reused across requests, which is
    the normal pattern for redis-py's async client (it manages its own
    connection pool internally)."""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            decode_responses=True,
        )
    return _redis_client


async def close_redis_client() -> None:
    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None
