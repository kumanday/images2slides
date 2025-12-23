# API Reference

Complete reference for all public modules, classes, and functions.

## models

Data models for representing infographic layouts.

### BBoxPx

Bounding box in pixel coordinates.

```python
@dataclass(frozen=True)
class BBoxPx:
    x: float      # Left edge X coordinate
    y: float      # Top edge Y coordinate
    w: float      # Width
    h: float      # Height
```

**Properties:**
- `area` -> `float`: Area in square pixels (w * h)
- `center` -> `tuple[float, float]`: Center point (cx, cy)

**Methods:**
- `to_dict()` -> `dict`: Convert to dictionary
- `from_dict(data: dict)` -> `BBoxPx`: Create from dictionary

---

### TextStyle

Text styling hints for a region.

```python
@dataclass(frozen=True)
class TextStyle:
    font_family: str | None = None     # e.g., "Arial"
    font_size_pt: float | None = None  # Font size in points
    bold: bool | None = None           # Bold flag
```

**Methods:**
- `to_dict()` -> `dict`: Convert to dictionary
- `from_dict(data: dict | None)` -> `TextStyle | None`: Create from dictionary

---

### Region

A detected region in the infographic.

```python
@dataclass(frozen=True)
class Region:
    id: str                              # Unique identifier
    order: int                           # Reading order (1-based)
    type: Literal["text", "image"]       # Region type
    bbox_px: BBoxPx                      # Bounding box
    text: str | None = None              # Text content (for text regions)
    style: TextStyle | None = None       # Text styling
    crop_from_infographic: bool = False  # Whether to crop from source
    confidence: float = 1.0              # VLM confidence (0-1)
    notes: str | None = None             # VLM notes
```

**Properties:**
- `is_text` -> `bool`: True if type == "text"
- `is_image` -> `bool`: True if type == "image"

**Methods:**
- `to_dict()` -> `dict`: Convert to dictionary
- `from_dict(data: dict, index: int = 0)` -> `Region`: Create from dictionary

---

### ImageDimensions

Image dimensions in pixels.

```python
@dataclass(frozen=True)
class ImageDimensions:
    width: int
    height: int
```

**Properties:**
- `aspect_ratio` -> `float`: Width / height ratio

**Methods:**
- `to_dict()` -> `dict`: Convert to dictionary
- `from_dict(data: dict)` -> `ImageDimensions`: Create from dictionary

---

### Layout

Complete layout extracted from an infographic.

```python
@dataclass(frozen=True)
class Layout:
    image_px: ImageDimensions      # Source image dimensions
    regions: tuple[Region, ...]    # Detected regions
```

**Properties:**
- `text_regions` -> `tuple[Region, ...]`: Only text regions
- `image_regions` -> `tuple[Region, ...]`: Only image regions

**Methods:**
- `to_dict()` -> `dict`: Convert to dictionary
- `to_json(indent: int = 2)` -> `str`: Convert to JSON string
- `from_dict(data: dict)` -> `Layout`: Create from dictionary
- `from_json(json_str: str)` -> `Layout`: Create from JSON string

---

## validator

JSON schema validation for layout.json files.

### LayoutValidationError

```python
class LayoutValidationError(Exception):
    """Raised when layout.json fails validation."""
```

### validate_layout

```python
def validate_layout(data: dict) -> Layout
```

Validate and parse a layout.json dictionary.

**Args:**
- `data`: Raw dictionary from JSON parsing

**Returns:**
- Validated `Layout` object

**Raises:**
- `LayoutValidationError`: If validation fails

---

### clamp_bbox_to_bounds

```python
def clamp_bbox_to_bounds(bbox: BBoxPx, width: int, height: int) -> BBoxPx
```

Clamp a bounding box to stay within image bounds.

**Args:**
- `bbox`: Original bounding box
- `width`: Image width in pixels
- `height`: Image height in pixels

**Returns:**
- Clamped `BBoxPx`

---

## geometry

Coordinate transforms from pixel space to slide points.

### Fit

```python
@dataclass(frozen=True)
class Fit:
    scale: float         # Scale factor (px to pt)
    offset_x_pt: float   # X offset for centering
    offset_y_pt: float   # Y offset for centering
    placed_w_pt: float   # Placed width in points
    placed_h_pt: float   # Placed height in points
```

### compute_fit

```python
def compute_fit(
    img_w_px: float,
    img_h_px: float,
    slide_w_pt: float,
    slide_h_pt: float,
) -> Fit
```

Compute scaling and offset to fit image on slide.

Preserves aspect ratio and centers the image.

**Args:**
- `img_w_px`: Image width in pixels
- `img_h_px`: Image height in pixels
- `slide_w_pt`: Slide width in points
- `slide_h_pt`: Slide height in points

**Returns:**
- `Fit` object with scale, offsets, and placed dimensions

---

### bbox_px_to_pt

```python
def bbox_px_to_pt(bbox: BBoxPx, fit: Fit) -> tuple[float, float, float, float]
```

Convert a bounding box from pixel coordinates to slide points.

**Args:**
- `bbox`: Bounding box in pixel coordinates
- `fit`: Fit object from `compute_fit()`

**Returns:**
- Tuple of `(x_pt, y_pt, w_pt, h_pt)` in slide coordinates

---

## postprocess

Post-processing utilities for VLM-extracted layouts.

### Layout Cleanup Functions

```python
def trim_whitespace(layout: Layout) -> Layout
def normalize_spaces(layout: Layout) -> Layout
def drop_empty_regions(layout: Layout) -> Layout
def clamp_to_bounds(layout: Layout) -> Layout
def sort_by_reading_order(layout: Layout) -> Layout
def enforce_minimum_size(layout: Layout, min_w: float = 10.0, min_h: float = 10.0) -> Layout
```

### postprocess_layout

```python
def postprocess_layout(layout: Layout) -> Layout
```

Apply all standard post-processing steps in order.

---

### ValidationWarning

```python
@dataclass
class ValidationWarning:
    region_id: str           # Region ID or comma-separated IDs
    warning_type: str        # Type: low_confidence, has_notes, empty_text, small_region, overlap
    message: str             # Human-readable message
    severity: str = "warning"  # "warning" or "info"
```

### OverlapInfo

```python
@dataclass
class OverlapInfo:
    region_a_id: str    # First region ID
    region_b_id: str    # Second region ID
    iou: float          # Intersection over Union
    overlap_area: float # Overlap area in square pixels
```

### compute_bbox_iou

```python
def compute_bbox_iou(a: BBoxPx, b: BBoxPx) -> float
```

Compute Intersection over Union (IoU) of two bounding boxes.

**Returns:** IoU value between 0 and 1.

---

### find_overlapping_regions

```python
def find_overlapping_regions(layout: Layout, iou_threshold: float = 0.3) -> list[OverlapInfo]
```

Find pairs of regions with significant overlap.

---

### validate_layout (postprocess)

```python
def validate_layout(
    layout: Layout,
    confidence_threshold: float = 0.7,
    iou_threshold: float = 0.3,
) -> list[ValidationWarning]
```

Validate a layout and return warnings about potential issues.

---

### get_layout_statistics

```python
def get_layout_statistics(layout: Layout) -> dict
```

Compute statistics about a layout.

**Returns:** Dictionary with keys:
- `total_regions`, `text_regions`, `image_regions`
- `avg_confidence`, `min_confidence`, `max_confidence`
- `total_text_chars`, `coverage_ratio`
- `image_width`, `image_height`

---

## uploader

Image upload and cropping utilities.

### UploadError

```python
class UploadError(Exception):
    """Raised when image upload fails."""
```

### Uploader (Protocol)

```python
class Uploader(Protocol):
    def upload_png(self, local_path: str, object_name: str) -> str:
        """Upload PNG and return public URL."""
```

### GCSUploader

```python
class GCSUploader:
    def __init__(self, bucket_name: str) -> None
    def upload_png(self, local_path: str, object_name: str) -> str
```

Google Cloud Storage uploader implementation.

---

### crop_region_png

```python
def crop_region_png(infographic_path: str, bbox: BBoxPx, out_path: str) -> None
```

Crop a region from an infographic and save as PNG.

---

### crop_and_upload_regions

```python
def crop_and_upload_regions(
    infographic_path: str,
    layout: Layout,
    uploader: Uploader,
    prefix: str = "",
    temp_dir: str | None = None,
) -> dict[str, str]
```

Crop and upload all image regions that need cropping.

**Returns:** Dict mapping region ID to public URL.

---

### get_image_dimensions

```python
def get_image_dimensions(image_path: str) -> tuple[int, int]
```

Get dimensions of an image file.

**Returns:** Tuple of `(width, height)` in pixels.

---

## slides_api

Google Slides API request builders.

### req_create_slide

```python
def req_create_slide(slide_id: str, insertion_index: int = 0) -> dict
```

Create a blank slide request.

---

### req_create_image

```python
def req_create_image(
    obj_id: str,
    slide_id: str,
    url: str,
    x_pt: float,
    y_pt: float,
    w_pt: float,
    h_pt: float,
) -> dict
```

Create an image placement request.

---

### req_create_textbox

```python
def req_create_textbox(
    obj_id: str,
    slide_id: str,
    x_pt: float,
    y_pt: float,
    w_pt: float,
    h_pt: float,
) -> dict
```

Create a text box request.

---

### req_insert_text

```python
def req_insert_text(obj_id: str, text: str) -> dict
```

Create a text insertion request.

---

### req_transparent_shape

```python
def req_transparent_shape(obj_id: str) -> dict
```

Make a shape transparent (no fill, no outline).

---

### req_text_style

```python
def req_text_style(
    obj_id: str,
    font_family: str | None = None,
    font_size_pt: float | None = None,
    bold: bool | None = None,
) -> dict | None
```

Create a text style update request.

**Returns:** Request dict, or `None` if no styles specified.

---

## build_slide

Main orchestration for building slides from layouts.

### SlidesAPIError

```python
class SlidesAPIError(Exception):
    """Raised when Slides API call fails."""
```

### get_page_size_pt

```python
def get_page_size_pt(service: Any, presentation_id: str) -> tuple[float, float]
```

Fetch slide page size in points.

**Returns:** Tuple of `(width_pt, height_pt)`.

---

### build_requests_for_infographic

```python
def build_requests_for_infographic(
    slide_id: str,
    layout: Layout,
    fit: Fit,
    infographic_public_url: str | None = None,
    cropped_url_by_region_id: dict[str, str] | None = None,
    place_background: bool = True,
) -> list[dict]
```

Build all API requests for one infographic slide.

---

### apply_requests

```python
def apply_requests(service: Any, presentation_id: str, requests: list[dict]) -> dict
```

Execute batch update with requests.

---

### build_slide

```python
def build_slide(
    service: Any,
    presentation_id: str,
    layout: Layout,
    slide_id: str,
    infographic_public_url: str | None = None,
    cropped_url_by_region_id: dict[str, str] | None = None,
    place_background: bool = True,
) -> dict
```

Build a complete slide from a layout.

---

## auth

Google API authentication utilities.

### get_slides_service_oauth

```python
def get_slides_service_oauth(
    client_secret_path: str,
    token_path: str = "token.json",
) -> Any
```

Get authenticated Slides API service using OAuth.

---

### get_slides_service_sa

```python
def get_slides_service_sa(sa_json_path: str) -> Any
```

Get authenticated Slides API service using service account.
