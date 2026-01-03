"""Configuration settings for the backend."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    database_url: str = "postgresql+asyncpg://images2slides:dev_password@localhost:5432/images2slides"

    # App URLs
    app_base_url: str = "http://localhost:3000"

    # Security
    tokens_encryption_key: str = "dev_encryption_key_32_chars_ok!!"

    # Google OAuth
    google_client_id: str = ""
    google_client_secret: str = ""

    # VLM Configuration
    vlm_provider: Literal["google", "openai", "anthropic", "openrouter"] = "google"
    vlm_model: str | None = None
    google_api_key: str = ""
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    openrouter_api_key: str = ""

    # Storage
    storage_type: Literal["local", "s3", "gcs"] = "local"
    local_storage_path: str = "/data/uploads"
    s3_bucket: str = ""
    s3_region: str = "us-east-1"
    gcs_bucket: str = ""

    # Job processing
    max_job_retries: int = 3
    job_poll_interval_seconds: float = 2.0

    # Limits
    max_images_per_project: int = 50
    max_image_size_bytes: int = 20 * 1024 * 1024  # 20MB

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()