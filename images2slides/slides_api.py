"""Google Slides API request builders."""

from typing import Literal

# Standard Google Slides page sizes in points
PAGE_SIZES = {
    "WIDESCREEN_16_9": (720.0, 405.0),
    "WIDESCREEN_16_10": (720.0, 450.0),
    "STANDARD_4_3": (720.0, 540.0),
    "CUSTOM": None,
}

PageSizePreset = Literal["WIDESCREEN_16_9", "WIDESCREEN_16_10", "STANDARD_4_3"]


def _element_props(
    page_object_id: str, x_pt: float, y_pt: float, w_pt: float, h_pt: float
) -> dict:
    """Build element properties with size and transform.

    Args:
        page_object_id: The slide/page object ID.
        x_pt: X position in points.
        y_pt: Y position in points.
        w_pt: Width in points.
        h_pt: Height in points.

    Returns:
        Element properties dict for Slides API.
    """
    return {
        "pageObjectId": page_object_id,
        "size": {
            "width": {"magnitude": float(w_pt), "unit": "PT"},
            "height": {"magnitude": float(h_pt), "unit": "PT"},
        },
        "transform": {
            "scaleX": 1,
            "scaleY": 1,
            "shearX": 0,
            "shearY": 0,
            "translateX": float(x_pt),
            "translateY": float(y_pt),
            "unit": "PT",
        },
    }


def req_create_slide(slide_id: str, insertion_index: int = 0) -> dict:
    """Create a blank slide request.

    Args:
        slide_id: Unique identifier for the new slide.
        insertion_index: Position to insert the slide.

    Returns:
        createSlide request dict.
    """
    return {
        "createSlide": {
            "objectId": slide_id,
            "insertionIndex": insertion_index,
            "slideLayoutReference": {"predefinedLayout": "BLANK"},
        }
    }


def req_create_image(
    obj_id: str, slide_id: str, url: str, x_pt: float, y_pt: float, w_pt: float, h_pt: float
) -> dict:
    """Create an image placement request.

    Args:
        obj_id: Unique identifier for the image object.
        slide_id: Slide to place the image on.
        url: Public URL of the image.
        x_pt: X position in points.
        y_pt: Y position in points.
        w_pt: Width in points.
        h_pt: Height in points.

    Returns:
        createImage request dict.
    """
    return {
        "createImage": {
            "objectId": obj_id,
            "url": url,
            "elementProperties": _element_props(slide_id, x_pt, y_pt, w_pt, h_pt),
        }
    }


def req_create_textbox(
    obj_id: str, slide_id: str, x_pt: float, y_pt: float, w_pt: float, h_pt: float
) -> dict:
    """Create a text box request.

    Args:
        obj_id: Unique identifier for the text box.
        slide_id: Slide to place the text box on.
        x_pt: X position in points.
        y_pt: Y position in points.
        w_pt: Width in points.
        h_pt: Height in points.

    Returns:
        createShape request dict for TEXT_BOX.
    """
    return {
        "createShape": {
            "objectId": obj_id,
            "shapeType": "TEXT_BOX",
            "elementProperties": _element_props(slide_id, x_pt, y_pt, w_pt, h_pt),
        }
    }


def req_insert_text(obj_id: str, text: str) -> dict:
    """Create a text insertion request.

    Args:
        obj_id: Text box object ID.
        text: Text content to insert.

    Returns:
        insertText request dict.
    """
    return {"insertText": {"objectId": obj_id, "insertionIndex": 0, "text": text}}


def req_transparent_shape(obj_id: str) -> dict:
    """Make a shape transparent (no fill, no outline).

    Args:
        obj_id: Shape object ID.

    Returns:
        updateShapeProperties request dict.
    """
    return {
        "updateShapeProperties": {
            "objectId": obj_id,
            "shapeProperties": {
                "shapeBackgroundFill": {"solidFill": {"alpha": 0}},
                "outline": {"propertyState": "NOT_RENDERED"},
            },
            "fields": "shapeBackgroundFill.solidFill.alpha,outline.propertyState",
        }
    }


def req_text_style(
    obj_id: str,
    font_family: str | None = None,
    font_size_pt: float | None = None,
    bold: bool | None = None,
) -> dict | None:
    """Create a text style update request.

    Args:
        obj_id: Text box object ID.
        font_family: Font family name.
        font_size_pt: Font size in points.
        bold: Whether text is bold.

    Returns:
        updateTextStyle request dict, or None if no styles specified.
    """
    style: dict = {}
    fields: list[str] = []

    if font_family:
        style["fontFamily"] = font_family
        fields.append("fontFamily")
    if font_size_pt is not None:
        style["fontSize"] = {"magnitude": float(font_size_pt), "unit": "PT"}
        fields.append("fontSize")
    if bold is not None:
        style["bold"] = bool(bold)
        fields.append("bold")

    if not style:
        return None

    return {
        "updateTextStyle": {
            "objectId": obj_id,
            "textRange": {"type": "ALL"},
            "style": style,
            "fields": ",".join(fields),
        }
    }


def req_delete_slide(slide_id: str) -> dict:
    """Create a delete slide request.

    Args:
        slide_id: ID of the slide to delete.

    Returns:
        deleteObject request dict.
    """
    return {"deleteObject": {"objectId": slide_id}}


def get_page_size_body(
    preset: PageSizePreset = "WIDESCREEN_16_9",
) -> dict:
    """Get page size specification for presentation creation.

    Args:
        preset: Page size preset name.

    Returns:
        Page size dict for API.
    """
    w_pt, h_pt = PAGE_SIZES[preset]
    return {
        "width": {"magnitude": w_pt, "unit": "PT"},
        "height": {"magnitude": h_pt, "unit": "PT"},
    }
