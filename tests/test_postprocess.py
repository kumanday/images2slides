"""Tests for postprocess module."""

import pytest

from images2slides.models import BBoxPx, ImageDimensions, Layout, Region
from images2slides.postprocess import (
    clamp_to_bounds,
    compute_bbox_iou,
    compute_overlap_area,
    drop_empty_regions,
    enforce_minimum_size,
    find_overlapping_regions,
    get_layout_statistics,
    normalize_spaces,
    postprocess_layout,
    sort_by_reading_order,
    trim_whitespace,
    validate_layout,
)


@pytest.fixture
def layout_with_whitespace() -> Layout:
    """Layout with whitespace in text."""
    return Layout(
        image_px=ImageDimensions(width=1000, height=1000),
        regions=(
            Region(
                id="r1",
                order=1,
                type="text",
                bbox_px=BBoxPx(x=0, y=0, w=100, h=50),
                text="  hello world  ",
            ),
        ),
    )


@pytest.fixture
def layout_with_multiple_spaces() -> Layout:
    """Layout with multiple spaces in text."""
    return Layout(
        image_px=ImageDimensions(width=1000, height=1000),
        regions=(
            Region(
                id="r1",
                order=1,
                type="text",
                bbox_px=BBoxPx(x=0, y=0, w=100, h=50),
                text="hello    world   test",
            ),
        ),
    )


@pytest.fixture
def layout_with_empty_regions() -> Layout:
    """Layout with empty text regions."""
    return Layout(
        image_px=ImageDimensions(width=1000, height=1000),
        regions=(
            Region(
                id="r1",
                order=1,
                type="text",
                bbox_px=BBoxPx(x=0, y=0, w=100, h=50),
                text="valid",
            ),
            Region(
                id="r2",
                order=2,
                type="text",
                bbox_px=BBoxPx(x=0, y=100, w=100, h=50),
                text="",
            ),
            Region(
                id="r3",
                order=3,
                type="text",
                bbox_px=BBoxPx(x=0, y=200, w=100, h=50),
                text="   ",
            ),
            Region(
                id="r4",
                order=4,
                type="image",
                bbox_px=BBoxPx(x=0, y=300, w=100, h=50),
            ),
        ),
    )


class TestTrimWhitespace:
    """Tests for trim_whitespace function."""

    def test_trims_leading_trailing(self, layout_with_whitespace: Layout) -> None:
        """Test trimming leading and trailing whitespace."""
        result = trim_whitespace(layout_with_whitespace)
        assert result.regions[0].text == "hello world"

    def test_preserves_image_regions(self) -> None:
        """Test that image regions are preserved."""
        layout = Layout(
            image_px=ImageDimensions(width=1000, height=1000),
            regions=(
                Region(
                    id="img",
                    order=1,
                    type="image",
                    bbox_px=BBoxPx(x=0, y=0, w=100, h=100),
                ),
            ),
        )
        result = trim_whitespace(layout)
        assert len(result.regions) == 1
        assert result.regions[0].type == "image"


class TestNormalizeSpaces:
    """Tests for normalize_spaces function."""

    def test_normalizes_multiple_spaces(self, layout_with_multiple_spaces: Layout) -> None:
        """Test normalizing multiple spaces to single space."""
        result = normalize_spaces(layout_with_multiple_spaces)
        assert result.regions[0].text == "hello world test"


class TestDropEmptyRegions:
    """Tests for drop_empty_regions function."""

    def test_drops_empty_text_regions(self, layout_with_empty_regions: Layout) -> None:
        """Test dropping empty text regions."""
        result = drop_empty_regions(layout_with_empty_regions)
        assert len(result.regions) == 2
        ids = [r.id for r in result.regions]
        assert "r1" in ids
        assert "r4" in ids
        assert "r2" not in ids
        assert "r3" not in ids


class TestClampToBounds:
    """Tests for clamp_to_bounds function."""

    def test_clamps_out_of_bounds(self) -> None:
        """Test clamping regions outside image bounds."""
        layout = Layout(
            image_px=ImageDimensions(width=500, height=500),
            regions=(
                Region(
                    id="r1",
                    order=1,
                    type="text",
                    bbox_px=BBoxPx(x=400, y=400, w=200, h=200),
                    text="test",
                ),
            ),
        )
        result = clamp_to_bounds(layout)
        bbox = result.regions[0].bbox_px
        assert bbox.w == 100
        assert bbox.h == 100


class TestSortByReadingOrder:
    """Tests for sort_by_reading_order function."""

    def test_sorts_by_order_then_position(self) -> None:
        """Test sorting by order, then y, then x."""
        layout = Layout(
            image_px=ImageDimensions(width=1000, height=1000),
            regions=(
                Region(id="r3", order=2, type="text", bbox_px=BBoxPx(x=0, y=0, w=50, h=50), text="c"),
                Region(id="r1", order=1, type="text", bbox_px=BBoxPx(x=100, y=0, w=50, h=50), text="a"),
                Region(id="r2", order=1, type="text", bbox_px=BBoxPx(x=0, y=0, w=50, h=50), text="b"),
            ),
        )
        result = sort_by_reading_order(layout)
        ids = [r.id for r in result.regions]
        assert ids == ["r2", "r1", "r3"]


class TestEnforceMinimumSize:
    """Tests for enforce_minimum_size function."""

    def test_expands_small_regions(self) -> None:
        """Test expanding regions smaller than minimum."""
        layout = Layout(
            image_px=ImageDimensions(width=1000, height=1000),
            regions=(
                Region(
                    id="r1",
                    order=1,
                    type="text",
                    bbox_px=BBoxPx(x=0, y=0, w=5, h=5),
                    text="tiny",
                ),
            ),
        )
        result = enforce_minimum_size(layout, min_w=20, min_h=20)
        assert result.regions[0].bbox_px.w == 20
        assert result.regions[0].bbox_px.h == 20


class TestPostprocessLayout:
    """Tests for postprocess_layout function."""

    def test_applies_all_steps(self) -> None:
        """Test that all postprocessing steps are applied."""
        layout = Layout(
            image_px=ImageDimensions(width=500, height=500),
            regions=(
                Region(
                    id="r1",
                    order=2,
                    type="text",
                    bbox_px=BBoxPx(x=0, y=100, w=5, h=5),
                    text="  hello    world  ",
                ),
                Region(
                    id="r2",
                    order=1,
                    type="text",
                    bbox_px=BBoxPx(x=0, y=0, w=100, h=50),
                    text="",
                ),
            ),
        )
        result = postprocess_layout(layout)
        assert len(result.regions) == 1
        assert result.regions[0].text == "hello world"
        assert result.regions[0].bbox_px.w >= 10
        assert result.regions[0].bbox_px.h >= 10


class TestComputeBboxIou:
    """Tests for compute_bbox_iou function."""

    def test_identical_boxes(self) -> None:
        """Test IoU of identical boxes is 1.0."""
        a = BBoxPx(x=0, y=0, w=100, h=100)
        b = BBoxPx(x=0, y=0, w=100, h=100)
        assert compute_bbox_iou(a, b) == pytest.approx(1.0)

    def test_no_overlap(self) -> None:
        """Test IoU of non-overlapping boxes is 0.0."""
        a = BBoxPx(x=0, y=0, w=50, h=50)
        b = BBoxPx(x=100, y=100, w=50, h=50)
        assert compute_bbox_iou(a, b) == 0.0

    def test_partial_overlap(self) -> None:
        """Test IoU of partially overlapping boxes."""
        a = BBoxPx(x=0, y=0, w=100, h=100)
        b = BBoxPx(x=50, y=50, w=100, h=100)
        # Intersection: 50x50 = 2500
        # Union: 10000 + 10000 - 2500 = 17500
        # IoU: 2500/17500 = 0.142857
        assert compute_bbox_iou(a, b) == pytest.approx(2500 / 17500)

    def test_one_inside_other(self) -> None:
        """Test IoU when one box is inside another."""
        outer = BBoxPx(x=0, y=0, w=100, h=100)
        inner = BBoxPx(x=25, y=25, w=50, h=50)
        # Intersection: 2500
        # Union: 10000 + 2500 - 2500 = 10000
        # IoU: 2500/10000 = 0.25
        assert compute_bbox_iou(outer, inner) == pytest.approx(0.25)


class TestComputeOverlapArea:
    """Tests for compute_overlap_area function."""

    def test_no_overlap(self) -> None:
        """Test overlap area of non-overlapping boxes."""
        a = BBoxPx(x=0, y=0, w=50, h=50)
        b = BBoxPx(x=100, y=100, w=50, h=50)
        assert compute_overlap_area(a, b) == 0.0

    def test_partial_overlap(self) -> None:
        """Test overlap area of partially overlapping boxes."""
        a = BBoxPx(x=0, y=0, w=100, h=100)
        b = BBoxPx(x=50, y=50, w=100, h=100)
        assert compute_overlap_area(a, b) == 2500.0

    def test_touching_edges(self) -> None:
        """Test boxes that touch at edge have 0 overlap."""
        a = BBoxPx(x=0, y=0, w=50, h=50)
        b = BBoxPx(x=50, y=0, w=50, h=50)
        assert compute_overlap_area(a, b) == 0.0


class TestFindOverlappingRegions:
    """Tests for find_overlapping_regions function."""

    def test_finds_overlapping_regions(self) -> None:
        """Test finding overlapping regions."""
        layout = Layout(
            image_px=ImageDimensions(width=1000, height=1000),
            regions=(
                Region(
                    id="r1", order=1, type="text",
                    bbox_px=BBoxPx(x=0, y=0, w=100, h=100), text="a"
                ),
                Region(
                    id="r2", order=2, type="text",
                    bbox_px=BBoxPx(x=50, y=50, w=100, h=100), text="b"
                ),
                Region(
                    id="r3", order=3, type="text",
                    bbox_px=BBoxPx(x=500, y=500, w=50, h=50), text="c"
                ),
            ),
        )
        overlaps = find_overlapping_regions(layout, iou_threshold=0.1)
        assert len(overlaps) == 1
        assert overlaps[0].region_a_id == "r1"
        assert overlaps[0].region_b_id == "r2"

    def test_no_overlaps(self) -> None:
        """Test layout with no overlapping regions."""
        layout = Layout(
            image_px=ImageDimensions(width=1000, height=1000),
            regions=(
                Region(
                    id="r1", order=1, type="text",
                    bbox_px=BBoxPx(x=0, y=0, w=50, h=50), text="a"
                ),
                Region(
                    id="r2", order=2, type="text",
                    bbox_px=BBoxPx(x=200, y=200, w=50, h=50), text="b"
                ),
            ),
        )
        overlaps = find_overlapping_regions(layout)
        assert len(overlaps) == 0


class TestValidateLayout:
    """Tests for validate_layout function."""

    def test_warns_on_low_confidence(self) -> None:
        """Test warning for low confidence regions."""
        layout = Layout(
            image_px=ImageDimensions(width=1000, height=1000),
            regions=(
                Region(
                    id="low_conf", order=1, type="text",
                    bbox_px=BBoxPx(x=0, y=0, w=100, h=50),
                    text="test", confidence=0.5
                ),
            ),
        )
        warnings = validate_layout(layout, confidence_threshold=0.7)
        low_conf_warnings = [w for w in warnings if w.warning_type == "low_confidence"]
        assert len(low_conf_warnings) == 1
        assert low_conf_warnings[0].region_id == "low_conf"

    def test_warns_on_notes(self) -> None:
        """Test info for regions with notes."""
        layout = Layout(
            image_px=ImageDimensions(width=1000, height=1000),
            regions=(
                Region(
                    id="noted", order=1, type="text",
                    bbox_px=BBoxPx(x=0, y=0, w=100, h=50),
                    text="test", notes="Check this region"
                ),
            ),
        )
        warnings = validate_layout(layout)
        notes_warnings = [w for w in warnings if w.warning_type == "has_notes"]
        assert len(notes_warnings) == 1
        assert notes_warnings[0].severity == "info"

    def test_warns_on_empty_text(self) -> None:
        """Test warning for empty text regions."""
        layout = Layout(
            image_px=ImageDimensions(width=1000, height=1000),
            regions=(
                Region(
                    id="empty", order=1, type="text",
                    bbox_px=BBoxPx(x=0, y=0, w=100, h=50),
                    text=None
                ),
            ),
        )
        warnings = validate_layout(layout)
        empty_warnings = [w for w in warnings if w.warning_type == "empty_text"]
        assert len(empty_warnings) == 1

    def test_warns_on_small_regions(self) -> None:
        """Test info for very small regions."""
        layout = Layout(
            image_px=ImageDimensions(width=1000, height=1000),
            regions=(
                Region(
                    id="tiny", order=1, type="text",
                    bbox_px=BBoxPx(x=0, y=0, w=5, h=5),
                    text="x"
                ),
            ),
        )
        warnings = validate_layout(layout)
        small_warnings = [w for w in warnings if w.warning_type == "small_region"]
        assert len(small_warnings) == 1

    def test_warns_on_overlaps(self) -> None:
        """Test warning for overlapping regions."""
        layout = Layout(
            image_px=ImageDimensions(width=1000, height=1000),
            regions=(
                Region(
                    id="r1", order=1, type="text",
                    bbox_px=BBoxPx(x=0, y=0, w=100, h=100), text="a"
                ),
                Region(
                    id="r2", order=2, type="text",
                    bbox_px=BBoxPx(x=10, y=10, w=100, h=100), text="b"
                ),
            ),
        )
        warnings = validate_layout(layout, iou_threshold=0.1)
        overlap_warnings = [w for w in warnings if w.warning_type == "overlap"]
        assert len(overlap_warnings) == 1


class TestGetLayoutStatistics:
    """Tests for get_layout_statistics function."""

    def test_computes_statistics(self) -> None:
        """Test computing layout statistics."""
        layout = Layout(
            image_px=ImageDimensions(width=1000, height=1000),
            regions=(
                Region(
                    id="r1", order=1, type="text",
                    bbox_px=BBoxPx(x=0, y=0, w=100, h=100),
                    text="Hello World", confidence=0.9
                ),
                Region(
                    id="r2", order=2, type="image",
                    bbox_px=BBoxPx(x=200, y=200, w=50, h=50),
                    confidence=0.8
                ),
            ),
        )
        stats = get_layout_statistics(layout)
        assert stats["total_regions"] == 2
        assert stats["text_regions"] == 1
        assert stats["image_regions"] == 1
        assert stats["avg_confidence"] == pytest.approx(0.85)
        assert stats["min_confidence"] == 0.8
        assert stats["max_confidence"] == 0.9
        assert stats["total_text_chars"] == 11
        assert stats["image_width"] == 1000
        assert stats["image_height"] == 1000

    def test_empty_layout_statistics(self) -> None:
        """Test statistics for empty layout."""
        layout = Layout(
            image_px=ImageDimensions(width=800, height=600),
            regions=(),
        )
        stats = get_layout_statistics(layout)
        assert stats["total_regions"] == 0
        assert stats["avg_confidence"] == 0
        assert stats["total_text_chars"] == 0
