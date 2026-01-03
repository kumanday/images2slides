from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://postgres:postgres@db:5432/images2slides"

    app_base_url: str = "http://localhost:3000"
    api_base_url: str = "http://localhost:8000"

    tokens_encryption_key: str

    google_client_id: str
    google_client_secret: str

    data_dir: Path = Path("/data")

    max_upload_bytes: int = 25 * 1024 * 1024
    max_images_per_project: int = 25

    jobs_per_hour: int = 20


@lru_cache
def get_settings() -> Settings:
    return Settings()
