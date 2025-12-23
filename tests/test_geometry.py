"""Tests for geometry module."""

import pytest

from images2slides.geometry import Fit, bbox_px_to_pt, compute_fit
from images2slides.models import BBoxPx


class TestComputeFit:
    """Tests for compute_fit function."""

    def test_landscape_image_on_landscape_slide(self) -> None:
        """Test fitting 16:9 image on 4:3 slide."""
        fit = compute_fit(1600, 900, 720, 540)
        assert fit.scale == pytest.approx(0.45)
        assert fit.offset_x_pt == pytest.approx(0)
        assert fit.offset_y_pt == pytest.approx(67.5)
        assert fit.placed_w_pt == pytest.approx(720)
        assert fit.placed_h_pt == pytest.approx(405)

    def test_square_image_on_landscape_slide(self) -> None:
        """Test fitting square image on landscape slide."""
        fit = compute_fit(1000, 1000, 720, 540)
        assert fit.scale == pytest.approx(0.54)
        assert fit.placed_w_pt == pytest.approx(540)
        assert fit.placed_h_pt == pytest.approx(540)
        assert fit.offset_x_pt == pytest.approx(90)
        assert fit.offset_y_pt == pytest.approx(0)

    def test_portrait_image_on_landscape_slide(self) -> None:
        """Test fitting portrait image on landscape slide."""
        fit = compute_fit(600, 1000, 720, 540)
        assert fit.scale == pytest.approx(0.54)
        assert fit.placed_h_pt == pytest.approx(540)
        assert fit.placed_w_pt == pytest.approx(324)
        assert fit.offset_y_pt == pytest.approx(0)
        assert fit.offset_x_pt == pytest.approx(198)

    def test_exact_fit(self) -> None:
        """Test when image aspect ratio matches slide."""
        fit = compute_fit(1440, 1080, 720, 540)
        assert fit.scale == pytest.approx(0.5)
        assert fit.offset_x_pt == pytest.approx(0)
        assert fit.offset_y_pt == pytest.approx(0)
        assert fit.placed_w_pt == pytest.approx(720)
        assert fit.placed_h_pt == pytest.approx(540)


class TestBboxPxToPt:
    """Tests for bbox_px_to_pt function."""

    def test_basic_conversion(self) -> None:
        """Test basic pixel to point conversion."""
        bbox = BBoxPx(x=100, y=50, w=400, h=100)
        fit = Fit(
            scale=0.5, offset_x_pt=10, offset_y_pt=20, placed_w_pt=800, placed_h_pt=450
        )
        x, y, w, h = bbox_px_to_pt(bbox, fit)
        assert x == pytest.approx(60)  # 10 + 100*0.5
        assert y == pytest.approx(45)  # 20 + 50*0.5
        assert w == pytest.approx(200)  # 400*0.5
        assert h == pytest.approx(50)  # 100*0.5

    def test_zero_offset(self) -> None:
        """Test conversion with zero offset."""
        bbox = BBoxPx(x=200, y=100, w=300, h=150)
        fit = Fit(scale=1.0, offset_x_pt=0, offset_y_pt=0, placed_w_pt=1600, placed_h_pt=900)
        x, y, w, h = bbox_px_to_pt(bbox, fit)
        assert x == pytest.approx(200)
        assert y == pytest.approx(100)
        assert w == pytest.approx(300)
        assert h == pytest.approx(150)

    def test_origin_bbox(self) -> None:
        """Test conversion of bbox at origin."""
        bbox = BBoxPx(x=0, y=0, w=100, h=100)
        fit = Fit(scale=0.5, offset_x_pt=50, offset_y_pt=50, placed_w_pt=400, placed_h_pt=400)
        x, y, w, h = bbox_px_to_pt(bbox, fit)
        assert x == pytest.approx(50)
        assert y == pytest.approx(50)
        assert w == pytest.approx(50)
        assert h == pytest.approx(50)
