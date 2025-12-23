"""Main orchestration for building slides from layouts."""

import logging
from dataclasses import dataclass
from typing import Any

from .geometry import Fit, bbox_px_to_pt, compute_fit
from .models import Layout
from .slides_api import (
    PAGE_SIZES,
    PageSizePreset,
    get_page_size_body,
    req_create_image,
    req_create_slide,
    req_create_textbox,
    req_delete_slide,
    req_insert_text,
    req_text_style,
    req_transparent_shape,
)

logger = logging.getLogger(__name__)


class SlidesAPIError(Exception):
    """Raised when Slides API call fails."""

    pass


def get_page_size_pt(service: Any, presentation_id: str) -> tuple[float, float]:
    """Fetch slide page size in points.

    Args:
        service: Google Slides API service.
        presentation_id: Presentation ID.

    Returns:
        Tuple of (width_pt, height_pt).

    Raises:
        SlidesAPIError: If API call fails or units unexpected.
    """
    try:
        pres = service.presentations().get(presentationId=presentation_id).execute()
        ps = pres["pageSize"]
        w = float(ps["width"]["magnitude"])
        h = float(ps["height"]["magnitude"])
        unit_w = ps["width"].get("unit", "PT")
        unit_h = ps["height"].get("unit", "PT")
        if unit_w != "PT" or unit_h != "PT":
            raise SlidesAPIError(f"Unexpected page units: {unit_w}, {unit_h}")
        return w, h
    except Exception as e:
        raise SlidesAPIError(f"Failed to get page size: {e}") from e


def build_requests_for_infographic(
    slide_id: str,
    layout: Layout,
    fit: Fit,
    infographic_public_url: str | None = None,
    cropped_url_by_region_id: dict[str, str] | None = None,
    place_background: bool = True,
) -> list[dict]:
    """Build all API requests for one infographic slide.

    Args:
        slide_id: Unique ID for the new slide.
        layout: Validated layout object.
        fit: Precomputed fit from compute_fit().
        infographic_public_url: URL for background image.
        cropped_url_by_region_id: Map of region ID to cropped image URL.
        place_background: Whether to place background image.

    Returns:
        List of Slides API request dicts.
    """
    reqs: list[dict] = []
    reqs.append(req_create_slide(slide_id))

    if place_background and infographic_public_url:
        reqs.append(
            req_create_image(
                obj_id=f"BG_{slide_id}",
                slide_id=slide_id,
                url=infographic_public_url,
                x_pt=fit.offset_x_pt,
                y_pt=fit.offset_y_pt,
                w_pt=fit.placed_w_pt,
                h_pt=fit.placed_h_pt,
            )
        )

    cropped_urls = cropped_url_by_region_id or {}

    for region in layout.regions:
        x_pt, y_pt, w_pt, h_pt = bbox_px_to_pt(region.bbox_px, fit)

        if region.type == "text":
            obj_id = f"TXT_{region.id}"
            reqs.append(req_create_textbox(obj_id, slide_id, x_pt, y_pt, w_pt, h_pt))
            reqs.append(req_insert_text(obj_id, region.text or ""))
            reqs.append(req_transparent_shape(obj_id))

            if region.style:
                # Scale font size proportionally to the image scaling
                # This ensures text fits properly when image is scaled to slide
                scaled_font_size = None
                if region.style.font_size_pt is not None:
                    scaled_font_size = region.style.font_size_pt * fit.scale

                style_req = req_text_style(
                    obj_id,
                    font_family=region.style.font_family,
                    font_size_pt=scaled_font_size,
                    bold=region.style.bold,
                )
                if style_req:
                    reqs.append(style_req)

        elif region.type == "image":
            if region.id not in cropped_urls:
                logger.warning(f"No cropped URL for image region: {region.id}")
                continue
            reqs.append(
                req_create_image(
                    obj_id=f"IMG_{region.id}",
                    slide_id=slide_id,
                    url=cropped_urls[region.id],
                    x_pt=x_pt,
                    y_pt=y_pt,
                    w_pt=w_pt,
                    h_pt=h_pt,
                )
            )

    return reqs


def apply_requests(service: Any, presentation_id: str, requests: list[dict]) -> dict:
    """Execute batch update with requests.

    Args:
        service: Google Slides API service.
        presentation_id: Presentation ID.
        requests: List of request dicts.

    Returns:
        API response dict.

    Raises:
        SlidesAPIError: If API call fails.
    """
    if not requests:
        return {}

    logger.info(f"Applying {len(requests)} requests to presentation {presentation_id}")

    try:
        from googleapiclient.errors import HttpError

        return (
            service.presentations()
            .batchUpdate(presentationId=presentation_id, body={"requests": requests})
            .execute()
        )
    except HttpError as e:
        if e.resp.status == 429:
            raise SlidesAPIError(f"Rate limited: {e}") from e
        raise SlidesAPIError(f"API error: {e}") from e
    except Exception as e:
        raise SlidesAPIError(f"Unexpected error: {e}") from e


def build_slide(
    service: Any,
    presentation_id: str,
    layout: Layout,
    slide_id: str,
    infographic_public_url: str | None = None,
    cropped_url_by_region_id: dict[str, str] | None = None,
    place_background: bool = True,
) -> dict:
    """Build a complete slide from a layout.

    Args:
        service: Google Slides API service.
        presentation_id: Presentation ID.
        layout: Validated layout object.
        slide_id: Unique ID for the new slide.
        infographic_public_url: URL for background image.
        cropped_url_by_region_id: Map of region ID to cropped image URL.
        place_background: Whether to place background image.

    Returns:
        API response dict.
    """
    logger.info(
        f"Building slide {slide_id}",
        extra={"presentation_id": presentation_id, "num_regions": len(layout.regions)},
    )

    slide_w_pt, slide_h_pt = get_page_size_pt(service, presentation_id)
    fit = compute_fit(
        layout.image_px.width, layout.image_px.height, slide_w_pt, slide_h_pt
    )

    requests = build_requests_for_infographic(
        slide_id=slide_id,
        layout=layout,
        fit=fit,
        infographic_public_url=infographic_public_url,
        cropped_url_by_region_id=cropped_url_by_region_id,
        place_background=place_background,
    )

    result = apply_requests(service, presentation_id, requests)
    logger.info(f"Slide {slide_id} created successfully")
    return result


@dataclass
class SlideInput:
    """Input for a single slide in a presentation."""

    layout: Layout
    infographic_public_url: str | None = None
    cropped_url_by_region_id: dict[str, str] | None = None
    place_background: bool = True
    slide_id: str | None = None


@dataclass
class PresentationResult:
    """Result of creating a presentation."""

    presentation_id: str
    presentation_url: str
    slide_ids: list[str]
    num_slides: int


def create_presentation(
    service: Any,
    title: str = "Untitled Presentation",
    page_size: PageSizePreset = "WIDESCREEN_16_9",
) -> tuple[str, float, float]:
    """Create a new Google Slides presentation.

    Args:
        service: Google Slides API service.
        title: Title for the new presentation.
        page_size: Page size preset.

    Returns:
        Tuple of (presentation_id, width_pt, height_pt).

    Raises:
        SlidesAPIError: If creation fails.
    """
    try:
        body = {
            "title": title,
            "pageSize": get_page_size_body(page_size),
        }
        presentation = service.presentations().create(body=body).execute()
        presentation_id = presentation["presentationId"]
        w_pt, h_pt = PAGE_SIZES[page_size]
        logger.info(f"Created presentation: {presentation_id} ({title})")
        return presentation_id, w_pt, h_pt
    except Exception as e:
        raise SlidesAPIError(f"Failed to create presentation: {e}") from e


def delete_initial_slide(service: Any, presentation_id: str) -> None:
    """Delete the initial blank slide from a new presentation.

    Args:
        service: Google Slides API service.
        presentation_id: Presentation ID.
    """
    try:
        pres = service.presentations().get(presentationId=presentation_id).execute()
        slides = pres.get("slides", [])
        if slides:
            initial_slide_id = slides[0]["objectId"]
            apply_requests(service, presentation_id, [req_delete_slide(initial_slide_id)])
            logger.debug(f"Deleted initial slide: {initial_slide_id}")
    except Exception as e:
        logger.warning(f"Could not delete initial slide: {e}")


def build_presentation(
    service: Any,
    slides: list[SlideInput],
    title: str = "Infographic Presentation",
    page_size: PageSizePreset = "WIDESCREEN_16_9",
    delete_initial: bool = True,
) -> PresentationResult:
    """Create a new presentation with multiple slides from layouts.

    Args:
        service: Google Slides API service.
        slides: List of SlideInput objects, one per slide.
        title: Title for the new presentation.
        page_size: Page size preset.
        delete_initial: Whether to delete the initial blank slide.

    Returns:
        PresentationResult with presentation info.

    Raises:
        SlidesAPIError: If creation fails.
    """
    if not slides:
        raise SlidesAPIError("No slides provided")

    # Create presentation
    presentation_id, slide_w_pt, slide_h_pt = create_presentation(
        service, title, page_size
    )

    # Delete initial blank slide if requested
    if delete_initial:
        delete_initial_slide(service, presentation_id)

    # Build all slides
    slide_ids: list[str] = []
    all_requests: list[dict] = []

    for i, slide_input in enumerate(slides):
        # Generate slide ID if not provided
        slide_id = slide_input.slide_id or f"SLIDE_{i:03d}"
        slide_ids.append(slide_id)

        # Compute fit for this layout
        fit = compute_fit(
            slide_input.layout.image_px.width,
            slide_input.layout.image_px.height,
            slide_w_pt,
            slide_h_pt,
        )

        # Build requests for this slide
        requests = build_requests_for_infographic(
            slide_id=slide_id,
            layout=slide_input.layout,
            fit=fit,
            infographic_public_url=slide_input.infographic_public_url,
            cropped_url_by_region_id=slide_input.cropped_url_by_region_id,
            place_background=slide_input.place_background,
        )

        # Update insertion index to append slides in order
        for req in requests:
            if "createSlide" in req:
                req["createSlide"]["insertionIndex"] = i

        all_requests.extend(requests)

    # Execute all requests in a single batch
    logger.info(f"Building {len(slides)} slides with {len(all_requests)} requests")
    apply_requests(service, presentation_id, all_requests)

    presentation_url = f"https://docs.google.com/presentation/d/{presentation_id}/edit"
    logger.info(f"Presentation created: {presentation_url}")

    return PresentationResult(
        presentation_id=presentation_id,
        presentation_url=presentation_url,
        slide_ids=slide_ids,
        num_slides=len(slides),
    )


def build_presentation_from_layouts(
    service: Any,
    layouts: list[Layout],
    infographic_urls: list[str] | None = None,
    title: str = "Infographic Presentation",
    page_size: PageSizePreset = "WIDESCREEN_16_9",
    place_backgrounds: bool = True,
) -> PresentationResult:
    """Convenience function to build presentation from list of layouts.

    Args:
        service: Google Slides API service.
        layouts: List of Layout objects, one per slide.
        infographic_urls: Optional list of public URLs for backgrounds.
        title: Title for the new presentation.
        page_size: Page size preset.
        place_backgrounds: Whether to place background images.

    Returns:
        PresentationResult with presentation info.
    """
    urls = infographic_urls or [None] * len(layouts)
    if len(urls) != len(layouts):
        raise SlidesAPIError(
            f"Number of URLs ({len(urls)}) must match number of layouts ({len(layouts)})"
        )

    slides = [
        SlideInput(
            layout=layout,
            infographic_public_url=url,
            place_background=place_backgrounds and url is not None,
        )
        for layout, url in zip(layouts, urls, strict=False)
    ]

    return build_presentation(service, slides, title, page_size)
