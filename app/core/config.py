from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Auth Backend"
    API_V1_STR: str = "/api/v1"

    # --- Postgres ---
    POSTGRES_SERVER: str
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str

    @property
    def ASYNC_DATABASE_URL(self) -> str:
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # --- Redis ---
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379

    # --- JWT ---
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24h
    JWT_RESET_TOKEN_EXPIRE_MINUTES: int = 15

    # --- OTP ---
    OTP_LENGTH: int = 6
    OTP_EXPIRE_SECONDS: int = 300  # 5 min
    OTP_RESEND_COOLDOWN_SECONDS: int = 30
    OTP_MAX_ATTEMPTS: int = 5  # max wrong-OTP guesses before the code is invalidated

    # --- Gmail SMTP ---
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = ""
    SMTP_FROM_NAME: str = "Auth Backend"
    # When no real Gmail App Password has been provided yet, fall back to
    # printing the OTP/email contents to the console/log instead of actually
    # sending — lets the whole login/OTP/reset flow be exercised end-to-end
    # before real SMTP credentials exist. See app/services/mailer_service.py.
    SMTP_DEV_MODE: bool = True

    # --- Initial Super Admin Bootstrap (seeded on startup if missing) ---
    SUPER_ADMIN_EMAIL: str = "humza.ahmad050504@gmail.com"
    SUPER_ADMIN_PASSWORD: str = "Test@1234"
    SUPER_ADMIN_FIRST_NAME: str = "Super"
    SUPER_ADMIN_LAST_NAME: str = "Admin"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
