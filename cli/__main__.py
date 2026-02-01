"""CLI entry point for slides-infographic."""

import json
import logging
import os
import sys
from pathlib import Path

import click
from dotenv import load_dotenv


# Load .env file - search current directory and parent directories
def _load_env_file() -> None:
    """Load .env file from current directory or project root."""
    current = Path.cwd()

    # Check current directory first
    env_path = current / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=False)
        return

    # Walk up to find .env near pyproject.toml
    for parent in current.parents:
        if (parent / "pyproject.toml").exists():
            env_path = parent / ".env"
            if env_path.exists():
                load_dotenv(env_path, override=False)
            return


_load_env_file()

EXIT_SUCCESS = 0
EXIT_VALIDATION_ERROR = 1
EXIT_API_ERROR = 2
EXIT_MISSING_CREDENTIALS = 3
EXIT_VLM_ERROR = 4


def setup_logging(verbose: bool) -> None:
    """Configure logging based on verbosity."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


def get_default_provider() -> str:
    """Get default VLM provider from environment or fallback to google."""
    return os.environ.get("VLM_PROVIDER", "google")


def get_default_model() -> str | None:
    """Get default VLM model from environment."""
    return os.environ.get("VLM_MODEL")


@click.group()
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose output.")
def cli(verbose: bool) -> None:
    """Infographic to Google Slides conversion tool."""
    setup_logging(verbose)


@cli.command()
@click.option(
    "--presentation-id",
    required=True,
    envvar="PRESENTATION_ID",
    help="Google Slides presentation ID.",
)
@click.option(
    "--layout",
    required=True,
    type=click.Path(exists=True),
    help="Path to layout.json file.",
)
@click.option(
    "--infographic",
    required=True,
    type=click.Path(exists=True),
    help="Path to infographic image.",
)
@click.option(
    "--infographic-url",
    default=None,
    help="Public URL for infographic (for background).",
)
@click.option(
    "--slide-id",
    default=None,
    help="Custom slide ID (default: auto-generated).",
)
@click.option(
    "--place-background/--no-background",
    default=True,
    help="Place infographic as background.",
)
@click.option(
    "--client-secret",
    envvar="CLIENT_SECRET_PATH",
    type=click.Path(exists=True),
    help="Path to OAuth client secret JSON.",
)
@click.option(
    "--service-account",
    envvar="SERVICE_ACCOUNT_PATH",
    type=click.Path(exists=True),
    help="Path to service account JSON.",
)
def build(
    presentation_id: str,
    layout: str,
    infographic: str,
    infographic_url: str | None,
    slide_id: str | None,
    place_background: bool,
    client_secret: str | None,
    service_account: str | None,
) -> None:
    """Build a slide from layout.json."""
    import uuid

    from images2slides.auth import get_slides_service_oauth, get_slides_service_sa
    from images2slides.build_slide import SlidesAPIError, build_slide
    from images2slides.postprocess import postprocess_layout
    from images2slides.validator import LayoutValidationError, validate_layout

    logger = logging.getLogger(__name__)

    # Load and validate layout
    try:
        with open(layout, encoding="utf-8") as f:
            layout_data = json.load(f)
        validated_layout = validate_layout(layout_data)
        validated_layout = postprocess_layout(validated_layout)
        logger.info(f"Loaded layout with {len(validated_layout.regions)} regions")
    except LayoutValidationError as e:
        click.echo(f"Layout validation error: {e}", err=True)
        sys.exit(EXIT_VALIDATION_ERROR)
    except json.JSONDecodeError as e:
        click.echo(f"Invalid JSON in layout file: {e}", err=True)
        sys.exit(EXIT_VALIDATION_ERROR)

    # Get Slides service
    if service_account:
        service = get_slides_service_sa(service_account)
    elif client_secret:
        service = get_slides_service_oauth(client_secret)
    else:
        click.echo("Error: Must provide --client-secret or --service-account", err=True)
        sys.exit(EXIT_MISSING_CREDENTIALS)

    # Generate slide ID if not provided
    if not slide_id:
        slide_id = f"SLIDE_{uuid.uuid4().hex[:12]}"

    # Build the slide
    try:
        build_slide(
            service=service,
            presentation_id=presentation_id,
            layout=validated_layout,
            slide_id=slide_id,
            infographic_public_url=infographic_url,
            place_background=place_background,
        )
        click.echo(f"Created slide: {slide_id}")
        click.echo(f"Regions processed: {len(validated_layout.regions)}")
    except SlidesAPIError as e:
        click.echo(f"Slides API error: {e}", err=True)
        sys.exit(EXIT_API_ERROR)


@cli.command()
@click.option(
    "--layout",
    required=True,
    type=click.Path(exists=True),
    help="Path to layout.json file.",
)
def validate(layout: str) -> None:
    """Validate a layout.json file."""
    from images2slides.validator import LayoutValidationError, validate_layout

    try:
        with open(layout, encoding="utf-8") as f:
            layout_data = json.load(f)
        validated = validate_layout(layout_data)
        click.echo(f"Valid layout: {len(validated.regions)} regions")
        click.echo(f"Image size: {validated.image_px.width}x{validated.image_px.height}")

        text_count = sum(1 for r in validated.regions if r.type == "text")
        image_count = sum(1 for r in validated.regions if r.type == "image")
        click.echo(f"Text regions: {text_count}")
        click.echo(f"Image regions: {image_count}")

        sys.exit(EXIT_SUCCESS)
    except LayoutValidationError as e:
        click.echo(f"Validation error: {e}", err=True)
        sys.exit(EXIT_VALIDATION_ERROR)
    except json.JSONDecodeError as e:
        click.echo(f"Invalid JSON: {e}", err=True)
        sys.exit(EXIT_VALIDATION_ERROR)


@cli.command()
@click.option(
    "--layout",
    required=True,
    type=click.Path(exists=True),
    help="Path to layout.json file.",
)
@click.option(
    "--output",
    required=True,
    type=click.Path(),
    help="Output path for processed layout.",
)
def postprocess(layout: str, output: str) -> None:
    """Post-process a layout.json file."""

    from images2slides.postprocess import postprocess_layout
    from images2slides.validator import LayoutValidationError, validate_layout

    try:
        with open(layout, encoding="utf-8") as f:
            layout_data = json.load(f)
        validated = validate_layout(layout_data)
        processed = postprocess_layout(validated)

        # Convert back to dict for JSON output
        output_data = {
            "image_px": {
                "width": processed.image_px.width,
                "height": processed.image_px.height,
            },
            "regions": [
                {
                    "id": r.id,
                    "order": r.order,
                    "type": r.type,
                    "bbox_px": {
                        "x": r.bbox_px.x,
                        "y": r.bbox_px.y,
                        "w": r.bbox_px.w,
                        "h": r.bbox_px.h,
                    },
                    "text": r.text,
                    "style": (
                        {
                            "font_family": r.style.font_family,
                            "font_size_pt": r.style.font_size_pt,
                            "bold": r.style.bold,
                        }
                        if r.style
                        else None
                    ),
                    "crop_from_infographic": r.crop_from_infographic,
                    "confidence": r.confidence,
                    "notes": r.notes,
                }
                for r in processed.regions
            ],
        }

        with open(output, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2)

        click.echo(f"Processed layout saved to: {output}")
        click.echo(f"Regions: {len(processed.regions)}")
        sys.exit(EXIT_SUCCESS)
    except LayoutValidationError as e:
        click.echo(f"Validation error: {e}", err=True)
        sys.exit(EXIT_VALIDATION_ERROR)
    except json.JSONDecodeError as e:
        click.echo(f"Invalid JSON: {e}", err=True)
        sys.exit(EXIT_VALIDATION_ERROR)


@cli.command()
@click.option(
    "--layout",
    "layouts",
    required=True,
    multiple=True,
    type=click.Path(exists=True),
    help="Path to layout.json file (can be specified multiple times).",
)
@click.option(
    "--title",
    default="Infographic Presentation",
    help="Title for the new presentation.",
)
@click.option(
    "--page-size",
    type=click.Choice(["16:9", "16:10", "4:3"]),
    default="16:9",
    help="Slide aspect ratio.",
)
@click.option(
    "--infographic-url",
    "infographic_urls",
    multiple=True,
    help="Public URL for infographic background (one per layout, in order).",
)
@click.option(
    "--place-background/--no-background",
    default=True,
    help="Place infographic as background.",
)
@click.option(
    "--client-secret",
    envvar="CLIENT_SECRET_PATH",
    type=click.Path(exists=True),
    help="Path to OAuth client secret JSON.",
)
@click.option(
    "--service-account",
    envvar="SERVICE_ACCOUNT_PATH",
    type=click.Path(exists=True),
    help="Path to service account JSON.",
)
def create(
    layouts: tuple[str, ...],
    title: str,
    page_size: str,
    infographic_urls: tuple[str, ...],
    place_background: bool,
    client_secret: str | None,
    service_account: str | None,
) -> None:
    """Create a new presentation from multiple layout files.

    Example:
        slides-infographic create --layout slide1.json --layout slide2.json --title "My Deck"
    """
    from images2slides.auth import get_slides_service_oauth, get_slides_service_sa
    from images2slides.build_slide import (
        PresentationResult,
        SlideInput,
        SlidesAPIError,
        build_presentation,
    )
    from images2slides.postprocess import postprocess_layout
    from images2slides.validator import LayoutValidationError, validate_layout

    logger = logging.getLogger(__name__)

    # Map page size to preset
    page_size_map = {
        "16:9": "WIDESCREEN_16_9",
        "16:10": "WIDESCREEN_16_10",
        "4:3": "STANDARD_4_3",
    }
    page_size_preset = page_size_map[page_size]

    # Load and validate all layouts
    validated_layouts = []
    try:
        for layout_path in layouts:
            with open(layout_path, encoding="utf-8") as f:
                layout_data = json.load(f)
            validated = validate_layout(layout_data)
            validated = postprocess_layout(validated)
            validated_layouts.append(validated)
            logger.info(f"Loaded {layout_path}: {len(validated.regions)} regions")
    except LayoutValidationError as e:
        click.echo(f"Layout validation error: {e}", err=True)
        sys.exit(EXIT_VALIDATION_ERROR)
    except json.JSONDecodeError as e:
        click.echo(f"Invalid JSON: {e}", err=True)
        sys.exit(EXIT_VALIDATION_ERROR)

    # Prepare URLs (pad with None if fewer URLs than layouts)
    urls: list[str | None] = list(infographic_urls)
    while len(urls) < len(validated_layouts):
        urls.append(None)

    # Get Slides service
    if service_account:
        service = get_slides_service_sa(service_account)
    elif client_secret:
        service = get_slides_service_oauth(client_secret)
    else:
        click.echo("Error: Must provide --client-secret or --service-account", err=True)
        sys.exit(EXIT_MISSING_CREDENTIALS)

    # Build slide inputs
    slide_inputs = [
        SlideInput(
            layout=layout,
            infographic_public_url=url,
            place_background=place_background and url is not None,
        )
        for layout, url in zip(validated_layouts, urls, strict=False)
    ]

    # Create presentation
    try:
        result: PresentationResult = build_presentation(
            service=service,
            slides=slide_inputs,
            title=title,
            page_size=page_size_preset,
        )
        click.echo(f"Created presentation: {result.presentation_url}")
        click.echo(f"Presentation ID: {result.presentation_id}")
        click.echo(f"Slides created: {result.num_slides}")
    except SlidesAPIError as e:
        click.echo(f"Slides API error: {e}", err=True)
        sys.exit(EXIT_API_ERROR)


@cli.command()
@click.option(
    "--image",
    "images",
    required=True,
    multiple=True,
    type=click.Path(exists=True),
    help="Path to infographic image (can be specified multiple times).",
)
@click.option(
    "--output",
    type=click.Path(),
    help="Output directory for layout JSON files (default: same as image).",
)
@click.option(
    "--provider",
    type=click.Choice(["google", "openai", "anthropic", "openrouter"]),
    default=None,
    help="VLM provider (default: from VLM_PROVIDER env var or 'google').",
)
@click.option(
    "--model",
    default=None,
    help="Model name (default: from VLM_MODEL env var or provider default).",
)
def analyze(
    images: tuple[str, ...],
    output: str | None,
    provider: str | None,
    model: str | None,
) -> None:
    """Analyze infographic images and extract layout JSON.

    Uses a Vision-Language Model to analyze each image and extract
    text regions, image regions, and their bounding boxes.

    Example:
        slides-infographic analyze --image slide1.png --image slide2.png
    """

    from images2slides.vlm import VLMConfig, VLMExtractionError, extract_layout_from_image

    # Use CLI args, fall back to env vars, then defaults
    actual_provider = provider or get_default_provider()
    actual_model = model or get_default_model()

    config = VLMConfig(provider=actual_provider, model=actual_model)

    output_dir = Path(output) if output else None
    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)

    try:
        for image_path in images:
            image = Path(image_path)
            click.echo(f"Analyzing: {image.name}")

            layout = extract_layout_from_image(image, config)

            # Determine output path
            if output_dir:
                out_path = output_dir / f"{image.stem}_layout.json"
            else:
                out_path = image.parent / f"{image.stem}_layout.json"

            # Save layout JSON
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(layout.to_json())

            text_count = len(layout.text_regions)
            image_count = len(layout.image_regions)
            click.echo(f"  -> {out_path.name}: {text_count} text, {image_count} image regions")

        click.echo(f"\nAnalyzed {len(images)} image(s) successfully.")
        sys.exit(EXIT_SUCCESS)

    except VLMExtractionError as e:
        click.echo(f"VLM extraction error: {e}", err=True)
        sys.exit(EXIT_VLM_ERROR)


@cli.command()
@click.option(
    "--image",
    "images",
    required=True,
    multiple=True,
    type=click.Path(exists=True),
    help="Path to infographic image (can be specified multiple times, in order).",
)
@click.option(
    "--title",
    default="Infographic Presentation",
    help="Title for the new presentation.",
)
@click.option(
    "--page-size",
    type=click.Choice(["16:9", "16:10", "4:3"]),
    default="16:9",
    help="Slide aspect ratio.",
)
@click.option(
    "--provider",
    type=click.Choice(["google", "openai", "anthropic", "openrouter"]),
    default=None,
    help="VLM provider (default: from VLM_PROVIDER env var or 'google').",
)
@click.option(
    "--model",
    default=None,
    help="Model name (default: from VLM_MODEL env var or provider default).",
)
@click.option(
    "--save-layouts",
    type=click.Path(),
    default=None,
    help="Directory to save intermediate layout JSON files.",
)
@click.option(
    "--gcs-bucket",
    envvar="GCS_BUCKET",
    default=None,
    help="GCS bucket for uploading cropped image regions.",
)
@click.option(
    "--client-secret",
    envvar="CLIENT_SECRET_PATH",
    type=click.Path(exists=True),
    help="Path to OAuth client secret JSON for Google Slides.",
)
@click.option(
    "--service-account",
    envvar="SERVICE_ACCOUNT_PATH",
    type=click.Path(exists=True),
    help="Path to service account JSON for Google Slides.",
)
def convert(
    images: tuple[str, ...],
    title: str,
    page_size: str,
    provider: str | None,
    model: str | None,
    save_layouts: str | None,
    gcs_bucket: str | None,
    client_secret: str | None,
    service_account: str | None,
) -> None:
    """Convert infographic images to an editable Google Slides presentation.

    This is the main end-to-end pipeline:
    1. Analyzes each image using a Vision-Language Model
    2. Extracts text and image regions with bounding boxes
    3. Creates a new Google Slides presentation
    4. Builds editable slides from the extracted layouts

    Example:
        slides-infographic convert --image slide1.png --image slide2.png --title "My Deck"

    Configuration is read from .env file, environment variables, or CLI arguments.
    See .env.example for all available options.
    """

    from images2slides.auth import get_slides_service_oauth, get_slides_service_sa
    from images2slides.build_slide import (
        PresentationResult,
        SlideInput,
        SlidesAPIError,
        build_presentation,
    )
    from images2slides.postprocess import postprocess_layout
    from images2slides.vlm import VLMConfig, VLMExtractionError, extract_layout_from_image

    logger = logging.getLogger(__name__)

    # Map page size to preset
    page_size_map = {
        "16:9": "WIDESCREEN_16_9",
        "16:10": "WIDESCREEN_16_10",
        "4:3": "STANDARD_4_3",
    }
    page_size_preset = page_size_map[page_size]

    # VLM configuration - use CLI args, fall back to env vars, then defaults
    actual_provider = provider or get_default_provider()
    actual_model = model or get_default_model()
    vlm_config = VLMConfig(provider=actual_provider, model=actual_model)

    # Prepare layouts directory if saving
    layouts_dir = Path(save_layouts) if save_layouts else None
    if layouts_dir:
        layouts_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Analyze images with VLM
    click.echo(f"Step 1: Analyzing {len(images)} image(s) with {vlm_config.get_model()}...")
    layouts = []
    try:
        for i, image_path in enumerate(images):
            image = Path(image_path)
            click.echo(f"  [{i + 1}/{len(images)}] Analyzing: {image.name}")

            layout = extract_layout_from_image(image, vlm_config)
            layout = postprocess_layout(layout)
            layouts.append(layout)

            text_count = len(layout.text_regions)
            image_count = len(layout.image_regions)
            click.echo(f"         Found {text_count} text, {image_count} image regions")

            # Save layout if requested
            if layouts_dir:
                out_path = layouts_dir / f"{image.stem}_layout.json"
                with open(out_path, "w", encoding="utf-8") as f:
                    f.write(layout.to_json())
                logger.debug(f"Saved layout to {out_path}")

    except VLMExtractionError as e:
        click.echo(f"VLM extraction error: {e}", err=True)
        sys.exit(EXIT_VLM_ERROR)

    # Step 2: Crop and upload image regions (if GCS bucket provided)
    cropped_urls_per_image: list[dict[str, str]] = []
    total_image_regions = sum(len(layout.image_regions) for layout in layouts)

    if total_image_regions > 0:
        if gcs_bucket:
            click.echo(f"\nStep 2: Uploading {total_image_regions} image region(s) to GCS...")
            from images2slides.uploader import GCSUploader, UploadError, crop_and_upload_regions

            uploader = GCSUploader(gcs_bucket)
            try:
                for i, (image_path, layout) in enumerate(zip(images, layouts, strict=False)):
                    image = Path(image_path)
                    image_region_count = len(layout.image_regions)
                    if image_region_count > 0:
                        click.echo(
                            f"  [{i + 1}/{len(images)}] Cropping {image_region_count} regions from {image.name}"
                        )
                        cropped_urls = crop_and_upload_regions(
                            infographic_path=str(image),
                            layout=layout,
                            uploader=uploader,
                            prefix=f"{image.stem}_",
                        )
                        cropped_urls_per_image.append(cropped_urls)
                    else:
                        cropped_urls_per_image.append({})
            except UploadError as e:
                click.echo(f"Image upload error: {e}", err=True)
                sys.exit(EXIT_API_ERROR)
        else:
            click.echo(
                f"\nNote: {total_image_regions} image region(s) detected but --gcs-bucket not provided."
            )
            click.echo(
                "      Image regions will be skipped. Set GCS_BUCKET in .env or use --gcs-bucket."
            )
            cropped_urls_per_image = [{} for _ in layouts]
    else:
        cropped_urls_per_image = [{} for _ in layouts]

    # Step 3: Get Slides service
    click.echo("\nStep 3: Connecting to Google Slides API...")
    if service_account:
        service = get_slides_service_sa(service_account)
    elif client_secret:
        service = get_slides_service_oauth(client_secret)
    else:
        click.echo("Error: Must provide --client-secret or --service-account", err=True)
        sys.exit(EXIT_MISSING_CREDENTIALS)

    # Step 4: Build presentation
    click.echo(f"\nStep 4: Creating presentation '{title}'...")
    slide_inputs = [
        SlideInput(
            layout=layout,
            cropped_url_by_region_id=cropped_urls,
            place_background=False,
        )
        for layout, cropped_urls in zip(layouts, cropped_urls_per_image, strict=False)
    ]

    try:
        result: PresentationResult = build_presentation(
            service=service,
            slides=slide_inputs,
            title=title,
            page_size=page_size_preset,
        )

        click.echo("\n" + "=" * 60)
        click.echo("SUCCESS!")
        click.echo("=" * 60)
        click.echo(f"Presentation URL: {result.presentation_url}")
        click.echo(f"Presentation ID:  {result.presentation_id}")
        click.echo(f"Slides created:   {result.num_slides}")
        if layouts_dir:
            click.echo(f"Layouts saved to: {layouts_dir}")

    except SlidesAPIError as e:
        click.echo(f"Slides API error: {e}", err=True)
        sys.exit(EXIT_API_ERROR)


if __name__ == "__main__":
    cli()
