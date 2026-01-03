"""Storage abstraction layer."""

import hashlib
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

from PIL import Image

from ..config import settings


class Storage(ABC):
    """Abstract base class for storage backends."""

    @abstractmethod
    async def get_upload_url(
        self, key: str, content_type: str, expires_in: int = 3600
    ) -> str:
        """Get a URL for uploading a file.
        
        Args:
            key: Storage key (path).
            content_type: MIME type of the file.
            expires_in: URL expiration in seconds.
            
        Returns:
            Upload URL (may be a presigned URL or direct endpoint).
        """
        pass

    @abstractmethod
    async def get_download_url(self, key: str, expires_in: int = 3600) -> str:
        """Get a URL for downloading a file.
        
        Args:
            key: Storage key (path).
            expires_in: URL expiration in seconds.
            
        Returns:
            Download URL.
        """
        pass

    @abstractmethod
    async def get_metadata(self, key: str) -> dict[str, Any]:
        """Get metadata for a stored file.
        
        Args:
            key: Storage key (path).
            
        Returns:
            Dict with size, content_type, sha256, width, height.
        """
        pass

    @abstractmethod
    async def put(self, key: str, data: bytes, content_type: str) -> None:
        """Store data directly.
        
        Args:
            key: Storage key (path).
            data: File contents.
            content_type: MIME type.
        """
        pass

    @abstractmethod
    async def get(self, key: str) -> bytes:
        """Retrieve data directly.
        
        Args:
            key: Storage key (path).
            
        Returns:
            File contents.
        """
        pass

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Delete a file.
        
        Args:
            key: Storage key (path).
        """
        pass

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if a file exists.
        
        Args:
            key: Storage key (path).
            
        Returns:
            True if file exists.
        """
        pass


class LocalStorage(Storage):
    """Local filesystem storage for development."""

    def __init__(self, base_path: str, base_url: str = "http://localhost:8000/files"):
        self.base_path = Path(base_path)
        self.base_url = base_url
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _get_path(self, key: str) -> Path:
        """Get full path for a storage key."""
        return self.base_path / key

    async def get_upload_url(
        self, key: str, content_type: str, expires_in: int = 3600
    ) -> str:
        """For local storage, return direct upload endpoint."""
        # Ensure parent directory exists
        path = self._get_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        # Return the direct file endpoint
        return f"{self.base_url}/{key}"

    async def get_download_url(self, key: str, expires_in: int = 3600) -> str:
        """For local storage, return direct download URL."""
        return f"{self.base_url}/{key}"

    async def get_metadata(self, key: str) -> dict[str, Any]:
        """Get file metadata from local filesystem."""
        path = self._get_path(key)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {key}")

        # Read file and compute hash
        data = path.read_bytes()
        sha256 = hashlib.sha256(data).hexdigest()

        # Guess content type
        ext = path.suffix.lower()
        content_types = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
            ".json": "application/json",
        }
        content_type = content_types.get(ext, "application/octet-stream")

        metadata = {
            "size": len(data),
            "content_type": content_type,
            "sha256": sha256,
        }

        # Get image dimensions if applicable
        if content_type.startswith("image/"):
            try:
                with Image.open(path) as img:
                    metadata["width"] = img.width
                    metadata["height"] = img.height
            except Exception:
                pass

        return metadata

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        """Write data to local filesystem."""
        path = self._get_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    async def get(self, key: str) -> bytes:
        """Read data from local filesystem."""
        path = self._get_path(key)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {key}")
        return path.read_bytes()

    async def delete(self, key: str) -> None:
        """Delete file from local filesystem."""
        path = self._get_path(key)
        if path.exists():
            path.unlink()

    async def exists(self, key: str) -> bool:
        """Check if file exists on local filesystem."""
        return self._get_path(key).exists()


# Singleton instance
_storage: Storage | None = None


def get_storage() -> Storage:
    """Get the configured storage backend.
    
    Returns:
        Storage instance based on configuration.
    """
    global _storage

    if _storage is not None:
        return _storage

    if settings.storage_type == "local":
        _storage = LocalStorage(
            base_path=settings.local_storage_path,
            base_url=f"{settings.app_base_url.rstrip('/')}/api/v1/files",
        )
    elif settings.storage_type == "s3":
        raise NotImplementedError("S3 storage not yet implemented")
    elif settings.storage_type == "gcs":
        raise NotImplementedError("GCS storage not yet implemented")
    else:
        raise ValueError(f"Unknown storage type: {settings.storage_type}")

    return _storage