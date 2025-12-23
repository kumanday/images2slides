# Development Guide

This guide covers setting up a development environment, running tests, and contributing to the project.

## Prerequisites

- Python 3.11 or higher
- [uv](https://docs.astral.sh/uv/) package manager
- Git
- (Optional) Google Cloud project for integration testing

### Installing uv

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or with Homebrew
brew install uv

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

## Environment Setup

### 1. Clone and Install Dependencies

```bash
cd slides_infographic

# Install all dependencies (creates .venv automatically)
uv sync

# Install with dev dependencies
uv sync --dev

# Install with VLM integration
uv sync --extra vlm

# Install everything
uv sync --dev --extra vlm
```

### 2. Verify Installation

```bash
# Check CLI is available
uv run slides-infographic --help

# Run tests
uv run pytest
```

### 3. Adding Dependencies

```bash
# Add a runtime dependency
uv add package-name

# Add a dev dependency
uv add --dev package-name

# Add to optional group
uv add --optional vlm package-name

# Remove a dependency
uv remove package-name
```

## Project Structure

```
slides_infographic/
├── slides_infographic/       # Main package
│   ├── __init__.py
│   ├── models.py            # Data models (BBoxPx, Region, Layout)
│   ├── validator.py         # JSON validation
│   ├── geometry.py          # Coordinate transforms
│   ├── postprocess.py       # Layout cleanup and validation
│   ├── uploader.py          # Image cropping and upload
│   ├── slides_api.py        # Slides API request builders
│   ├── build_slide.py       # Main orchestration
│   ├── auth.py              # Google API authentication
│   └── vlm/                  # VLM integration (future)
├── cli/                      # CLI entry points
│   └── __main__.py
├── tests/                    # Test suite
│   ├── conftest.py          # Pytest fixtures
│   ├── test_*.py            # Test modules
│   └── fixtures/            # Test data
├── docs/                     # Documentation
├── examples/                 # Example files
├── secrets/                  # Credentials (gitignored)
├── pyproject.toml           # Project configuration
├── uv.lock                  # Locked dependencies
└── README.md
```

## Running Tests

### All Tests

```bash
uv run pytest
```

### With Verbose Output

```bash
uv run pytest -v
```

### Specific Test File

```bash
uv run pytest tests/test_geometry.py -v
```

### Specific Test Class or Function

```bash
uv run pytest tests/test_geometry.py::TestComputeFit -v
uv run pytest tests/test_geometry.py::TestComputeFit::test_landscape_image_on_landscape_slide -v
```

### With Coverage

```bash
uv run pytest --cov=slides_infographic --cov=cli --cov-report=html
open htmlcov/index.html  # View coverage report
```

### Test Categories

| File | Tests | Description |
|------|-------|-------------|
| `test_models.py` | 25 | Data model serialization |
| `test_geometry.py` | 7 | Coordinate transforms |
| `test_validator.py` | 12 | JSON validation |
| `test_postprocess.py` | 24 | Layout cleanup and validation |
| `test_slides_api.py` | 10 | API request builders |
| `test_build_slide.py` | 12 | Slide building |
| `test_uploader.py` | 10 | Image cropping and upload |

## Code Quality

### Formatting

```bash
# Format all code
uv run black slides_infographic tests cli

# Check without modifying
uv run black --check slides_infographic tests cli
```

### Import Sorting

```bash
# Sort imports
uv run isort slides_infographic tests cli

# Check without modifying
uv run isort --check slides_infographic tests cli
```

### Linting

```bash
# Run linter
uv run ruff check slides_infographic tests cli

# Auto-fix issues
uv run ruff check --fix slides_infographic tests cli
```

### Type Checking

```bash
uv run mypy slides_infographic
```

### All Checks

```bash
# Run all quality checks
uv run black --check slides_infographic tests cli && \
uv run isort --check slides_infographic tests cli && \
uv run ruff check slides_infographic tests cli && \
uv run pytest
```

## Writing Tests

### Test Structure

Follow the existing pattern:

```python
"""Tests for module_name module."""

import pytest

from images2slides.module_name import function_to_test


class TestFunctionToTest:
    """Tests for function_to_test function."""

    def test_basic_case(self) -> None:
        """Test basic functionality."""
        result = function_to_test(input_value)
        assert result == expected_value

    def test_edge_case(self) -> None:
        """Test edge case handling."""
        result = function_to_test(edge_input)
        assert result == edge_expected
```

### Using Fixtures

Fixtures are defined in `conftest.py`:

```python
@pytest.fixture
def sample_layout() -> Layout:
    """Create a sample layout for testing."""
    return Layout(
        image_px=ImageDimensions(width=1600, height=900),
        regions=(
            Region(id="title", order=1, type="text", ...),
        ),
    )

# Use in tests
def test_something(sample_layout: Layout) -> None:
    result = process(sample_layout)
    assert ...
```

### Asserting Approximate Values

```python
import pytest

def test_floating_point(self) -> None:
    result = compute_something()
    assert result == pytest.approx(0.142857, rel=1e-5)
```

## Adding New Features

### 1. Create the Module

```python
# slides_infographic/new_feature.py
"""New feature description."""

from .models import Layout


def new_function(layout: Layout) -> SomeResult:
    """Do something new.
    
    Args:
        layout: Input layout.
        
    Returns:
        The result.
    """
    ...
```

### 2. Add Tests

```python
# tests/test_new_feature.py
"""Tests for new_feature module."""

import pytest

from images2slides.new_feature import new_function


class TestNewFunction:
    def test_basic(self) -> None:
        ...
```

### 3. Export from Package (if needed)

```python
# slides_infographic/__init__.py
from .new_feature import new_function

__all__ = [..., "new_function"]
```

### 4. Add CLI Command (if applicable)

```python
# cli/__main__.py

@cli.command()
@click.option("--input", required=True)
def new_command(input: str) -> None:
    """Description of new command."""
    from images2slides.new_feature import new_function
    result = new_function(input)
    click.echo(f"Result: {result}")
```

## Coding Conventions

### Type Hints

All functions should have type hints:

```python
def process_regions(
    layout: Layout,
    threshold: float = 0.7,
) -> list[Region]:
    ...
```

### Docstrings

Use Google-style docstrings:

```python
def compute_fit(
    img_w_px: float,
    img_h_px: float,
    slide_w_pt: float,
    slide_h_pt: float,
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

    Raises:
        ValueError: If dimensions are non-positive.
    """
```

### Logging

Use module-level loggers:

```python
import logging

logger = logging.getLogger(__name__)

def process():
    logger.info("Starting process")
    logger.debug("Details: %s", details)
    logger.warning("Potential issue: %s", issue)
    logger.error("Failed: %s", error)
```

### Error Handling

Define specific exceptions:

```python
class SpecificError(Exception):
    """Raised when specific condition occurs."""
    pass

def function():
    if error_condition:
        raise SpecificError(f"Details: {context}")
```

## Integration Testing

For testing with actual Google Slides API:

### 1. Set Up Credentials

```bash
# Download OAuth client secret
cp ~/Downloads/client_secret_*.json secrets/client_secret.json
```

### 2. Create Test Presentation

Create a blank Google Slides presentation and note its ID from the URL:
`https://docs.google.com/presentation/d/PRESENTATION_ID/edit`

### 3. Run Manual Test

```bash
export PRESENTATION_ID="your-presentation-id"

uv run slides-infographic build \
  --presentation-id $PRESENTATION_ID \
  --layout examples/sample_layout.json \
  --infographic path/to/test_image.png \
  --client-secret secrets/client_secret.json \
  --no-background
```

## Troubleshooting

### Import Errors

```bash
# Ensure dependencies are synced
uv sync --dev
```

### Dependency Issues

```bash
# Update lock file
uv lock

# Upgrade all dependencies
uv lock --upgrade

# Upgrade specific package
uv lock --upgrade-package package-name
```

### Test Discovery Issues

```bash
# Ensure __init__.py exists in tests/
touch tests/__init__.py
```

### OAuth Token Issues

```bash
# Delete cached token and re-authenticate
rm token.json
uv run slides-infographic build ...  # Will prompt for auth
```

### GCS Upload Errors

```bash
# Check GCS credentials
gcloud auth application-default login

# Or set service account
export GOOGLE_APPLICATION_CREDENTIALS="path/to/sa.json"
```

## uv Quick Reference

| Command | Description |
|---------|-------------|
| `uv sync` | Install dependencies from lock file |
| `uv sync --dev` | Include dev dependencies |
| `uv sync --extra vlm` | Include optional vlm group |
| `uv add pkg` | Add a dependency |
| `uv add --dev pkg` | Add a dev dependency |
| `uv remove pkg` | Remove a dependency |
| `uv lock` | Update lock file |
| `uv lock --upgrade` | Upgrade all dependencies |
| `uv run cmd` | Run command in virtual env |
| `uv python list` | List available Python versions |
| `uv python install 3.12` | Install Python version |
