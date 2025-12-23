"""Tests for uploader module."""

import os
import tempfile

import pytest
from PIL import Image

from images2slides.models import BBoxPx, ImageDimensions, Layout, Region
from images2slides.uploader import (
    UploadError,
    crop_and_upload_regions,
    crop_region_png,
    get_file_hash,
    get_image_dimensions,
)


@pytest.fixture
def sample_image_path() -> str:
    """Create a sample image for testing."""
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        img = Image.new("RGB", (200, 100), color="red")
        # Draw some variation
        for x in range(50, 100):
            for y in range(25, 75):
                img.putpixel((x, y), (0, 255, 0))
        img.save(f.name, format="PNG")
        yield f.name
    os.unlink(f.name)


@pytest.fixture
def layout_with_image_regions() -> Layout:
    """Layout with image regions for testing."""
    return Layout(
        image_px=ImageDimensions(width=200, height=100),
        regions=(
            Region(
                id="green_box",
                order=1,
                type="image",
                bbox_px=BBoxPx(x=50, y=25, w=50, h=50),
                crop_from_infographic=True,
            ),
            Region(
                id="red_corner",
                order=2,
                type="image",
                bbox_px=BBoxPx(x=0, y=0, w=50, h=25),
                crop_from_infographic=True,
            ),
            Region(
                id="text_region",
                order=3,
                type="text",
                bbox_px=BBoxPx(x=100, y=50, w=100, h=50),
                text="Some text",
            ),
            Region(
                id="no_crop",
                order=4,
                type="image",
                bbox_px=BBoxPx(x=150, y=50, w=50, h=50),
                crop_from_infographic=False,
            ),
        ),
    )


class TestCropRegionPng:
    """Tests for crop_region_png function."""

    def test_crops_region(self, sample_image_path: str) -> None:
        """Test cropping a region from an image."""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as out:
            out_path = out.name

        try:
            bbox = BBoxPx(x=50, y=25, w=50, h=50)
            crop_region_png(sample_image_path, bbox, out_path)

            # Verify the cropped image
            with Image.open(out_path) as cropped:
                assert cropped.size == (50, 50)
                # Center should be green
                assert cropped.getpixel((25, 25)) == (0, 255, 0)
        finally:
            os.unlink(out_path)

    def test_crops_corner(self, sample_image_path: str) -> None:
        """Test cropping from corner of image."""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as out:
            out_path = out.name

        try:
            bbox = BBoxPx(x=0, y=0, w=50, h=25)
            crop_region_png(sample_image_path, bbox, out_path)

            with Image.open(out_path) as cropped:
                assert cropped.size == (50, 25)
                # Should be red
                assert cropped.getpixel((10, 10)) == (255, 0, 0)
        finally:
            os.unlink(out_path)

    def test_raises_on_invalid_path(self) -> None:
        """Test that invalid path raises UploadError."""
        bbox = BBoxPx(x=0, y=0, w=10, h=10)
        with pytest.raises(UploadError, match="Failed to crop"):
            crop_region_png("/nonexistent/image.png", bbox, "/tmp/out.png")


class TestGetFilehash:
    """Tests for get_file_hash function."""

    def test_returns_consistent_hash(self, sample_image_path: str) -> None:
        """Test that same file returns same hash."""
        hash1 = get_file_hash(sample_image_path)
        hash2 = get_file_hash(sample_image_path)
        assert hash1 == hash2
        assert len(hash1) == 16

    def test_different_files_different_hash(self) -> None:
        """Test that different files return different hashes."""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f1:
            img1 = Image.new("RGB", (10, 10), color="red")
            img1.save(f1.name)
            path1 = f1.name

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f2:
            img2 = Image.new("RGB", (10, 10), color="blue")
            img2.save(f2.name)
            path2 = f2.name

        try:
            hash1 = get_file_hash(path1)
            hash2 = get_file_hash(path2)
            assert hash1 != hash2
        finally:
            os.unlink(path1)
            os.unlink(path2)


class TestGetImageDimensions:
    """Tests for get_image_dimensions function."""

    def test_returns_correct_dimensions(self, sample_image_path: str) -> None:
        """Test getting image dimensions."""
        width, height = get_image_dimensions(sample_image_path)
        assert width == 200
        assert height == 100

    def test_different_sizes(self) -> None:
        """Test with different image sizes."""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            img = Image.new("RGB", (1920, 1080))
            img.save(f.name)
            path = f.name

        try:
            width, height = get_image_dimensions(path)
            assert width == 1920
            assert height == 1080
        finally:
            os.unlink(path)


class TestCropAndUploadRegions:
    """Tests for crop_and_upload_regions function."""

    def test_crops_all_image_regions(
        self, sample_image_path: str, layout_with_image_regions: Layout
    ) -> None:
        """Test that all image regions are processed (text regions excluded)."""
        uploaded: dict[str, str] = {}

        class MockUploader:
            def upload_png(self, local_path: str, object_name: str) -> str:
                url = f"https://mock.com/{object_name}"
                uploaded[object_name] = local_path
                return url

        with tempfile.TemporaryDirectory() as temp_dir:
            result = crop_and_upload_regions(
                infographic_path=sample_image_path,
                layout=layout_with_image_regions,
                uploader=MockUploader(),
                prefix="test_",
                temp_dir=temp_dir,
            )

        # Should have processed all image regions (green_box, red_corner, no_crop), not text_region
        assert len(result) == 3
        assert "green_box" in result
        assert "red_corner" in result
        assert "no_crop" in result
        assert "text_region" not in result

    def test_returns_urls(
        self, sample_image_path: str, layout_with_image_regions: Layout
    ) -> None:
        """Test that URLs are returned correctly."""

        class MockUploader:
            def upload_png(self, local_path: str, object_name: str) -> str:
                return f"https://storage.example.com/{object_name}"

        with tempfile.TemporaryDirectory() as temp_dir:
            result = crop_and_upload_regions(
                infographic_path=sample_image_path,
                layout=layout_with_image_regions,
                uploader=MockUploader(),
                temp_dir=temp_dir,
            )

        assert result["green_box"].startswith("https://storage.example.com/")
        assert "green_box" in result["green_box"]

    def test_uses_hash_in_object_name(
        self, sample_image_path: str, layout_with_image_regions: Layout
    ) -> None:
        """Test that object names include content hash."""
        object_names: list[str] = []

        class MockUploader:
            def upload_png(self, local_path: str, object_name: str) -> str:
                object_names.append(object_name)
                return f"https://mock.com/{object_name}"

        with tempfile.TemporaryDirectory() as temp_dir:
            crop_and_upload_regions(
                infographic_path=sample_image_path,
                layout=layout_with_image_regions,
                uploader=MockUploader(),
                prefix="pre_",
                temp_dir=temp_dir,
            )

        # Each object name should have format: pre_<id>_<hash>.png
        for name in object_names:
            assert name.startswith("pre_")
            assert name.endswith(".png")
            parts = name[:-4].split("_")  # Remove .png and split
            assert len(parts) >= 3  # pre, id, hash
