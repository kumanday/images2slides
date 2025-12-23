# Configuration Guide

This guide covers all configuration options for the slides_infographic system.

## Environment Variables

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `PRESENTATION_ID` | Target Google Slides presentation ID | `1BxiMVs0XRA5nFMdKvBd...` |

### Authentication Variables

Choose one authentication method:

#### OAuth 2.0 (Interactive)

| Variable | Description | Default |
|----------|-------------|---------|
| `CLIENT_SECRET_PATH` | Path to OAuth client secret JSON | - |
| `TOKEN_PATH` | Path to cached OAuth token | `token.json` |

#### Service Account (Automated)

| Variable | Description | Default |
|----------|-------------|---------|
| `SERVICE_ACCOUNT_PATH` | Path to service account JSON | - |

### Image Upload Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `GCS_BUCKET` | Google Cloud Storage bucket name | - |

### VLM Variables (one required for image analysis)

| Variable | Description | Default Model |
|----------|-------------|---------------|
| `GOOGLE_API_KEY` | Google AI API key (default provider) | `gemini-3-pro-preview` |
| `OPENAI_API_KEY` | OpenAI API key | `gpt-5.2` |
| `ANTHROPIC_API_KEY` | Anthropic API key | `claude-opus-4-5` |
| `OPENROUTER_API_KEY` | OpenRouter API key | `qwen/qwen3-vl-235b-a22b-instruct` |

## Google Cloud Setup

### 1. Create a Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Note your project ID

### 2. Enable APIs

Enable the following APIs:
- Google Slides API
- Google Drive API (if using Drive for images)
- Cloud Storage API (if using GCS for images)

```bash
gcloud services enable slides.googleapis.com
gcloud services enable drive.googleapis.com
gcloud services enable storage.googleapis.com
```

### 3. Create Credentials

#### Option A: OAuth 2.0 (Recommended for Development)

1. Go to APIs & Services > Credentials
2. Click "Create Credentials" > "OAuth client ID"
3. Select "Desktop app"
4. Download the JSON file
5. Save as `secrets/client_secret.json`

First run will open a browser for authentication. Token is cached in `token.json`.

#### Option B: Service Account (Recommended for Production)

1. Go to APIs & Services > Credentials
2. Click "Create Credentials" > "Service account"
3. Grant necessary roles:
   - `roles/slides.editor` for Slides access
   - `roles/storage.objectAdmin` for GCS (if needed)
4. Create a key (JSON format)
5. Save as `secrets/service_account.json`

**Important:** Share the target presentation with the service account email.

### 4. Set Up Cloud Storage (Optional)

For image region uploads:

```bash
# Create bucket
gsutil mb gs://your-bucket-name

# Make objects publicly readable (for Slides API)
gsutil iam ch allUsers:objectViewer gs://your-bucket-name
```

Or use fine-grained access with signed URLs.

## Configuration Files

### secrets/client_secret.json

OAuth 2.0 client secret (downloaded from Google Cloud Console):

```json
{
  "installed": {
    "client_id": "xxx.apps.googleusercontent.com",
    "project_id": "your-project",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "client_secret": "xxx",
    "redirect_uris": ["http://localhost"]
  }
}
```

### secrets/service_account.json

Service account key (downloaded from Google Cloud Console):

```json
{
  "type": "service_account",
  "project_id": "your-project",
  "private_key_id": "xxx",
  "private_key": "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n",
  "client_email": "name@your-project.iam.gserviceaccount.com",
  "client_id": "xxx",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token"
}
```

### .env (Optional)

For local development, create a `.env` file:

```bash
PRESENTATION_ID=1BxiMVs0XRA5nFMdKvBdkVTWFtYRCB...
CLIENT_SECRET_PATH=secrets/client_secret.json
GCS_BUCKET=my-slides-bucket
```

Load with:
```bash
export $(cat .env | xargs)
```

## CLI Configuration

### Command-Line Options

All environment variables can be overridden via CLI:

```bash
slides-infographic build \
  --presentation-id "OVERRIDE_ID" \
  --client-secret "path/to/secret.json" \
  --layout layout.json \
  --infographic image.png
```

### Verbosity

Enable verbose logging:

```bash
slides-infographic -v build ...
```

## Logging Configuration

Configure logging in your application:

```python
import logging

# Set level for all slides_infographic loggers
logging.getLogger("slides_infographic").setLevel(logging.DEBUG)

# Or configure specific modules
logging.getLogger("slides_infographic.build_slide").setLevel(logging.INFO)
logging.getLogger("slides_infographic.uploader").setLevel(logging.DEBUG)
```

### Log Levels

| Level | Usage |
|-------|-------|
| DEBUG | Coordinate transforms, request details |
| INFO | Slide created, regions processed |
| WARNING | Low confidence regions, overlaps detected |
| ERROR | API failures, validation errors |

## Slide Configuration

### Page Size

The system automatically detects page size from the presentation. Common sizes:

| Type | Width (pt) | Height (pt) | Aspect Ratio |
|------|------------|-------------|--------------|
| Standard (4:3) | 720 | 540 | 1.33 |
| Widescreen (16:9) | 720 | 405 | 1.78 |
| Widescreen (16:10) | 720 | 450 | 1.60 |

### Object ID Conventions

Customize object ID prefixes:

```python
# Default conventions
slide_id = f"SLIDE_{slug}"
text_id = f"TXT_{region_id}"
image_id = f"IMG_{region_id}"
background_id = f"BG_{slide_id}"
```

## Validation Thresholds

Configure validation in code:

```python
from images2slides.postprocess import validate_layout

warnings = validate_layout(
    layout,
    confidence_threshold=0.7,  # Warn below this confidence
    iou_threshold=0.3,         # Warn on overlaps above this IoU
)
```

### Default Thresholds

| Setting | Default | Description |
|---------|---------|-------------|
| `confidence_threshold` | 0.7 | Minimum confidence before warning |
| `iou_threshold` | 0.3 | Minimum IoU to warn about overlaps |
| `min_w` | 10.0 | Minimum region width (px) |
| `min_h` | 10.0 | Minimum region height (px) |
| `small_area` | 100 | Area below which to warn (sq px) |

## Security Considerations

### Credential Storage

- **Never** commit credentials to version control
- Add to `.gitignore`:
  ```
  secrets/
  token.json
  *.json
  !examples/*.json
  !tests/fixtures/*.json
  ```

### Token Refresh

OAuth tokens expire. The system automatically refreshes them using the refresh token stored in `token.json`.

### Service Account Permissions

Grant minimum required permissions:
- Slides: `roles/slides.editor` (or custom role with `slides.presentations.update`)
- GCS: `roles/storage.objectCreator` for uploads

### Network Security

- All Google API calls use HTTPS
- GCS URLs can be:
  - Public (`gs://bucket/object` → `https://storage.googleapis.com/bucket/object`)
  - Signed URLs (time-limited access)

## Troubleshooting

### "Access denied" errors

1. Check presentation is shared with service account email
2. Verify OAuth scopes include `presentations`
3. Re-authenticate: `rm token.json && slides-infographic build ...`

### "Image not accessible" errors

1. Verify image URL is publicly accessible
2. Check GCS bucket permissions
3. Test URL in browser: `curl -I <url>`

### "Rate limit exceeded"

1. Reduce batch size
2. Add delays between requests
3. Request quota increase in Cloud Console

### "Invalid object ID"

1. Object IDs must be unique per presentation
2. Use deterministic IDs to enable retries
3. Check for ID collisions with existing elements
