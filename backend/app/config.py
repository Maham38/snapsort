from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    database_url: str = Field(
        default="postgresql+psycopg://snapsort:change-me@localhost:5432/snapsort"
    )
    firebase_credentials_file: str | None = None
    firebase_credentials_json: str | None = None
    firebase_project_id: str | None = None
    allowed_origins: list[str] = ["http://localhost:3000"]
    supabase_url: str | None = None
    supabase_secret_key: str | None = None
    supabase_service_role_key: str | None = None
    supabase_bucket_name: str | None = None
    supabase_signed_url_ttl_seconds: int = 900
    redis_url: str = "redis://localhost:6379/0"
    ai_model_name: str = "buffalo_l"
    ai_model_root: str | None = None
    ai_match_threshold: float = Field(default=0.45, gt=0, lt=1)
    max_upload_size_bytes: int = Field(default=26214400, gt=0)
    stripe_secret_key: str | None = None
    stripe_webhook_secret: str | None = None
    stripe_success_url: str = "https://example.invalid/billing/success"
    stripe_cancel_url: str = "https://example.invalid/billing/cancel"
    stripe_webhook_tolerance_seconds: int = Field(default=300, gt=0)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
