# images2slides SaaS Wrapper

A lightweight SaaS-style web application that wraps the existing `kumanday/images2slides` proof of concept (POC) and exposes it via a multi-user web UI.

## Features

- **Google SSO Login**: Users sign in with their Google account
- **Project Management**: Create projects and upload infographic images
- **Image Ordering**: Reorder images to control slide sequence
- **Async Job Processing**: Background worker processes conversion jobs
- **Google Slides Integration**: Generate editable presentations in user's Google Drive
- **Job Observability**: View job progress and download artifacts

## Architecture

```
Frontend: Next.js 14 (App Router)
Backend: FastAPI (Python)
Database: PostgreSQL
Worker: Python background process
Container: Docker Compose
```

## Project Structure

```
saas/
├── api/                 # FastAPI backend
│   ├── main.py         # Application entry point
│   ├── routes.py       # API routes
│   ├── models.py       # SQLAlchemy models
│   ├── schemas.py      # Pydantic schemas
│   ├── auth.py         # Authentication utilities
│   ├── database.py     # Database connection
│   ├── requirements.txt
│   └── Dockerfile
├── worker/             # Background job processor
│   ├── worker.py       # Job runner
│   ├── requirements.txt
│   └── Dockerfile
└── web/                # Next.js frontend
    ├── app/            # App Router pages
    ├── components/     # React components
    ├── lib/            # Utilities
    ├── package.json
    └── Dockerfile

docker-compose.yml      # Orchestration
```

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Google Cloud Console credentials (OAuth 2.0 Client ID)

### 1. Configure Environment

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your credentials
# - GOOGLE_CLIENT_ID
# - GOOGLE_CLIENT_SECRET
# - NEXTAUTH_SECRET (generate with: openssl rand -base64 32)
# - TOKENS_ENCRYPTION_KEY (generate with: openssl rand -base64 32)
```

### 2. Start Services

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f
```

### 3. Verify Health

```bash
# API health check
curl http://localhost:8000/api/v1/health

# Expected: {"status":"healthy"}
```

## Development

### Frontend

```bash
cd saas/web
npm install
npm run dev
```

### Backend

```bash
cd saas/api
pip install -r requirements.txt
uvicorn main:app --reload
```

### Worker

```bash
cd saas/worker
pip install -r requirements.txt
python worker.py
```

## API Endpoints

### Authentication
- `POST /api/v1/auth/google` - Authenticate with Google ID token
- `GET /api/v1/me` - Get current user info

### Projects
- `POST /api/v1/projects` - Create project
- `GET /api/v1/projects` - List user's projects
- `GET /api/v1/projects/{id}` - Get project details
- `PATCH /api/v1/projects/{id}` - Update project
- `DELETE /api/v1/projects/{id}` - Delete project

### Images
- `POST /api/v1/projects/{id}/images` - Add image
- `POST /api/v1/projects/{id}/images/reorder` - Reorder images
- `DELETE /api/v1/projects/{id}/images/{image_id}` - Delete image

### Jobs
- `POST /api/v1/projects/{id}/jobs` - Create job
- `GET /api/v1/jobs/{id}` - Get job status
- `GET /api/v1/projects/{id}/jobs` - List project jobs

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://images2slides:images2slides@localhost:5432/images2slides` |
| `APP_BASE_URL` | Application base URL | `http://localhost:3000` |
| `TOKENS_ENCRYPTION_KEY` | Key for encrypting OAuth tokens | - |
| `GOOGLE_CLIENT_ID` | Google OAuth Client ID | - |
| `GOOGLE_CLIENT_SECRET` | Google OAuth Client Secret | - |
| `VLM_PROVIDER` | VLM provider (openai, anthropic) | `openai` |
| `VLM_MODEL` | VLM model name | `gpt-4o` |
| `NEXTAUTH_URL` | NextAuth URL | `http://localhost:3000` |
| `NEXTAUTH_SECRET` | NextAuth secret key | - |

### Google OAuth Scopes

The application requests these scopes:
- `openid`, `email`, `profile`
- `https://www.googleapis.com/auth/presentations`
- `https://www.googleapis.com/auth/drive.file`

## Milestones

| Milestone | Status |
|-----------|--------|
| 0: Repo skeleton and local boot | ✅ |
| 1: Google SSO and user identity | ✅ |
| 2: Project CRUD + image upload | ✅ |
| 3: Jobs framework with stub engine | ✅ |
| 4: Integrate analyze + postprocess | ✅ |
| 5: Create Slides in user's Drive | 🔄 |
| 6: Safe retries and failure surfacing | 🔄 |

## Database Schema

### Tables
- `users` - User accounts
- `oauth_tokens` - Encrypted OAuth tokens
- `projects` - User projects
- `project_images` - Images within projects
- `jobs` - Conversion jobs
- `job_events` - Job step events
- `job_artifacts` - Job artifacts (layouts, logs)

## Security Considerations

- OAuth tokens are encrypted at rest
- Jobs use row-level locking (`FOR UPDATE SKIP LOCKED`)
- Rate limiting on job creation
- File uploads restricted to image types
- Input validation on all endpoints

## License

MIT License
