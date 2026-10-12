import sys
from contextlib import asynccontextmanager
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.academics import router as academics_router
from app.api.v1.auth import router as auth_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.locations import router as locations_router
from app.api.v1.schools import router as schools_router
from app.api.v1.users import router as users_router
from app.core.config import settings
from app.core.database import async_engine, ensure_db_schema
from app.core.redis import close_redis_client, get_redis_client
from app.core.response import register_exception_handlers


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[Startup] Verifying database schema...")
    await ensure_db_schema()

    print("[Startup] Verifying Redis connection...")
    redis_client = get_redis_client()
    await redis_client.ping()

    if settings.SMTP_DEV_MODE:
        print(
            "[Startup] SMTP_DEV_MODE is ON — OTP/reset emails will be "
            "printed to the console instead of actually sent. Set a real "
            "SMTP_PASSWORD and SMTP_DEV_MODE=false in .env once a Gmail "
            "App Password is available."
        )

    yield

    print("[Shutdown] Closing database connection pool...")
    await async_engine.dispose()

    print("[Shutdown] Closing Redis connection...")
    await close_redis_client()


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten to the real frontend origin before production use
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

app.include_router(auth_router, prefix=settings.API_V1_STR)
app.include_router(locations_router, prefix=settings.API_V1_STR)
app.include_router(academics_router, prefix=settings.API_V1_STR)
app.include_router(schools_router, prefix=settings.API_V1_STR)
app.include_router(users_router, prefix=settings.API_V1_STR)
app.include_router(dashboard_router, prefix=settings.API_V1_STR)



@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": settings.PROJECT_NAME}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
