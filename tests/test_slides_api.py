"""Tests for slides_api module."""


from images2slides.slides_api import (
    req_create_image,
    req_create_slide,
    req_create_textbox,
    req_insert_text,
    req_text_style,
    req_transparent_shape,
)


class TestReqCreateSlide:
    """Tests for req_create_slide function."""

    def test_basic_slide_creation(self) -> None:
        """Test basic slide creation request."""
        req = req_create_slide("SLIDE_test123")
        assert req["createSlide"]["objectId"] == "SLIDE_test123"
        assert req["createSlide"]["insertionIndex"] == 0
        assert req["createSlide"]["slideLayoutReference"]["predefinedLayout"] == "BLANK"

    def test_custom_insertion_index(self) -> None:
        """Test slide creation with custom insertion index."""
        req = req_create_slide("SLIDE_test", insertion_index=5)
        assert req["createSlide"]["insertionIndex"] == 5


class TestReqCreateImage:
    """Tests for req_create_image function."""

    def test_image_creation(self) -> None:
        """Test image creation request."""
        req = req_create_image(
            obj_id="IMG_test",
            slide_id="SLIDE_1",
            url="https://example.com/image.png",
            x_pt=10,
            y_pt=20,
            w_pt=100,
            h_pt=80,
        )
        assert req["createImage"]["objectId"] == "IMG_test"
        assert req["createImage"]["url"] == "https://example.com/image.png"
        props = req["createImage"]["elementProperties"]
        assert props["pageObjectId"] == "SLIDE_1"
        assert props["size"]["width"]["magnitude"] == 100
        assert props["size"]["height"]["magnitude"] == 80
        assert props["transform"]["translateX"] == 10
        assert props["transform"]["translateY"] == 20


class TestReqCreateTextbox:
    """Tests for req_create_textbox function."""

    def test_textbox_creation(self) -> None:
        """Test textbox creation request."""
        req = req_create_textbox(
            obj_id="TXT_title",
            slide_id="SLIDE_1",
            x_pt=50,
            y_pt=30,
            w_pt=400,
            h_pt=60,
        )
        assert req["createShape"]["objectId"] == "TXT_title"
        assert req["createShape"]["shapeType"] == "TEXT_BOX"
        props = req["createShape"]["elementProperties"]
        assert props["pageObjectId"] == "SLIDE_1"
        assert props["size"]["width"]["magnitude"] == 400
        assert props["size"]["height"]["magnitude"] == 60


class TestReqInsertText:
    """Tests for req_insert_text function."""

    def test_text_insertion(self) -> None:
        """Test text insertion request."""
        req = req_insert_text("TXT_title", "Hello World")
        assert req["insertText"]["objectId"] == "TXT_title"
        assert req["insertText"]["text"] == "Hello World"
        assert req["insertText"]["insertionIndex"] == 0


class TestReqTransparentShape:
    """Tests for req_transparent_shape function."""

    def test_transparent_shape(self) -> None:
        """Test transparent shape request."""
        req = req_transparent_shape("TXT_title")
        assert req["updateShapeProperties"]["objectId"] == "TXT_title"
        props = req["updateShapeProperties"]["shapeProperties"]
        assert props["shapeBackgroundFill"]["solidFill"]["alpha"] == 0
        assert props["outline"]["propertyState"] == "NOT_RENDERED"


class TestReqTextStyle:
    """Tests for req_text_style function."""

    def test_full_style(self) -> None:
        """Test text style with all options."""
        req = req_text_style("TXT_1", font_family="Arial", font_size_pt=24, bold=True)
        assert req is not None
        style = req["updateTextStyle"]
        assert style["objectId"] == "TXT_1"
        assert style["style"]["fontFamily"] == "Arial"
        assert style["style"]["fontSize"]["magnitude"] == 24
        assert style["style"]["bold"] is True
        assert "fontFamily" in style["fields"]
        assert "fontSize" in style["fields"]
        assert "bold" in style["fields"]

    def test_partial_style(self) -> None:
        """Test text style with partial options."""
        req = req_text_style("TXT_1", font_family="Roboto")
        assert req is not None
        assert req["updateTextStyle"]["style"]["fontFamily"] == "Roboto"
        assert "fontSize" not in req["updateTextStyle"]["style"]

    def test_empty_style(self) -> None:
        """Test text style with no options returns None."""
        req = req_text_style("TXT_1")
        assert req is None

    def test_bold_false(self) -> None:
        """Test text style with bold=False."""
        req = req_text_style("TXT_1", bold=False)
        assert req is not None
        assert req["updateTextStyle"]["style"]["bold"] is False


class TestReqDeleteSlide:
    """Tests for req_delete_slide function."""

    def test_delete_slide_request(self) -> None:
        """Test delete slide request structure."""
        from images2slides.slides_api import req_delete_slide

        req = req_delete_slide("SLIDE_abc123")
        assert "deleteObject" in req
        assert req["deleteObject"]["objectId"] == "SLIDE_abc123"


class TestGetPageSizeBody:
    """Tests for get_page_size_body function."""

    def test_widescreen_16_9(self) -> None:
        """Test 16:9 widescreen page size."""
        from images2slides.slides_api import get_page_size_body

        body = get_page_size_body("WIDESCREEN_16_9")
        assert body["width"]["magnitude"] == 720.0
        assert body["width"]["unit"] == "PT"
        assert body["height"]["magnitude"] == 405.0
        assert body["height"]["unit"] == "PT"

    def test_widescreen_16_10(self) -> None:
        """Test 16:10 widescreen page size."""
        from images2slides.slides_api import get_page_size_body

        body = get_page_size_body("WIDESCREEN_16_10")
        assert body["width"]["magnitude"] == 720.0
        assert body["height"]["magnitude"] == 450.0

    def test_standard_4_3(self) -> None:
        """Test 4:3 standard page size."""
        from images2slides.slides_api import get_page_size_body

        body = get_page_size_body("STANDARD_4_3")
        assert body["width"]["magnitude"] == 720.0
        assert body["height"]["magnitude"] == 540.0


class TestPageSizes:
    """Tests for PAGE_SIZES constant."""

    def test_page_sizes_contains_presets(self) -> None:
        """Test that PAGE_SIZES contains all presets."""
        from images2slides.slides_api import PAGE_SIZES

        assert "WIDESCREEN_16_9" in PAGE_SIZES
        assert "WIDESCREEN_16_10" in PAGE_SIZES
        assert "STANDARD_4_3" in PAGE_SIZES
        assert "CUSTOM" in PAGE_SIZES

    def test_page_sizes_correct_dimensions(self) -> None:
        """Test that PAGE_SIZES has correct dimension tuples."""
        from images2slides.slides_api import PAGE_SIZES

        # 16:9 ratio check
        w, h = PAGE_SIZES["WIDESCREEN_16_9"]
        assert abs(w / h - 16 / 9) < 0.01

        # 16:10 ratio check
        w, h = PAGE_SIZES["WIDESCREEN_16_10"]
        assert abs(w / h - 16 / 10) < 0.01

        # 4:3 ratio check
        w, h = PAGE_SIZES["STANDARD_4_3"]
        assert abs(w / h - 4 / 3) < 0.01
