from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from images2slides.build_slide import PresentationResult, SlideInput, build_presentation
from images2slides.postprocess import postprocess_layout
from images2slides.vlm import VLMConfig, extract_layouts_from_images


@dataclass(frozen=True)
class PresentationInfo:
    presentation_id: str
    presentation_url: str


PAGE_SIZE_MAP: dict[str, str] = {
    "16:9": "WIDESCREEN_16_9",
    "16:10": "WIDESCREEN_16_10",
    "4:3": "STANDARD_4_3",
}


def extract_layouts(image_paths: list[Path], vlm_config: VLMConfig) -> list[Any]:
    return extract_layouts_from_images([str(p) for p in image_paths], config=vlm_config)


def postprocess(layouts: list[Any]) -> list[Any]:
    return [postprocess_layout(l) for l in layouts]


def upload_assets(layouts: list[Any], image_paths: list[Path]) -> list[dict[str, Any]]:
    # v0.1 local dev: no external hosting, so skip image-region insertion.
    # Returning empty URLs forces the upstream builder to skip image regions.
    _ = image_paths
    return [{"layout": layout, "cropped_url_by_region_id": {}} for layout in layouts]


def build_slides_presentation(
    service: Any,
    layouts_with_urls: list[dict[str, Any]],
    title: str,
    page_size: str,
) -> PresentationInfo:
    preset = PAGE_SIZE_MAP.get(page_size)
    if preset is None:
        raise ValueError(f"Unsupported page_size: {page_size}")

    slides = [
        SlideInput(
            layout=item["layout"],
            cropped_url_by_region_id=item.get("cropped_url_by_region_id"),
            place_background=False,
        )
        for item in layouts_with_urls
    ]

    result: PresentationResult = build_presentation(
        service=service,
        slides=slides,
        title=title,
        page_size=preset,
    )
    return PresentationInfo(presentation_id=result.presentation_id, presentation_url=result.presentation_url)
