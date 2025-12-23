# images2slides

Convert static infographic images into editable Google Slides. Provide your infographic images, and the system automatically analyzes them using Vision-Language Models (VLMs) to extract text and visual elements, then reconstructs them as native, editable slide elements.

## Demo

<a href="https://storage.googleapis.com/images2slides/images2slides.mp4" target="_blank">
  <img src="https://storage.googleapis.com/images2slides/images2slides-Cover.jpg" alt="Watch the demo" />
</a>

*Click the image above to watch the demo video*

## Features

- **End-to-End Pipeline**: Just provide images - VLM analysis, layout extraction, and slide creation are all automated
- **Multi-Provider VLM Support**: Google Gemini, OpenAI, Anthropic, and OpenRouter
- **Multi-Slide Presentations**: Convert multiple infographics into a single presentation
- **Flexible Configuration**: Configure via `.env` file, environment variables, or CLI arguments
- **Coordinate Transformation**: Map pixel coordinates to slide points with aspect-ratio-preserving fit
- **Slide Reconstruction**: Create editable text boxes and placed images via Google Slides API

## Quick Start

```bash
# 1. Install
cd images2slides
uv sync

# 2. Configure (copy and edit .env.example)
cp .env.example .env
# Edit .env with your API keys and credentials

# 3. Convert images to slides
uv run images2slides convert \
  --image slide1.png \
  --image slide2.png \
  --title "My Presentation"
```

> **Note:** All CLI commands must be run with `uv run` prefix (e.g., `uv run images2slides ...`), which executes them within the project's virtual environment.

---

## Installation

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager

### Install

```bash
cd images2slides
uv sync
```

---

## Configuration

All configuration can be set via:
1. `.env` file (recommended)
2. Environment variables
3. CLI arguments (override .env and env vars)

### Step 1: Copy the Example Configuration

```bash
cp .env.example .env
```

### Step 2: Configure VLM Provider

Edit `.env` and set your VLM provider and API key:

```bash
# Choose your provider: google, openai, anthropic, or openrouter
VLM_PROVIDER=google

# Set the API key for your chosen provider
GOOGLE_API_KEY=your-api-key-here
```

#### VLM Provider Options

| Provider | Default Model | API Key Variable | Get API Key |
|----------|---------------|------------------|-------------|
| `google` (default) | `gemini-3-pro-preview` | `GOOGLE_API_KEY` | [Google AI Studio](https://aistudio.google.com/apikey) |
| `openai` | `gpt-5.2` | `OPENAI_API_KEY` | [OpenAI Platform](https://platform.openai.com/api-keys) |
| `anthropic` | `claude-opus-4-5` | `ANTHROPIC_API_KEY` | [Anthropic Console](https://console.anthropic.com/settings/keys) |
| `openrouter` | `qwen/qwen3-vl-235b-a22b-instruct` | `OPENROUTER_API_KEY` | [OpenRouter](https://openrouter.ai/keys) |

To use a specific model, set `VLM_MODEL` in `.env`:

```bash
VLM_MODEL=gemini-3-pro-preview
```

### Step 3: Configure Google Slides API Access

You need to authenticate with Google to create presentations. Choose **one** of these methods:

#### Option A: OAuth 2.0 Client Secret (Recommended for Personal Use)

This method opens a browser window for you to log in with your Google account. Best for local development and personal use.

**How to get `client_secret.json`:**

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the **Google Slides API**:
   - Go to "APIs & Services" > "Library"
   - Search for "Google Slides API"
   - Click "Enable"
4. Create OAuth credentials:
   - Go to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "OAuth client ID"
   - If prompted, configure the OAuth consent screen first (External is fine for personal use)
   - Select "Desktop app" as application type
   - Name it (e.g., "Slides Infographic")
   - Click "Create"
5. Download the credentials:
   - Click the download button next to your new OAuth client
   - Save the file as `secrets/client_secret.json`

**Configure in `.env`:**

```bash
CLIENT_SECRET_PATH=secrets/client_secret.json
```

On first run, a browser window will open for you to authorize the app. The token is cached for future use.

#### Option B: Service Account (Recommended for Automation/Servers)

This method uses a service account key file. Best for automated pipelines and server deployments. No browser interaction needed.

**How to get `service_account.json`:**

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the **Google Slides API** (same as above)
4. Create a service account:
   - Go to "IAM & Admin" > "Service Accounts"
   - Click "Create Service Account"
   - Name it (e.g., "slides-infographic")
   - Click "Create and Continue"
   - Skip the optional steps, click "Done"
5. Create a key:
   - Click on the service account you just created
   - Go to "Keys" tab
   - Click "Add Key" > "Create new key"
   - Select "JSON" format
   - Save the file as `secrets/service_account.json`

**Configure in `.env`:**

```bash
SERVICE_ACCOUNT_PATH=secrets/service_account.json
```

**Important:** Service accounts create presentations in their own Drive. To access them:
- Share the presentation with your email after creation, OR
- Set up domain-wide delegation to impersonate users

#### Which Should I Choose?

| Use Case | Recommended Method |
|----------|-------------------|
| Local development | OAuth 2.0 |
| Personal scripts | OAuth 2.0 |
| CI/CD pipelines | Service Account |
| Server applications | Service Account |
| Shared team tool | Service Account with delegation |

---

## Usage

All commands are run with `uv run` to execute within the virtual environment.

### Main Command: Convert Images to Slides

```bash
uv run images2slides convert \
  --image infographic1.png \
  --image infographic2.png \
  --title "My Presentation"
```

This command:
1. Analyzes each image with the configured VLM
2. Extracts text regions and image regions (icons, logos, charts)
3. Optionally uploads cropped image regions to GCS
4. Creates a new Google Slides presentation
5. Builds editable slides with text boxes and images

### Including Image Regions

If your infographics contain icons, logos, or charts that the VLM detects as image regions, you need a Google Cloud Storage bucket to host them:

```bash
uv run images2slides convert \
  --image infographic.png \
  --title "My Presentation" \
  --gcs-bucket your-bucket-name
```

Or set `GCS_BUCKET` in your `.env` file. Without a GCS bucket, image regions will be skipped and you'll see a warning.

**Output:**
```
Step 1: Analyzing 1 image(s) with gemini-3-pro-preview...
  [1/1] Analyzing: infographic.png
         Found 5 text, 3 image regions

Step 2: Uploading 3 image region(s) to GCS...
  [1/1] Cropping 3 regions from infographic.png

Step 3: Connecting to Google Slides API...

Step 4: Creating presentation 'My Presentation'...

============================================================
SUCCESS!
============================================================
Presentation URL: https://docs.google.com/presentation/d/abc123/edit
Presentation ID:  abc123
Slides created:   1
```

### CLI Options

```bash
uv run images2slides convert --help
```

| Option | Description | Default |
|--------|-------------|---------|
| `--image` | Path to infographic image (repeatable) | Required |
| `--title` | Presentation title | "Infographic Presentation" |
| `--page-size` | Slide size: 16:9, 16:10, or 4:3 | 16:9 |
| `--provider` | VLM provider | From `VLM_PROVIDER` or "google" |
| `--model` | VLM model | From `VLM_MODEL` or provider default |
| `--gcs-bucket` | GCS bucket for image regions | From `GCS_BUCKET` |
| `--save-layouts` | Save layout JSON files to directory | - |
| `--client-secret` | OAuth client secret path | From `CLIENT_SECRET_PATH` |
| `--service-account` | Service account path | From `SERVICE_ACCOUNT_PATH` |

### Analyze Images Only

Extract layout JSON without creating slides:

```bash
uv run images2slides analyze \
  --image infographic.png \
  --output layouts/
```

Creates `infographic_layout.json` with extracted text and bounding boxes.

### Other Commands

```bash
# Validate a layout file
uv run images2slides validate --layout layout.json

# Post-process a layout (clean up whitespace, clamp bounds)
uv run images2slides postprocess --layout raw.json --output clean.json

# Build slides from pre-existing layout files
uv run images2slides create \
  --layout slide1.json \
  --layout slide2.json \
  --title "My Deck"
```

---

## Programmatic Usage

```python
from images2slides.vlm import VLMConfig, extract_layout_from_image
from images2slides.auth import get_slides_service_oauth
from images2slides.build_slide import build_presentation, SlideInput
from images2slides.postprocess import postprocess_layout

# Configure VLM
config = VLMConfig(provider="google", model="gemini-3-pro-preview")

# Extract layouts from images
layouts = []
for image_path in ["slide1.png", "slide2.png"]:
    layout = extract_layout_from_image(image_path, config)
    layout = postprocess_layout(layout)
    layouts.append(layout)

# Authenticate with Google Slides
service = get_slides_service_oauth("secrets/client_secret.json")

# Build presentation
slide_inputs = [SlideInput(layout=layout) for layout in layouts]
result = build_presentation(
    service=service,
    slides=slide_inputs,
    title="My Presentation",
)

print(f"Created: {result.presentation_url}")
```

---

## Configuration Reference

### Environment Variables

All variables can be set in `.env` or as environment variables:

| Variable | Description |
|----------|-------------|
| `VLM_PROVIDER` | VLM provider: google, openai, anthropic, openrouter |
| `VLM_MODEL` | Model name (optional, uses provider default) |
| `GOOGLE_API_KEY` | Google AI API key |
| `OPENAI_API_KEY` | OpenAI API key |
| `ANTHROPIC_API_KEY` | Anthropic API key |
| `OPENROUTER_API_KEY` | OpenRouter API key |
| `CLIENT_SECRET_PATH` | Path to OAuth client secret JSON |
| `SERVICE_ACCOUNT_PATH` | Path to service account JSON |
| `GCS_BUCKET` | GCS bucket for image uploads (optional) |

### Example `.env` File

```bash
# VLM Configuration
VLM_PROVIDER=google
GOOGLE_API_KEY=AIza...

# Google Slides Authentication
CLIENT_SECRET_PATH=secrets/client_secret.json
```

---

## Development

### Setup

```bash
uv sync --dev
```

### Testing

```bash
uv run pytest
```

### Code Quality

```bash
uv run ruff check images2slides cli
uv run black images2slides cli
```

---

## Troubleshooting

### "API key not found"

Make sure you have:
1. Created a `.env` file from `.env.example`
2. Set the API key for your chosen provider
3. The `.env` file is in the current directory or a parent directory

### "Must provide --client-secret or --service-account"

You need Google Slides API credentials. See [Configure Google Slides API Access](#step-3-configure-google-slides-api-access).

### OAuth browser doesn't open

If running on a headless server, use a service account instead of OAuth.

### Service account can't access presentation

Service accounts create files in their own Drive. Either:
- Check the presentation URL in the output and open it
- Share the presentation with your email
- Use OAuth instead for personal use

---

## License

MIT
