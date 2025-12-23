"""JSON schema validation for layout.json files."""

from .models import BBoxPx, ImageDimensions, Layout, Region, TextStyle


class LayoutValidationError(Exception):
    """Raised when layout.json fails validation."""

    pass


def _validate_bbox(data: dict, field_name: str) -> BBoxPx:
    """Validate and parse a bounding box."""
    required = ["x", "y", "w", "h"]
    for key in required:
        if key not in data:
            raise LayoutValidationError(f"{field_name} missing required field: {key}")
        if not isinstance(data[key], (int, float)):
            raise LayoutValidationError(f"{field_name}.{key} must be a number")

    return BBoxPx(x=float(data["x"]), y=float(data["y"]), w=float(data["w"]), h=float(data["h"]))


def _validate_style(data: dict | None) -> TextStyle | None:
    """Validate and parse text style."""
    if data is None:
        return None
    return TextStyle(
        font_family=data.get("font_family"),
        font_size_pt=data.get("font_size_pt"),
        bold=data.get("bold"),
    )


def _validate_region(data: dict, index: int) -> Region:
    """Validate and parse a single region."""
    prefix = f"regions[{index}]"

    if "id" not in data:
        raise LayoutValidationError(f"{prefix} missing 'id'")
    if "type" not in data:
        raise LayoutValidationError(f"{prefix} missing 'type'")
    if data["type"] not in ("text", "image"):
        raise LayoutValidationError(f"{prefix}.type must be 'text' or 'image'")
    if "bbox_px" not in data:
        raise LayoutValidationError(f"{prefix} missing 'bbox_px'")

    bbox = _validate_bbox(data["bbox_px"], f"{prefix}.bbox_px")
    style = _validate_style(data.get("style"))

    return Region(
        id=str(data["id"]),
        order=int(data.get("order", index + 1)),
        type=data["type"],
        bbox_px=bbox,
        text=data.get("text"),
        style=style,
        crop_from_infographic=bool(data.get("crop_from_infographic", False)),
        confidence=float(data.get("confidence", 1.0)),
        notes=data.get("notes"),
    )


def validate_layout(data: dict) -> Layout:
    """Validate and parse a layout.json dictionary.

    Args:
        data: Raw dictionary from JSON parsing.

    Returns:
        Validated Layout object.

    Raises:
        LayoutValidationError: If validation fails.
    """
    if "image_px" not in data:
        raise LayoutValidationError("Missing 'image_px' field")
    if "regions" not in data:
        raise LayoutValidationError("Missing 'regions' field")

    image_px_data = data["image_px"]
    if "width" not in image_px_data or "height" not in image_px_data:
        raise LayoutValidationError("image_px must have 'width' and 'height'")

    image_px = ImageDimensions(
        width=int(image_px_data["width"]), height=int(image_px_data["height"])
    )

    regions_data = data["regions"]
    if not isinstance(regions_data, list):
        raise LayoutValidationError("'regions' must be a list")

    regions = tuple(_validate_region(r, i) for i, r in enumerate(regions_data))

    return Layout(image_px=image_px, regions=regions)


def clamp_bbox_to_bounds(bbox: BBoxPx, width: int, height: int) -> BBoxPx:
    """Clamp a bounding box to stay within image bounds.

    Args:
        bbox: Original bounding box.
        width: Image width in pixels.
        height: Image height in pixels.

    Returns:
        Clamped bounding box.
    """
    x = max(0, min(bbox.x, width))
    y = max(0, min(bbox.y, height))
    w = min(bbox.w, width - x)
    h = min(bbox.h, height - y)
    return BBoxPx(x=x, y=y, w=max(0, w), h=max(0, h))
