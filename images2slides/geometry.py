"""Coordinate transforms from pixel space to slide points."""

from dataclasses import dataclass

from .models import BBoxPx


@dataclass(frozen=True)
class Fit:
    """Result of fitting an image onto a slide."""

    scale: float
    offset_x_pt: float
    offset_y_pt: float
    placed_w_pt: float
    placed_h_pt: float


def compute_fit(
    img_w_px: float, img_h_px: float, slide_w_pt: float, slide_h_pt: float
) -> Fit:
    """Compute scaling and offset to fit image on slide.

    Preserves aspect ratio and centers the image.

    Args:
        img_w_px: Image width in pixels.
        img_h_px: Image height in pixels.
        slide_w_pt: Slide width in points.
        slide_h_pt: Slide height in points.

    Returns:
        Fit object with scale, offsets, and placed dimensions.
    """
    scale = min(slide_w_pt / img_w_px, slide_h_pt / img_h_px)
    placed_w_pt = img_w_px * scale
    placed_h_pt = img_h_px * scale
    offset_x_pt = (slide_w_pt - placed_w_pt) / 2
    offset_y_pt = (slide_h_pt - placed_h_pt) / 2
    return Fit(
        scale=scale,
        offset_x_pt=offset_x_pt,
        offset_y_pt=offset_y_pt,
        placed_w_pt=placed_w_pt,
        placed_h_pt=placed_h_pt,
    )


def bbox_px_to_pt(bbox: BBoxPx, fit: Fit) -> tuple[float, float, float, float]:
    """Convert a bounding box from pixel coordinates to slide points.

    Args:
        bbox: Bounding box in pixel coordinates.
        fit: Fit object from compute_fit().

    Returns:
        Tuple of (x_pt, y_pt, w_pt, h_pt) in slide coordinates.
    """
    x_pt = fit.offset_x_pt + bbox.x * fit.scale
    y_pt = fit.offset_y_pt + bbox.y * fit.scale
    w_pt = bbox.w * fit.scale
    h_pt = bbox.h * fit.scale
    return x_pt, y_pt, w_pt, h_pt
