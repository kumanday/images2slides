# Images2Slides SaaS Wrapper

A web application that wraps the `images2slides` library, allowing users to convert infographic images into editable Google Slides presentations through a multi-user web UI.

## Architecture

- **Frontend**: Next.js (App Router) with TypeScript
- **Backend**: FastAPI (Python)
- **Database**: PostgreSQL
- **Worker**: Async job processor with database-backed queue
- **Orchestration**: Docker Compose

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Google Cloud Project with OAuth 2.0 credentials
- VLM API key (OpenAI, Anthropic, or Google)

### Setup

1. **Clone and navigate to the project**:
   ```bash
   cd images2slides
   ```

2. **Configure environment variables**:
   ```bash
   cp .env.example .env
   ```

   Edit `.env` and fill in:
   - `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` (from Google Cloud Console)
   - `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` (for VLM)
   - `TOKENS_ENCRYPTION_KEY` (generate a 32-byte key)
   - `NEXTAUTH_SECRET` (generate a random secret)

3. **Start the services**:
   ```bash
   docker-compose up -d
   ```

4. **Run database migrations**:
   ```bash
   docker-compose exec api alembic upgrade head
   ```

5. **Access the application**:
   - Frontend: http://localhost:3000
   - API: http://localhost:8000
   - API Docs: http://localhost:8000/docs

## Development

### Running Services

```bash
# Start all services
docker-compose up

# Start specific service
docker-compose up api
docker-compose up worker
docker-compose up web
```

### Database Migrations

```bash
# Create a new migration
docker-compose exec api alembic revision --autogenerate -m "description"

# Apply migrations
docker-compose exec api alembic upgrade head

# Rollback migration
docker-compose exec api alembic downgrade -1
```

### API Development

The API is built with FastAPI and includes:
- Health check: `GET /api/v1/health`
- Authentication: `POST /api/v1/auth/google`, `GET /api/v1/me`
- Projects: CRUD operations at `/api/v1/projects`
- Jobs: Create and monitor at `/api/v1/jobs`

Interactive API documentation is available at `/docs`.

### Worker Development

The worker processes jobs asynchronously using a database-backed queue with row-level locking (`FOR UPDATE SKIP LOCKED`).

Job pipeline steps:
1. `validate_inputs` - Check project, images, and tokens
2. `extract_layouts` - Use VLM to analyze images
3. `postprocess_layouts` - Clean and optimize layouts
4. `upload_assets` - Upload image regions to storage (optional)
5. `create_presentation` - Create Google Slides presentation
6. `build_slides` - Build slides with extracted content

## Project Structure

```
images2slides/
├── images2slides/          # Core library
├── saas/
│   ├── api/               # FastAPI backend
│   │   ├── main.py        # Application entry point
│   │   ├── database.py    # Database configuration
│   │   ├── models.py      # SQLAlchemy models
│   │   ├── routers/       # API route handlers
│   │   └── migrations/    # Alembic migrations
│   ├── worker/            # Job worker
│   │   ├── main.py        # Worker entry point
│   │   ├── conversion_engine.py  # Pipeline orchestration
│   │   └── steps.py       # Pipeline step implementations
│   └── web/               # Next.js frontend
│       ├── app/           # App Router pages
│       └── lib/           # Utilities and API client
├── docker-compose.yml     # Service orchestration
├── Dockerfile.api         # API/Worker container
└── alembic.ini            # Alembic configuration
```

## Milestones

The implementation follows these milestones:

- **Milestone 0**: Infrastructure setup (docker-compose, health endpoints)
- **Milestone 1**: Google SSO and user identity
- **Milestone 2**: Project CRUD and image upload/reorder
- **Milestone 3**: Jobs framework with observable logs
- **Milestone 4**: Integrate upstream analyze + postprocess
- **Milestone 5**: Create Slides in user's Drive (end-to-end)
- **Milestone 6**: Safe retries and failure surfacing

## Security

- OAuth tokens are encrypted at rest using `TOKENS_ENCRYPTION_KEY`
- File uploads are restricted to image MIME types
- Rate limiting on job creation per user
- Signed URLs for artifact downloads
- Row-level locking prevents duplicate job execution

## License

MIT
