from __future__ import annotations

from functools import lru_cache

from ..config import get_settings
from .local import LocalStorage


@lru_cache
def get_upload_storage() -> LocalStorage:
    settings = get_settings()
    return LocalStorage(settings.data_dir / "uploads")


@lru_cache
def get_artifact_storage() -> LocalStorage:
    settings = get_settings()
    return LocalStorage(settings.data_dir / "artifacts")
