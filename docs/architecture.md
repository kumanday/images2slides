# System Architecture

This document describes the architecture of the slides_infographic system.

## Overview

The system converts static infographic images into editable Google Slides by:

1. Accepting a layout JSON describing detected regions
2. Transforming pixel coordinates to slide coordinates
3. Reconstructing elements via Google Slides API

## High-Level Data Flow

```
┌──────────────┐
│ Infographic  │
│   (PNG/JPG)  │
└──────┬───────┘
       │
       ▼
┌──────────────┐     ┌──────────────┐
│     VLM      │────▶│ layout.json  │
│  (external)  │     │              │
└──────────────┘     └──────┬───────┘
                            │
       ┌────────────────────┼────────────────────┐
       │                    ▼                    │
       │  ┌─────────────────────────────────┐   │
       │  │           validator.py          │   │
       │  │  • Schema validation            │   │
       │  │  • Type conversion              │   │
       │  │  • Bounds clamping              │   │
       │  └─────────────┬───────────────────┘   │
       │                │                        │
       │                ▼                        │
       │  ┌─────────────────────────────────┐   │
       │  │         postprocess.py          │   │
       │  │  • Whitespace trimming          │   │
       │  │  • Empty region removal         │   │
       │  │  • Reading order sort           │   │
       │  │  • Minimum size enforcement     │   │
       │  │  • Validation warnings          │   │
       │  └─────────────┬───────────────────┘   │
       │                │                        │
       │                ▼                        │
       │  ┌─────────────────────────────────┐   │
       │  │          geometry.py            │   │
       │  │  • Compute fit (scale, offset)  │   │
       │  │  • Transform bbox px → pt       │   │
       │  └─────────────┬───────────────────┘   │
       │                │                        │
       │                ▼                        │
       │  ┌─────────────────────────────────┐   │
       │  │          uploader.py            │   │
       │  │  • Crop image regions           │   │
       │  │  • Upload to GCS                │   │
       │  │  • Return public URLs           │   │
       │  └─────────────┬───────────────────┘   │
       │                │                        │
       │                ▼                        │
       │  ┌─────────────────────────────────┐   │
       │  │         slides_api.py           │   │
       │  │  • Build API request dicts      │   │
       │  │  • createSlide, createImage     │   │
       │  │  • createShape, insertText      │   │
       │  │  • updateShapeProperties        │   │
       │  └─────────────┬───────────────────┘   │
       │                │                        │
       │                ▼                        │
       │  ┌─────────────────────────────────┐   │
       │  │        build_slide.py           │   │
       │  │  • Orchestrate full build       │   │
       │  │  • Get page size                │   │
       │  │  • Execute batchUpdate          │   │
       │  └─────────────┬───────────────────┘   │
       │                │                        │
       │    slides_infographic package          │
       └────────────────┼────────────────────────┘
                        │
                        ▼
              ┌──────────────────┐
              │ Google Slides API│
              │   batchUpdate    │
              └────────┬─────────┘
                       │
                       ▼
              ┌──────────────────┐
              │  Editable Slide  │
              │  • Text boxes    │
              │  • Images        │
              └──────────────────┘
```

## Module Responsibilities

### Core Modules

#### `models.py`
Data structures for representing layouts:
- `BBoxPx` - Bounding box in pixel coordinates
- `TextStyle` - Font styling (family, size, bold)
- `Region` - A detected region (text or image)
- `Layout` - Complete layout with image dimensions and regions

All models are frozen dataclasses with JSON serialization methods.

#### `validator.py`
JSON schema validation:
- Validates required fields (image_px, regions, bbox_px)
- Converts raw dicts to typed dataclasses
- Applies default values for optional fields
- Clamps bounding boxes to image bounds

#### `geometry.py`
Coordinate transformation:
- `compute_fit()` - Calculate scale and offset for aspect-ratio-preserving fit
- `bbox_px_to_pt()` - Transform pixel coordinates to slide points

#### `postprocess.py`
VLM output cleanup:
- `trim_whitespace()` - Strip leading/trailing whitespace
- `normalize_spaces()` - Replace multiple spaces with single
- `drop_empty_regions()` - Remove empty text regions
- `clamp_to_bounds()` - Ensure boxes within image
- `sort_by_reading_order()` - Order by y then x
- `enforce_minimum_size()` - Expand tiny regions

Validation utilities:
- `compute_bbox_iou()` - Intersection over Union
- `find_overlapping_regions()` - Detect overlaps
- `validate_layout()` - Generate warnings
- `get_layout_statistics()` - Compute metrics

#### `uploader.py`
Image handling:
- `Uploader` protocol - Interface for upload backends
- `GCSUploader` - Google Cloud Storage implementation
- `crop_region_png()` - Crop region from source image
- `crop_and_upload_regions()` - Full crop/upload workflow

#### `slides_api.py`
Google Slides API request builders:
- `req_create_slide()` - Create blank slide
- `req_create_image()` - Place image on slide
- `req_create_textbox()` - Create text box shape
- `req_insert_text()` - Insert text content
- `req_transparent_shape()` - Make shape transparent
- `req_text_style()` - Apply font styling

#### `build_slide.py`
Orchestration:
- `get_page_size_pt()` - Fetch slide dimensions
- `build_requests_for_infographic()` - Generate all requests
- `apply_requests()` - Execute batchUpdate
- `build_slide()` - Full end-to-end build

#### `auth.py`
Google API authentication:
- `get_slides_service_oauth()` - OAuth 2.0 flow
- `get_slides_service_sa()` - Service account auth

### CLI Module

#### `cli/__main__.py`
Command-line interface:
- `build` - Build slide from layout
- `validate` - Validate layout file
- `postprocess` - Clean up layout file

## Key Design Decisions

### Frozen Dataclasses
All data models are immutable (`frozen=True`). This ensures:
- Thread safety
- Hashability for caching
- Clear data flow (transformations return new objects)

### Single batchUpdate
All Slides API operations are batched into a single `batchUpdate` call:
- Atomic: all succeed or all fail
- Efficient: one API call instead of many
- Idempotent: deterministic object IDs enable safe retries

### Deterministic Object IDs
Object IDs follow a predictable pattern:
- `SLIDE_<slug>` - Slide ID
- `TXT_<region_id>` - Text box ID
- `IMG_<region_id>` - Image ID
- `BG_<slide_id>` - Background image ID

This enables:
- Safe retries (same IDs = no duplicates)
- Easy debugging (predictable names)
- Traceability (map IDs to regions)

### Protocol-Based Uploader
The `Uploader` protocol allows swapping storage backends:
- `GCSUploader` - Google Cloud Storage
- Custom implementations for S3, local file server, etc.

### Separation of Concerns
Each module has a single responsibility:
- `validator.py` - Only validation, no business logic
- `geometry.py` - Only coordinate math
- `slides_api.py` - Only request building, no API calls
- `build_slide.py` - Only orchestration

## Error Handling

### Custom Exceptions
- `LayoutValidationError` - Invalid layout JSON
- `SlidesAPIError` - API call failures
- `UploadError` - Image upload failures

### Validation Warnings
Non-fatal issues are returned as `ValidationWarning` objects:
- `low_confidence` - Region confidence below threshold
- `has_notes` - Region has VLM notes
- `empty_text` - Text region without content
- `small_region` - Region area < 100 sq px
- `overlap` - Significant region overlap (IoU > threshold)

## Dependencies

### Runtime
- `google-api-python-client` - Slides API client
- `google-auth` / `google-auth-oauthlib` - Authentication
- `google-cloud-storage` - GCS uploads
- `pillow` - Image cropping
- `pydantic` - Data validation (optional)
- `click` - CLI framework

### Development
- `pytest` - Testing
- `black` - Formatting
- `ruff` - Linting
- `mypy` - Type checking
