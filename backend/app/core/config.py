from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    # Application
    PROJECT_NAME: str = "Invonics Technologies Storefront"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://invonics:invonics_dev_pass@localhost:5433/invonics_dev"

    # JWT
    SECRET_KEY: str = "changeme"
    ALGORITHM: str = "HS256"
    # ponytail: one 12h session cookie, no refresh tokens; add refresh + revocation if sessions must be killable
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 720
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    COOKIE_SECURE: bool = True  # set false only for plain-http local dev

    # File storage (originals + per-buyer watermarked copies)
    STORAGE_DIR: str = str(BACKEND_DIR / "storage")
    MAX_UPLOAD_MB: int = 200

    # MinIO / Object Storage
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "invonics_minio"
    MINIO_SECRET_KEY: str = "invonics_minio_pass"
    MINIO_BUCKET_NAME: str = "invonics-resources"
    MINIO_SECURE: bool = False

    # Brevo (Email)
    BREVO_API_KEY: str = ""
    BREVO_SENDER_EMAIL: str = "noreply@invonics.com"
    BREVO_SENDER_NAME: str = "Invonics Technologies"

    # M-Pesa Daraja
    DARAJA_ENV: str = "mock"  # "mock" | "sandbox" | "production"
    DARAJA_CONSUMER_KEY: str = ""
    DARAJA_CONSUMER_SECRET: str = ""
    DARAJA_SHORTCODE: str = ""
    DARAJA_PASSKEY: str = ""
    DARAJA_CALLBACK_URL: str = ""  # public base URL (e.g. ngrok); path is appended
    DARAJA_CALLBACK_SECRET: str = ""  # unguessable path segment so forged callbacks 404

    # Security
    REBIND_LIMIT_PER_MONTH: int = 3
    WATERMARK_TTL_HOURS: int = 4
    OTP_EXPIRE_MINUTES: int = 10

    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")


settings = Settings()
