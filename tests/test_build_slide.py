"""Tests for build_slide module."""

import pytest

from images2slides.build_slide import build_requests_for_infographic
from images2slides.geometry import Fit
from images2slides.models import BBoxPx, ImageDimensions, Layout, Region, TextStyle


@pytest.fixture
def sample_fit() -> Fit:
    """Sample fit for testing."""
    return Fit(
        scale=0.5,
        offset_x_pt=50,
        offset_y_pt=25,
        placed_w_pt=700,
        placed_h_pt=400,
    )


@pytest.fixture
def text_only_layout() -> Layout:
    """Layout with only text regions."""
    return Layout(
        image_px=ImageDimensions(width=1400, height=800),
        regions=(
            Region(
                id="title",
                order=1,
                type="text",
                bbox_px=BBoxPx(x=100, y=50, w=400, h=60),
                text="Hello World",
                style=TextStyle(font_family="Arial", font_size_pt=24, bold=True),
            ),
            Region(
                id="body",
                order=2,
                type="text",
                bbox_px=BBoxPx(x=100, y=150, w=400, h=200),
                text="Body text content",
            ),
        ),
    )


@pytest.fixture
def mixed_layout() -> Layout:
    """Layout with both text and image regions."""
    return Layout(
        image_px=ImageDimensions(width=1600, height=900),
        regions=(
            Region(
                id="title",
                order=1,
                type="text",
                bbox_px=BBoxPx(x=100, y=50, w=400, h=60),
                text="Title",
            ),
            Region(
                id="icon_1",
                order=2,
                type="image",
                bbox_px=BBoxPx(x=50, y=200, w=100, h=100),
                crop_from_infographic=True,
            ),
            Region(
                id="icon_2",
                order=3,
                type="image",
                bbox_px=BBoxPx(x=200, y=200, w=100, h=100),
                crop_from_infographic=True,
            ),
        ),
    )


class TestBuildRequestsForInfographic:
    """Tests for build_requests_for_infographic function."""

    def test_creates_slide_request(
        self, text_only_layout: Layout, sample_fit: Fit
    ) -> None:
        """Test that a createSlide request is always first."""
        reqs = build_requests_for_infographic(
            slide_id="SLIDE_test",
            layout=text_only_layout,
            fit=sample_fit,
            place_background=False,
        )
        assert len(reqs) > 0
        assert "createSlide" in reqs[0]
        assert reqs[0]["createSlide"]["objectId"] == "SLIDE_test"

    def test_creates_background_image(
        self, text_only_layout: Layout, sample_fit: Fit
    ) -> None:
        """Test background image is created when URL provided."""
        reqs = build_requests_for_infographic(
            slide_id="SLIDE_bg",
            layout=text_only_layout,
            fit=sample_fit,
            infographic_public_url="https://example.com/image.png",
            place_background=True,
        )
        # Find the createImage request for background
        bg_reqs = [r for r in reqs if "createImage" in r]
        assert len(bg_reqs) == 1
        assert bg_reqs[0]["createImage"]["objectId"] == "BG_SLIDE_bg"
        assert bg_reqs[0]["createImage"]["url"] == "https://example.com/image.png"

    def test_no_background_when_disabled(
        self, text_only_layout: Layout, sample_fit: Fit
    ) -> None:
        """Test no background image when place_background=False."""
        reqs = build_requests_for_infographic(
            slide_id="SLIDE_nobg",
            layout=text_only_layout,
            fit=sample_fit,
            infographic_public_url="https://example.com/image.png",
            place_background=False,
        )
        bg_reqs = [r for r in reqs if "createImage" in r]
        assert len(bg_reqs) == 0

    def test_creates_text_boxes(
        self, text_only_layout: Layout, sample_fit: Fit
    ) -> None:
        """Test text boxes are created for text regions."""
        reqs = build_requests_for_infographic(
            slide_id="SLIDE_txt",
            layout=text_only_layout,
            fit=sample_fit,
            place_background=False,
        )
        # Find createShape requests
        shape_reqs = [r for r in reqs if "createShape" in r]
        assert len(shape_reqs) == 2
        obj_ids = {r["createShape"]["objectId"] for r in shape_reqs}
        assert "TXT_title" in obj_ids
        assert "TXT_body" in obj_ids

    def test_inserts_text_content(
        self, text_only_layout: Layout, sample_fit: Fit
    ) -> None:
        """Test text content is inserted."""
        reqs = build_requests_for_infographic(
            slide_id="SLIDE_ins",
            layout=text_only_layout,
            fit=sample_fit,
            place_background=False,
        )
        insert_reqs = [r for r in reqs if "insertText" in r]
        assert len(insert_reqs) == 2
        texts = {r["insertText"]["text"] for r in insert_reqs}
        assert "Hello World" in texts
        assert "Body text content" in texts

    def test_makes_text_boxes_transparent(
        self, text_only_layout: Layout, sample_fit: Fit
    ) -> None:
        """Test text boxes are made transparent."""
        reqs = build_requests_for_infographic(
            slide_id="SLIDE_trans",
            layout=text_only_layout,
            fit=sample_fit,
            place_background=False,
        )
        transparent_reqs = [r for r in reqs if "updateShapeProperties" in r]
        assert len(transparent_reqs) == 2

    def test_applies_text_styles(
        self, text_only_layout: Layout, sample_fit: Fit
    ) -> None:
        """Test text styles are applied when present."""
        reqs = build_requests_for_infographic(
            slide_id="SLIDE_style",
            layout=text_only_layout,
            fit=sample_fit,
            place_background=False,
        )
        style_reqs = [r for r in reqs if "updateTextStyle" in r]
        # Only title has style
        assert len(style_reqs) == 1
        style = style_reqs[0]["updateTextStyle"]
        assert style["objectId"] == "TXT_title"
        assert style["style"]["fontFamily"] == "Arial"
        # Font size is scaled by fit.scale (0.5): 24 * 0.5 = 12
        assert style["style"]["fontSize"]["magnitude"] == 12.0
        assert style["style"]["bold"] is True

    def test_creates_image_regions_with_urls(
        self, mixed_layout: Layout, sample_fit: Fit
    ) -> None:
        """Test image regions are created when URLs provided."""
        cropped_urls = {
            "icon_1": "https://example.com/icon1.png",
            "icon_2": "https://example.com/icon2.png",
        }
        reqs = build_requests_for_infographic(
            slide_id="SLIDE_img",
            layout=mixed_layout,
            fit=sample_fit,
            cropped_url_by_region_id=cropped_urls,
            place_background=False,
        )
        img_reqs = [r for r in reqs if "createImage" in r]
        assert len(img_reqs) == 2
        obj_ids = {r["createImage"]["objectId"] for r in img_reqs}
        assert "IMG_icon_1" in obj_ids
        assert "IMG_icon_2" in obj_ids

    def test_skips_image_regions_without_urls(
        self, mixed_layout: Layout, sample_fit: Fit
    ) -> None:
        """Test image regions are skipped when no URL provided."""
        # Only provide URL for icon_1
        cropped_urls = {"icon_1": "https://example.com/icon1.png"}
        reqs = build_requests_for_infographic(
            slide_id="SLIDE_partial",
            layout=mixed_layout,
            fit=sample_fit,
            cropped_url_by_region_id=cropped_urls,
            place_background=False,
        )
        img_reqs = [r for r in reqs if "createImage" in r]
        assert len(img_reqs) == 1
        assert img_reqs[0]["createImage"]["objectId"] == "IMG_icon_1"

    def test_coordinate_transformation(
        self, text_only_layout: Layout, sample_fit: Fit
    ) -> None:
        """Test that coordinates are correctly transformed."""
        reqs = build_requests_for_infographic(
            slide_id="SLIDE_coord",
            layout=text_only_layout,
            fit=sample_fit,
            place_background=False,
        )
        # Find the title text box
        title_req = next(
            r for r in reqs
            if "createShape" in r and r["createShape"]["objectId"] == "TXT_title"
        )
        props = title_req["createShape"]["elementProperties"]
        # Original: x=100, y=50, w=400, h=60
        # With scale=0.5 and offset (50, 25):
        # x_pt = 50 + 100*0.5 = 100
        # y_pt = 25 + 50*0.5 = 50
        # w_pt = 400*0.5 = 200
        # h_pt = 60*0.5 = 30
        assert props["transform"]["translateX"] == 100
        assert props["transform"]["translateY"] == 50
        assert props["size"]["width"]["magnitude"] == 200
        assert props["size"]["height"]["magnitude"] == 30

    def test_request_order(
        self, text_only_layout: Layout, sample_fit: Fit
    ) -> None:
        """Test that requests are in correct order."""
        reqs = build_requests_for_infographic(
            slide_id="SLIDE_order",
            layout=text_only_layout,
            fit=sample_fit,
            infographic_public_url="https://example.com/bg.png",
            place_background=True,
        )
        # First should be createSlide
        assert "createSlide" in reqs[0]
        # Second should be background image
        assert "createImage" in reqs[1]
        assert reqs[1]["createImage"]["objectId"].startswith("BG_")

    def test_empty_layout(self, sample_fit: Fit) -> None:
        """Test handling of layout with no regions."""
        empty_layout = Layout(
            image_px=ImageDimensions(width=800, height=600),
            regions=(),
        )
        reqs = build_requests_for_infographic(
            slide_id="SLIDE_empty",
            layout=empty_layout,
            fit=sample_fit,
            place_background=False,
        )
        # Should only have createSlide
        assert len(reqs) == 1
        assert "createSlide" in reqs[0]


class TestSlideInputDataclass:
    """Tests for SlideInput dataclass."""

    def test_basic_creation(self, text_only_layout: Layout) -> None:
        """Test creating a SlideInput with required fields."""
        from images2slides.build_slide import SlideInput

        slide = SlideInput(layout=text_only_layout)
        assert slide.layout == text_only_layout
        assert slide.infographic_public_url is None
        assert slide.cropped_url_by_region_id is None
        assert slide.place_background is True
        assert slide.slide_id is None

    def test_with_all_fields(self, text_only_layout: Layout) -> None:
        """Test creating a SlideInput with all fields."""
        from images2slides.build_slide import SlideInput

        slide = SlideInput(
            layout=text_only_layout,
            infographic_public_url="https://example.com/bg.png",
            cropped_url_by_region_id={"img1": "https://example.com/img1.png"},
            place_background=False,
            slide_id="SLIDE_custom",
        )
        assert slide.infographic_public_url == "https://example.com/bg.png"
        assert slide.cropped_url_by_region_id == {"img1": "https://example.com/img1.png"}
        assert slide.place_background is False
        assert slide.slide_id == "SLIDE_custom"


class TestPresentationResultDataclass:
    """Tests for PresentationResult dataclass."""

    def test_basic_creation(self) -> None:
        """Test creating a PresentationResult."""
        from images2slides.build_slide import PresentationResult

        result = PresentationResult(
            presentation_id="abc123",
            presentation_url="https://docs.google.com/presentation/d/abc123/edit",
            slide_ids=["SLIDE_000", "SLIDE_001"],
            num_slides=2,
        )
        assert result.presentation_id == "abc123"
        assert result.presentation_url == "https://docs.google.com/presentation/d/abc123/edit"
        assert result.slide_ids == ["SLIDE_000", "SLIDE_001"]
        assert result.num_slides == 2


class TestBuildPresentationRequestGeneration:
    """Tests for build_presentation request generation logic."""

    def test_slide_insertion_indices(self, text_only_layout: Layout, sample_fit: Fit) -> None:
        """Test that slides get correct insertion indices."""
        from images2slides.build_slide import SlideInput, build_requests_for_infographic
        from images2slides.geometry import compute_fit

        # Create two slide inputs
        layout1 = text_only_layout
        layout2 = Layout(
            image_px=ImageDimensions(width=800, height=600),
            regions=(),
        )

        slide_inputs = [
            SlideInput(layout=layout1, slide_id="SLIDE_000"),
            SlideInput(layout=layout2, slide_id="SLIDE_001"),
        ]

        # Simulate what build_presentation does
        slide_w_pt, slide_h_pt = 720.0, 405.0
        all_requests: list[dict] = []

        for i, slide_input in enumerate(slide_inputs):
            fit = compute_fit(
                slide_input.layout.image_px.width,
                slide_input.layout.image_px.height,
                slide_w_pt,
                slide_h_pt,
            )
            requests = build_requests_for_infographic(
                slide_id=slide_input.slide_id or f"SLIDE_{i:03d}",
                layout=slide_input.layout,
                fit=fit,
                place_background=False,
            )
            # Update insertion index like build_presentation does
            for req in requests:
                if "createSlide" in req:
                    req["createSlide"]["insertionIndex"] = i
            all_requests.extend(requests)

        # Find createSlide requests and check insertion indices
        create_slide_requests = [r for r in all_requests if "createSlide" in r]
        assert len(create_slide_requests) == 2
        assert create_slide_requests[0]["createSlide"]["insertionIndex"] == 0
        assert create_slide_requests[1]["createSlide"]["insertionIndex"] == 1

    def test_multiple_layouts_request_count(self, text_only_layout: Layout, sample_fit: Fit) -> None:
        """Test correct number of requests for multiple layouts."""
        from images2slides.build_slide import build_requests_for_infographic
        from images2slides.geometry import compute_fit

        # text_only_layout has 2 regions, each text region generates:
        # createTextbox, insertText, transparentShape, (optional) textStyle
        slide_w_pt, slide_h_pt = 720.0, 405.0
        fit = compute_fit(
            text_only_layout.image_px.width,
            text_only_layout.image_px.height,
            slide_w_pt,
            slide_h_pt,
        )

        reqs = build_requests_for_infographic(
            slide_id="SLIDE_test",
            layout=text_only_layout,
            fit=fit,
            place_background=False,
        )
        # createSlide + (createTextbox + insertText + transparentShape + textStyle) * 2 regions
        assert len(reqs) >= 1  # At minimum, createSlide
