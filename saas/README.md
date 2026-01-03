# images2slides SaaS Wrapper

A web application that wraps the `images2slides` library, enabling multi-user access via Google SSO.

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│                 │     │                 │     │                 │
│   Next.js Web   │────▶│  FastAPI API    │────▶│    Worker       │
│   (port 3000)   │     │  (port 8000)    │     │  (background)   │
│                 │     │                 │     │                 │
└─────────────────┘     └────────┬────────┘     └────────┬────────┘
                                 │                       │
                                 ▼                       ▼
                        ┌─────────────────┐     ┌─────────────────┐
                        │   PostgreSQL    │     │ images2slides   │
                        │   (port 5432)   │     │    library      │
                        └─────────────────┘     └─────────────────┘
```

## Quick Start

1. **Configure environment variables**
   ```bash
   cp .env.example .env
   # Edit .env and set:
   # - GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET (from Google Cloud Console)
   # - GOOGLE_API_KEY (for VLM extraction)
   # - TOKENS_ENCRYPTION_KEY (random 32+ char string)
   # - NEXTAUTH_SECRET (random string)
   ```

2. **Start with Docker Compose**
   ```bash
   docker-compose up
   ```

3. **Access the application**
   - Web UI: http://localhost:3000
   - API: http://localhost:8000
   - Health check: http://localhost:8000/api/v1/health

## Components

### Backend (`backend/`)
FastAPI application providing:
- User authentication via Google JWT verification
- Project and image management
- Job queue management
- File storage abstraction

### Worker (`worker/`)
Background job processor:
- Polls for queued jobs
- Runs the conversion pipeline
- Stores artifacts and logs

### Frontend (`web/`)
Next.js 14 application:
- Google SSO via NextAuth.js
- Project creation and management
- Image upload with drag-and-drop reordering
- Job status monitoring

## API Endpoints

### Health
- `GET /api/v1/health` - Health check

### Authentication
- `GET /api/v1/me` - Get current user

### OAuth
- `POST /api/v1/oauth/google/exchange` - Store OAuth tokens
- `GET /api/v1/oauth/google/status` - Check OAuth status

### Projects
- `POST /api/v1/projects` - Create project
- `GET /api/v1/projects` - List projects
- `GET /api/v1/projects/{id}` - Get project
- `PATCH /api/v1/projects/{id}` - Update project
- `DELETE /api/v1/projects/{id}` - Delete project
- `POST /api/v1/projects/{id}/uploads/init` - Initialize upload
- `POST /api/v1/projects/{id}/uploads/complete` - Complete upload
- `PATCH /api/v1/projects/{id}/images/reorder` - Reorder images
- `DELETE /api/v1/projects/{id}/images/{image_id}` - Delete image
- `POST /api/v1/projects/{id}/generate` - Start generation job

### Jobs
- `GET /api/v1/jobs/{id}` - Get job status
- `GET /api/v1/jobs/{id}/artifacts` - Get job artifacts
- `POST /api/v1/jobs/{id}/retry` - Retry failed job

## Development

### Database Migrations
```bash
# Run migrations
docker-compose exec api alembic upgrade head

# Create new migration
docker-compose exec api alembic revision --autogenerate -m "description"
```

### Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f worker
```

## Configuration

See `.env.example` for all configuration options.

### Required Variables
- `GOOGLE_CLIENT_ID` - Google OAuth client ID
- `GOOGLE_CLIENT_SECRET` - Google OAuth client secret  
- `GOOGLE_API_KEY` - Google AI API key for VLM
- `TOKENS_ENCRYPTION_KEY` - 32+ character encryption key
- `NEXTAUTH_SECRET` - NextAuth session encryption key

### Optional Variables
- `VLM_PROVIDER` - VLM provider (google, openai, anthropic, openrouter)
- `VLM_MODEL` - Specific model to use
- `STORAGE_TYPE` - Storage backend (local, s3, gcs)