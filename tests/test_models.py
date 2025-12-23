"""Tests for models module."""

import json

import pytest

from images2slides.models import (
    BBoxPx,
    ImageDimensions,
    Layout,
    Region,
    TextStyle,
)


class TestBBoxPx:
    """Tests for BBoxPx dataclass."""

    def test_to_dict(self) -> None:
        """Test conversion to dictionary."""
        bbox = BBoxPx(x=10, y=20, w=100, h=50)
        assert bbox.to_dict() == {"x": 10, "y": 20, "w": 100, "h": 50}

    def test_from_dict(self) -> None:
        """Test creation from dictionary."""
        data = {"x": 10, "y": 20, "w": 100, "h": 50}
        bbox = BBoxPx.from_dict(data)
        assert bbox.x == 10
        assert bbox.y == 20
        assert bbox.w == 100
        assert bbox.h == 50

    def test_area(self) -> None:
        """Test area calculation."""
        bbox = BBoxPx(x=0, y=0, w=100, h=50)
        assert bbox.area == 5000

    def test_center(self) -> None:
        """Test center point calculation."""
        bbox = BBoxPx(x=100, y=200, w=50, h=30)
        cx, cy = bbox.center
        assert cx == 125
        assert cy == 215

    def test_roundtrip(self) -> None:
        """Test dict roundtrip preserves values."""
        original = BBoxPx(x=15.5, y=25.5, w=100.0, h=50.0)
        roundtrip = BBoxPx.from_dict(original.to_dict())
        assert roundtrip == original


class TestTextStyle:
    """Tests for TextStyle dataclass."""

    def test_to_dict(self) -> None:
        """Test conversion to dictionary."""
        style = TextStyle(font_family="Arial", font_size_pt=24, bold=True)
        assert style.to_dict() == {
            "font_family": "Arial",
            "font_size_pt": 24,
            "bold": True,
        }

    def test_from_dict(self) -> None:
        """Test creation from dictionary."""
        data = {"font_family": "Roboto", "font_size_pt": 18, "bold": False}
        style = TextStyle.from_dict(data)
        assert style is not None
        assert style.font_family == "Roboto"
        assert style.font_size_pt == 18
        assert style.bold is False

    def test_from_dict_none(self) -> None:
        """Test from_dict with None returns None."""
        assert TextStyle.from_dict(None) is None

    def test_from_dict_partial(self) -> None:
        """Test from_dict with partial data."""
        style = TextStyle.from_dict({"font_family": "Arial"})
        assert style is not None
        assert style.font_family == "Arial"
        assert style.font_size_pt is None
        assert style.bold is None


class TestRegion:
    """Tests for Region dataclass."""

    def test_to_dict(self) -> None:
        """Test conversion to dictionary."""
        region = Region(
            id="title",
            order=1,
            type="text",
            bbox_px=BBoxPx(x=0, y=0, w=100, h=50),
            text="Hello",
            style=TextStyle(font_family="Arial"),
        )
        d = region.to_dict()
        assert d["id"] == "title"
        assert d["order"] == 1
        assert d["type"] == "text"
        assert d["bbox_px"] == {"x": 0, "y": 0, "w": 100, "h": 50}
        assert d["text"] == "Hello"
        assert d["style"]["font_family"] == "Arial"

    def test_from_dict(self) -> None:
        """Test creation from dictionary."""
        data = {
            "id": "icon_1",
            "order": 2,
            "type": "image",
            "bbox_px": {"x": 10, "y": 20, "w": 50, "h": 50},
            "crop_from_infographic": True,
        }
        region = Region.from_dict(data)
        assert region.id == "icon_1"
        assert region.order == 2
        assert region.type == "image"
        assert region.crop_from_infographic is True

    def test_is_text(self) -> None:
        """Test is_text property."""
        text_region = Region(
            id="t1", order=1, type="text", bbox_px=BBoxPx(0, 0, 100, 50)
        )
        image_region = Region(
            id="i1", order=2, type="image", bbox_px=BBoxPx(0, 0, 100, 50)
        )
        assert text_region.is_text is True
        assert text_region.is_image is False
        assert image_region.is_text is False
        assert image_region.is_image is True

    def test_default_order_from_index(self) -> None:
        """Test that order defaults to index + 1."""
        data = {
            "id": "test",
            "type": "text",
            "bbox_px": {"x": 0, "y": 0, "w": 10, "h": 10},
        }
        region = Region.from_dict(data, index=5)
        assert region.order == 6


class TestImageDimensions:
    """Tests for ImageDimensions dataclass."""

    def test_to_dict(self) -> None:
        """Test conversion to dictionary."""
        dims = ImageDimensions(width=1920, height=1080)
        assert dims.to_dict() == {"width": 1920, "height": 1080}

    def test_from_dict(self) -> None:
        """Test creation from dictionary."""
        dims = ImageDimensions.from_dict({"width": 800, "height": 600})
        assert dims.width == 800
        assert dims.height == 600

    def test_aspect_ratio(self) -> None:
        """Test aspect ratio calculation."""
        dims = ImageDimensions(width=1920, height=1080)
        assert dims.aspect_ratio == pytest.approx(16 / 9)

    def test_aspect_ratio_zero_height(self) -> None:
        """Test aspect ratio with zero height."""
        dims = ImageDimensions(width=100, height=0)
        assert dims.aspect_ratio == 0


class TestLayout:
    """Tests for Layout dataclass."""

    @pytest.fixture
    def sample_layout(self) -> Layout:
        """Create a sample layout for testing."""
        return Layout(
            image_px=ImageDimensions(width=1600, height=900),
            regions=(
                Region(
                    id="title",
                    order=1,
                    type="text",
                    bbox_px=BBoxPx(x=100, y=50, w=400, h=60),
                    text="Test Title",
                ),
                Region(
                    id="icon",
                    order=2,
                    type="image",
                    bbox_px=BBoxPx(x=50, y=200, w=100, h=100),
                    crop_from_infographic=True,
                ),
            ),
        )

    def test_to_dict(self, sample_layout: Layout) -> None:
        """Test conversion to dictionary."""
        d = sample_layout.to_dict()
        assert d["image_px"] == {"width": 1600, "height": 900}
        assert len(d["regions"]) == 2
        assert d["regions"][0]["id"] == "title"

    def test_to_json(self, sample_layout: Layout) -> None:
        """Test conversion to JSON string."""
        json_str = sample_layout.to_json()
        parsed = json.loads(json_str)
        assert parsed["image_px"]["width"] == 1600
        assert len(parsed["regions"]) == 2

    def test_from_dict(self) -> None:
        """Test creation from dictionary."""
        data = {
            "image_px": {"width": 800, "height": 600},
            "regions": [
                {
                    "id": "r1",
                    "type": "text",
                    "bbox_px": {"x": 0, "y": 0, "w": 100, "h": 50},
                    "text": "Hello",
                }
            ],
        }
        layout = Layout.from_dict(data)
        assert layout.image_px.width == 800
        assert len(layout.regions) == 1
        assert layout.regions[0].text == "Hello"

    def test_from_json(self) -> None:
        """Test creation from JSON string."""
        json_str = '{"image_px": {"width": 640, "height": 480}, "regions": []}'
        layout = Layout.from_json(json_str)
        assert layout.image_px.width == 640
        assert layout.image_px.height == 480
        assert len(layout.regions) == 0

    def test_text_regions(self, sample_layout: Layout) -> None:
        """Test text_regions property."""
        text_regions = sample_layout.text_regions
        assert len(text_regions) == 1
        assert text_regions[0].id == "title"

    def test_image_regions(self, sample_layout: Layout) -> None:
        """Test image_regions property."""
        image_regions = sample_layout.image_regions
        assert len(image_regions) == 1
        assert image_regions[0].id == "icon"

    def test_roundtrip_dict(self, sample_layout: Layout) -> None:
        """Test dict roundtrip preserves structure."""
        roundtrip = Layout.from_dict(sample_layout.to_dict())
        assert roundtrip.image_px == sample_layout.image_px
        assert len(roundtrip.regions) == len(sample_layout.regions)
        assert roundtrip.regions[0].id == sample_layout.regions[0].id

    def test_roundtrip_json(self, sample_layout: Layout) -> None:
        """Test JSON roundtrip preserves structure."""
        roundtrip = Layout.from_json(sample_layout.to_json())
        assert roundtrip.image_px == sample_layout.image_px
        assert len(roundtrip.regions) == len(sample_layout.regions)
