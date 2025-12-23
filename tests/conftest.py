"""Pytest fixtures for slides-infographic tests."""

import pytest

from images2slides.models import BBoxPx, ImageDimensions, Layout, Region, TextStyle


@pytest.fixture
def sample_bbox() -> BBoxPx:
    """Sample bounding box."""
    return BBoxPx(x=100, y=50, w=400, h=60)


@pytest.fixture
def sample_text_style() -> TextStyle:
    """Sample text style."""
    return TextStyle(font_family="Arial", font_size_pt=24, bold=True)


@pytest.fixture
def sample_text_region(sample_bbox: BBoxPx, sample_text_style: TextStyle) -> Region:
    """Sample text region."""
    return Region(
        id="title",
        order=1,
        type="text",
        bbox_px=sample_bbox,
        text="Test Title",
        style=sample_text_style,
        confidence=0.95,
    )


@pytest.fixture
def sample_image_region() -> Region:
    """Sample image region."""
    return Region(
        id="icon_1",
        order=2,
        type="image",
        bbox_px=BBoxPx(x=50, y=200, w=100, h=100),
        crop_from_infographic=True,
        confidence=0.9,
    )


@pytest.fixture
def sample_layout(sample_text_region: Region, sample_image_region: Region) -> Layout:
    """Sample layout with text and image regions."""
    return Layout(
        image_px=ImageDimensions(width=1600, height=900),
        regions=(sample_text_region, sample_image_region),
    )


@pytest.fixture
def sample_layout_dict() -> dict:
    """Sample layout as raw dict (before validation)."""
    return {
        "image_px": {"width": 1600, "height": 900},
        "regions": [
            {
                "id": "title",
                "order": 1,
                "type": "text",
                "bbox_px": {"x": 100, "y": 50, "w": 400, "h": 60},
                "text": "Test Title",
                "style": {"font_family": "Arial", "font_size_pt": 24, "bold": True},
                "confidence": 0.95,
            },
            {
                "id": "icon_1",
                "order": 2,
                "type": "image",
                "bbox_px": {"x": 50, "y": 200, "w": 100, "h": 100},
                "crop_from_infographic": True,
                "confidence": 0.9,
            },
        ],
    }
