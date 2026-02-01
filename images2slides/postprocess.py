"""Post-processing utilities for VLM-extracted layouts."""

import logging
import re
from dataclasses import dataclass

from .models import BBoxPx, Layout, Region
from .validator import clamp_bbox_to_bounds

logger = logging.getLogger(__name__)


def trim_whitespace(layout: Layout) -> Layout:
    """Trim leading/trailing whitespace from all text regions.

    Args:
        layout: Input layout.

    Returns:
        Layout with trimmed text.
    """
    new_regions = []
    for r in layout.regions:
        if r.type == "text" and r.text:
            new_regions.append(
                Region(
                    id=r.id,
                    order=r.order,
                    type=r.type,
                    bbox_px=r.bbox_px,
                    text=r.text.strip(),
                    style=r.style,
                    crop_from_infographic=r.crop_from_infographic,
                    confidence=r.confidence,
                    notes=r.notes,
                )
            )
        else:
            new_regions.append(r)
    return Layout(image_px=layout.image_px, regions=tuple(new_regions))


def normalize_spaces(layout: Layout) -> Layout:
    """Replace multiple spaces with single space in text regions.

    Args:
        layout: Input layout.

    Returns:
        Layout with normalized spaces.
    """
    new_regions = []
    for r in layout.regions:
        if r.type == "text" and r.text:
            normalized = re.sub(r" +", " ", r.text)
            new_regions.append(
                Region(
                    id=r.id,
                    order=r.order,
                    type=r.type,
                    bbox_px=r.bbox_px,
                    text=normalized,
                    style=r.style,
                    crop_from_infographic=r.crop_from_infographic,
                    confidence=r.confidence,
                    notes=r.notes,
                )
            )
        else:
            new_regions.append(r)
    return Layout(image_px=layout.image_px, regions=tuple(new_regions))


def drop_empty_regions(layout: Layout) -> Layout:
    """Remove text regions with empty or whitespace-only text.

    Args:
        layout: Input layout.

    Returns:
        Layout without empty text regions.
    """
    new_regions = []
    for r in layout.regions:
        if r.type == "text":
            if r.text and r.text.strip():
                new_regions.append(r)
        else:
            new_regions.append(r)
    return Layout(image_px=layout.image_px, regions=tuple(new_regions))


def clamp_to_bounds(layout: Layout) -> Layout:
    """Ensure all bounding boxes are within image bounds.

    Args:
        layout: Input layout.

    Returns:
        Layout with clamped bounding boxes.
    """
    width = layout.image_px.width
    height = layout.image_px.height
    new_regions = []
    for r in layout.regions:
        clamped_bbox = clamp_bbox_to_bounds(r.bbox_px, width, height)
        new_regions.append(
            Region(
                id=r.id,
                order=r.order,
                type=r.type,
                bbox_px=clamped_bbox,
                text=r.text,
                style=r.style,
                crop_from_infographic=r.crop_from_infographic,
                confidence=r.confidence,
                notes=r.notes,
            )
        )
    return Layout(image_px=layout.image_px, regions=tuple(new_regions))


def sort_by_reading_order(layout: Layout) -> Layout:
    """Sort regions by reading order (order field, then y, then x).

    Args:
        layout: Input layout.

    Returns:
        Layout with sorted regions.
    """
    sorted_regions = sorted(layout.regions, key=lambda r: (r.order, r.bbox_px.y, r.bbox_px.x))
    return Layout(image_px=layout.image_px, regions=tuple(sorted_regions))


def enforce_minimum_size(layout: Layout, min_w: float = 10.0, min_h: float = 10.0) -> Layout:
    """Expand regions smaller than minimum size.

    Args:
        layout: Input layout.
        min_w: Minimum width in pixels.
        min_h: Minimum height in pixels.

    Returns:
        Layout with enforced minimum sizes.
    """
    new_regions = []
    for r in layout.regions:
        w = max(r.bbox_px.w, min_w)
        h = max(r.bbox_px.h, min_h)
        if w != r.bbox_px.w or h != r.bbox_px.h:
            new_bbox = BBoxPx(x=r.bbox_px.x, y=r.bbox_px.y, w=w, h=h)
            new_regions.append(
                Region(
                    id=r.id,
                    order=r.order,
                    type=r.type,
                    bbox_px=new_bbox,
                    text=r.text,
                    style=r.style,
                    crop_from_infographic=r.crop_from_infographic,
                    confidence=r.confidence,
                    notes=r.notes,
                )
            )
        else:
            new_regions.append(r)
    return Layout(image_px=layout.image_px, regions=tuple(new_regions))


def postprocess_layout(layout: Layout) -> Layout:
    """Apply all standard post-processing steps.

    Args:
        layout: Input layout.

    Returns:
        Fully post-processed layout.
    """
    layout = trim_whitespace(layout)
    layout = normalize_spaces(layout)
    layout = drop_empty_regions(layout)
    layout = clamp_to_bounds(layout)
    layout = sort_by_reading_order(layout)
    layout = enforce_minimum_size(layout)
    return layout


# --- Validation and Analysis Utilities ---


@dataclass
class ValidationWarning:
    """A warning about a potential issue in the layout."""

    region_id: str
    warning_type: str
    message: str
    severity: str = "warning"  # "warning" or "info"


@dataclass
class OverlapInfo:
    """Information about overlapping regions."""

    region_a_id: str
    region_b_id: str
    iou: float
    overlap_area: float


def compute_bbox_iou(a: BBoxPx, b: BBoxPx) -> float:
    """Compute Intersection over Union (IoU) of two bounding boxes.

    Args:
        a: First bounding box.
        b: Second bounding box.

    Returns:
        IoU value between 0 and 1.
    """
    # Compute intersection
    x1 = max(a.x, b.x)
    y1 = max(a.y, b.y)
    x2 = min(a.x + a.w, b.x + b.w)
    y2 = min(a.y + a.h, b.y + b.h)

    if x2 <= x1 or y2 <= y1:
        return 0.0

    intersection = (x2 - x1) * (y2 - y1)
    area_a = a.w * a.h
    area_b = b.w * b.h
    union = area_a + area_b - intersection

    if union <= 0:
        return 0.0

    return intersection / union


def compute_overlap_area(a: BBoxPx, b: BBoxPx) -> float:
    """Compute the overlapping area of two bounding boxes.

    Args:
        a: First bounding box.
        b: Second bounding box.

    Returns:
        Overlap area in square pixels.
    """
    x1 = max(a.x, b.x)
    y1 = max(a.y, b.y)
    x2 = min(a.x + a.w, b.x + b.w)
    y2 = min(a.y + a.h, b.y + b.h)

    if x2 <= x1 or y2 <= y1:
        return 0.0

    return (x2 - x1) * (y2 - y1)


def find_overlapping_regions(layout: Layout, iou_threshold: float = 0.3) -> list[OverlapInfo]:
    """Find pairs of regions with significant overlap.

    Args:
        layout: Layout to analyze.
        iou_threshold: Minimum IoU to consider as overlapping.

    Returns:
        List of OverlapInfo for overlapping region pairs.
    """
    overlaps: list[OverlapInfo] = []
    regions = layout.regions

    for i in range(len(regions)):
        for j in range(i + 1, len(regions)):
            a = regions[i]
            b = regions[j]
            iou = compute_bbox_iou(a.bbox_px, b.bbox_px)
            if iou >= iou_threshold:
                overlap_area = compute_overlap_area(a.bbox_px, b.bbox_px)
                overlaps.append(
                    OverlapInfo(
                        region_a_id=a.id,
                        region_b_id=b.id,
                        iou=iou,
                        overlap_area=overlap_area,
                    )
                )

    return overlaps


def validate_layout(
    layout: Layout,
    confidence_threshold: float = 0.7,
    iou_threshold: float = 0.3,
) -> list[ValidationWarning]:
    """Validate a layout and return warnings about potential issues.

    Args:
        layout: Layout to validate.
        confidence_threshold: Minimum confidence before warning.
        iou_threshold: Minimum IoU to warn about overlaps.

    Returns:
        List of ValidationWarning objects.
    """
    warnings: list[ValidationWarning] = []

    # Check for low confidence regions
    for region in layout.regions:
        if region.confidence < confidence_threshold:
            warnings.append(
                ValidationWarning(
                    region_id=region.id,
                    warning_type="low_confidence",
                    message=f"Region has low confidence: {region.confidence:.2f}",
                    severity="warning",
                )
            )

        # Check for regions with notes (may need attention)
        if region.notes:
            warnings.append(
                ValidationWarning(
                    region_id=region.id,
                    warning_type="has_notes",
                    message=f"Region has notes: {region.notes}",
                    severity="info",
                )
            )

        # Check for text regions without text
        if region.type == "text" and not region.text:
            warnings.append(
                ValidationWarning(
                    region_id=region.id,
                    warning_type="empty_text",
                    message="Text region has no text content",
                    severity="warning",
                )
            )

        # Check for very small regions
        if region.bbox_px.area < 100:
            warnings.append(
                ValidationWarning(
                    region_id=region.id,
                    warning_type="small_region",
                    message=f"Region is very small: {region.bbox_px.area:.0f} sq px",
                    severity="info",
                )
            )

    # Check for overlapping regions
    overlaps = find_overlapping_regions(layout, iou_threshold)
    for overlap in overlaps:
        warnings.append(
            ValidationWarning(
                region_id=f"{overlap.region_a_id},{overlap.region_b_id}",
                warning_type="overlap",
                message=f"Regions overlap with IoU={overlap.iou:.2f}",
                severity="warning",
            )
        )

    return warnings


def log_validation_warnings(warnings: list[ValidationWarning]) -> None:
    """Log validation warnings using the module logger.

    Args:
        warnings: List of warnings to log.
    """
    for w in warnings:
        if w.severity == "warning":
            logger.warning(f"[{w.warning_type}] {w.region_id}: {w.message}")
        else:
            logger.info(f"[{w.warning_type}] {w.region_id}: {w.message}")


def get_layout_statistics(layout: Layout) -> dict:
    """Compute statistics about a layout.

    Args:
        layout: Layout to analyze.

    Returns:
        Dictionary of statistics.
    """
    text_regions = [r for r in layout.regions if r.type == "text"]
    image_regions = [r for r in layout.regions if r.type == "image"]

    confidences = [r.confidence for r in layout.regions]
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0

    areas = [r.bbox_px.area for r in layout.regions]
    total_area = sum(areas)
    image_area = layout.image_px.width * layout.image_px.height
    coverage = total_area / image_area if image_area > 0 else 0

    return {
        "total_regions": len(layout.regions),
        "text_regions": len(text_regions),
        "image_regions": len(image_regions),
        "avg_confidence": avg_confidence,
        "min_confidence": min(confidences) if confidences else 0,
        "max_confidence": max(confidences) if confidences else 0,
        "total_text_chars": sum(len(r.text or "") for r in text_regions),
        "coverage_ratio": coverage,
        "image_width": layout.image_px.width,
        "image_height": layout.image_px.height,
    }
