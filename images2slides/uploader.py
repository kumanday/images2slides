"""Image upload and cropping utilities."""

import hashlib
import logging
import os
import tempfile
from typing import Any, Protocol

from PIL import Image

from .models import BBoxPx, Layout

logger = logging.getLogger(__name__)


class UploadError(Exception):
    """Raised when image upload fails."""

    pass


class Uploader(Protocol):
    """Protocol for image uploaders."""

    def upload_png(self, local_path: str, object_name: str) -> str:
        """Upload a PNG file and return its public URL.

        Args:
            local_path: Local path to the PNG file.
            object_name: Name/key for the uploaded object.

        Returns:
            Public URL accessible by Google Slides API.
        """
        ...


class GCSUploader:
    """Google Cloud Storage uploader implementation."""

    def __init__(self, bucket_name: str) -> None:
        """Initialize GCS uploader.

        Args:
            bucket_name: Name of the GCS bucket.
        """
        self.bucket_name = bucket_name
        self._client: Any = None
        self._bucket: Any = None

    def _get_bucket(self) -> Any:
        """Lazy-load GCS client and bucket."""
        if self._bucket is None:
            from google.cloud import storage

            self._client = storage.Client()
            self._bucket = self._client.bucket(self.bucket_name)
        return self._bucket

    def upload_png(self, local_path: str, object_name: str) -> str:
        """Upload a PNG file to GCS.

        Args:
            local_path: Local path to the PNG file.
            object_name: Name/key for the uploaded object.

        Returns:
            Public URL of the uploaded image.

        Raises:
            UploadError: If upload fails.
        """
        try:
            bucket = self._get_bucket()
            blob = bucket.blob(object_name)
            blob.upload_from_filename(local_path, content_type="image/png")

            # Try to make public, but skip if bucket uses uniform access
            # (bucket must be configured for public access at bucket level)
            try:
                blob.make_public()
            except Exception:
                # Uniform bucket-level access enabled - assume bucket is already public
                logger.debug("Could not set object ACL (uniform access?), using public URL anyway")

            return blob.public_url
        except Exception as e:
            raise UploadError(f"Failed to upload {local_path}: {e}") from e


def crop_region_png(infographic_path: str, bbox: BBoxPx, out_path: str) -> None:
    """Crop a region from an infographic and save as PNG.

    Adds 10px padding to right and bottom to compensate for VLM bbox tightness.

    Args:
        infographic_path: Path to the source infographic image.
        bbox: Bounding box to crop (in pixels).
        out_path: Output path for the cropped PNG.

    Raises:
        UploadError: If cropping fails.
    """
    try:
        with Image.open(infographic_path) as img:
            img_w, img_h = img.size
            # Keep original top-left corner
            x1 = int(bbox.x)
            y1 = int(bbox.y)
            # Add 10px padding to right and bottom (clamped to image bounds)
            x2 = min(int(bbox.x) + int(bbox.w) + 10, img_w)
            y2 = min(int(bbox.y) + int(bbox.h) + 10, img_h)
            cropped = img.crop((x1, y1, x2, y2))
            cropped.save(out_path, format="PNG")
            logger.debug(f"Cropped region to {out_path}: {x2-x1}x{y2-y1} at ({x1},{y1})")
    except Exception as e:
        raise UploadError(f"Failed to crop region: {e}") from e


def get_file_hash(file_path: str) -> str:
    """Get SHA256 hash of a file for cache keying.

    Args:
        file_path: Path to the file.

    Returns:
        Hex string of the file's SHA256 hash.
    """
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()[:16]


def crop_and_upload_regions(
    infographic_path: str,
    layout: Layout,
    uploader: Uploader,
    prefix: str = "",
    temp_dir: str | None = None,
) -> dict[str, str]:
    """Crop and upload all image regions that need cropping.

    Args:
        infographic_path: Path to the source infographic.
        layout: Layout with regions to process.
        uploader: Uploader instance for uploading cropped images.
        prefix: Optional prefix for uploaded object names.
        temp_dir: Optional temp directory for cropped files.

    Returns:
        Dict mapping region ID to public URL.
    """
    cropped_urls: dict[str, str] = {}
    use_temp_dir = temp_dir or tempfile.mkdtemp(prefix="slides_crop_")

    for region in layout.regions:
        # Process all image regions - they need to be cropped from the infographic
        if region.type != "image":
            continue

        # Generate unique filename based on content
        crop_filename = f"{prefix}{region.id}.png"
        crop_path = os.path.join(use_temp_dir, crop_filename)

        try:
            crop_region_png(infographic_path, region.bbox_px, crop_path)
            file_hash = get_file_hash(crop_path)
            object_name = f"{prefix}{region.id}_{file_hash}.png"
            url = uploader.upload_png(crop_path, object_name)
            cropped_urls[region.id] = url
            logger.info(f"Uploaded cropped region {region.id} to {url}")
        except UploadError as e:
            logger.error(f"Failed to process region {region.id}: {e}")
            raise

    return cropped_urls


def get_image_dimensions(image_path: str) -> tuple[int, int]:
    """Get dimensions of an image file.

    Args:
        image_path: Path to the image file.

    Returns:
        Tuple of (width, height) in pixels.
    """
    with Image.open(image_path) as img:
        return img.size
