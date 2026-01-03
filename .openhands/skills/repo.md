# images2slides Repository Knowledge

## Project Overview
This repository contains the `images2slides` project - a tool to convert static infographic images into editable Google Slides presentations using Vision-Language Models (VLMs).

## Project Structure

### Core Library (`images2slides/`)
- `vlm/extract.py` - VLM extraction for infographic region analysis, supports Google, OpenAI, Anthropic, OpenRouter
- `models.py` - Data models: Layout, Region, BBoxPx, TextStyle, ImageDimensions
- `postprocess.py` - Post-processing utilities for layouts (trim whitespace, normalize, clamp bounds)
- `build_slide.py` - Main orchestration for building slides from layouts
- `slides_api.py` - Google Slides API helpers
- `validator.py` - Layout validation
- `geometry.py` - Geometry calculations for slide fitting
- `uploader.py` - Image uploading utilities
- `auth.py` - Google OAuth authentication

### CLI (`cli/`)
- `__main__.py` - Command-line interface entry point

### SaaS Wrapper (`saas/`)
Implements the SaaS web application as specified in `plans/images2slides_SaaS_wrapper_SPEC.md`.

#### Backend (`saas/backend/`)
- FastAPI application
- `main.py` - App entry point with lifespan handler
- `config.py` - Pydantic settings from environment
- `db/models.py` - SQLAlchemy models (User, OAuthToken, Project, ProjectImage, Job, JobEvent, JobArtifact)
- `db/session.py` - Async database session management
- `routers/` - API endpoints (health, auth, oauth, projects, jobs, files)
- `services/auth.py` - Google token verification and user management
- `services/encryption.py` - Token encryption at rest using Fernet
- `storage/base.py` - Storage abstraction (local filesystem, S3/GCS placeholders)
- `migrations/` - Alembic migrations

#### Worker (`saas/worker/`)
- `main.py` - Job runner loop with graceful shutdown
- `pipeline.py` - Job pipeline execution (validate -> extract -> postprocess -> build)

#### Frontend (`saas/web/`)
- Next.js 14 with App Router
- NextAuth.js for Google SSO
- Tailwind CSS for styling
- @dnd-kit for drag-and-drop reordering
- `app/page.tsx` - Landing page with sign-in
- `app/(dashboard)/` - Authenticated dashboard routes
- `lib/api.ts` - API client functions

## Key Design Decisions
1. **Postgres-backed job queue** - Uses `FOR UPDATE SKIP LOCKED` for safe job claiming
2. **Encrypted token storage** - OAuth tokens encrypted at rest with Fernet
3. **Step machine pattern** - Jobs progress through discrete steps with persistence
4. **Separation of concerns** - API for HTTP/auth, Worker for long-running tasks
5. **Storage abstraction** - Supports local dev and cloud storage backends

## Running Locally
```bash
docker-compose up
```

Services:
- Web: http://localhost:3000
- API: http://localhost:8000
- Health check: http://localhost:8000/api/v1/health

## Environment Variables
See `.env.example` for all configuration options.