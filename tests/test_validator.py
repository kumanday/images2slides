"""Tests for validator module."""

import pytest

from images2slides.models import BBoxPx
from images2slides.validator import (
    LayoutValidationError,
    clamp_bbox_to_bounds,
    validate_layout,
)


class TestValidateLayout:
    """Tests for validate_layout function."""

    def test_valid_layout(self, sample_layout_dict: dict) -> None:
        """Test validation of valid layout."""
        layout = validate_layout(sample_layout_dict)
        assert layout.image_px.width == 1600
        assert layout.image_px.height == 900
        assert len(layout.regions) == 2

    def test_missing_image_px(self) -> None:
        """Test error when image_px is missing."""
        data = {"regions": []}
        with pytest.raises(LayoutValidationError, match="Missing 'image_px'"):
            validate_layout(data)

    def test_missing_regions(self) -> None:
        """Test error when regions is missing."""
        data = {"image_px": {"width": 1600, "height": 900}}
        with pytest.raises(LayoutValidationError, match="Missing 'regions'"):
            validate_layout(data)

    def test_missing_region_id(self) -> None:
        """Test error when region id is missing."""
        data = {
            "image_px": {"width": 1600, "height": 900},
            "regions": [{"type": "text", "bbox_px": {"x": 0, "y": 0, "w": 100, "h": 100}}],
        }
        with pytest.raises(LayoutValidationError, match="missing 'id'"):
            validate_layout(data)

    def test_missing_region_type(self) -> None:
        """Test error when region type is missing."""
        data = {
            "image_px": {"width": 1600, "height": 900},
            "regions": [{"id": "test", "bbox_px": {"x": 0, "y": 0, "w": 100, "h": 100}}],
        }
        with pytest.raises(LayoutValidationError, match="missing 'type'"):
            validate_layout(data)

    def test_invalid_region_type(self) -> None:
        """Test error when region type is invalid."""
        data = {
            "image_px": {"width": 1600, "height": 900},
            "regions": [
                {"id": "test", "type": "invalid", "bbox_px": {"x": 0, "y": 0, "w": 100, "h": 100}}
            ],
        }
        with pytest.raises(LayoutValidationError, match="must be 'text' or 'image'"):
            validate_layout(data)

    def test_missing_bbox_field(self) -> None:
        """Test error when bbox field is missing."""
        data = {
            "image_px": {"width": 1600, "height": 900},
            "regions": [
                {"id": "test", "type": "text", "bbox_px": {"x": 0, "y": 0, "w": 100}}
            ],
        }
        with pytest.raises(LayoutValidationError, match="missing required field: h"):
            validate_layout(data)

    def test_default_values(self) -> None:
        """Test that default values are applied."""
        data = {
            "image_px": {"width": 800, "height": 600},
            "regions": [
                {
                    "id": "minimal",
                    "type": "text",
                    "bbox_px": {"x": 10, "y": 20, "w": 100, "h": 50},
                }
            ],
        }
        layout = validate_layout(data)
        region = layout.regions[0]
        assert region.order == 1
        assert region.confidence == 1.0
        assert region.crop_from_infographic is False
        assert region.notes is None


class TestClampBboxToBounds:
    """Tests for clamp_bbox_to_bounds function."""

    def test_bbox_within_bounds(self) -> None:
        """Test bbox already within bounds."""
        bbox = BBoxPx(x=100, y=100, w=200, h=200)
        clamped = clamp_bbox_to_bounds(bbox, 1000, 1000)
        assert clamped == bbox

    def test_bbox_exceeds_right(self) -> None:
        """Test bbox exceeding right edge."""
        bbox = BBoxPx(x=900, y=100, w=200, h=200)
        clamped = clamp_bbox_to_bounds(bbox, 1000, 1000)
        assert clamped.x == 900
        assert clamped.w == 100

    def test_bbox_exceeds_bottom(self) -> None:
        """Test bbox exceeding bottom edge."""
        bbox = BBoxPx(x=100, y=900, w=200, h=200)
        clamped = clamp_bbox_to_bounds(bbox, 1000, 1000)
        assert clamped.y == 900
        assert clamped.h == 100

    def test_bbox_negative_coords(self) -> None:
        """Test bbox with negative coordinates."""
        bbox = BBoxPx(x=-50, y=-30, w=200, h=200)
        clamped = clamp_bbox_to_bounds(bbox, 1000, 1000)
        assert clamped.x == 0
        assert clamped.y == 0
        assert clamped.w == 200
        assert clamped.h == 200
