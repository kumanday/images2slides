# Repository notes (images2slides)

## SaaS wrapper (spec: plans/images2slides_SaaS_wrapper_SPEC.md)

Implemented under `saas/`:

- `saas/backend/`: FastAPI backend (API) + Alembic migrations
- `saas/worker/`: worker process (FastAPI health endpoint + background job runner)
- `saas/web/`: Next.js (App Router) UI using NextAuth Google provider

### Local dev (docker-compose)

`docker-compose.yml` at repo root starts:

- `db` Postgres
- `api` FastAPI on :8000
- `worker` FastAPI health + runner on :8001
- `web` Next.js on :3000

Typical flow:

1. User signs in with Google via NextAuth.
2. NextAuth callback calls backend `POST /api/v1/oauth/google/exchange` (Bearer: Google **ID token**) to store access/refresh tokens encrypted.
3. UI uses `Authorization: Bearer <idToken>` to call backend APIs.
4. UI uploads images using `uploads/init` -> PUT signed URL -> `uploads/complete`.
5. UI creates job via `POST /projects/{id}/generate`.
6. Worker claims with `FOR UPDATE SKIP LOCKED`, runs step machine, stores artifacts, builds Slides.

### Env vars

Added to `.env.example`:

- `TOKENS_ENCRYPTION_KEY` (Fernet key)
- `NEXTAUTH_SECRET`
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`

Backend also uses `DATABASE_URL`, `APP_BASE_URL`, `API_BASE_URL`.

### Key API endpoints

- `GET /api/v1/health`
- `GET /api/v1/me`
- `POST /api/v1/oauth/google/exchange`
- `POST/GET/PATCH/DELETE /api/v1/projects...`
- `POST /api/v1/projects/{id}/uploads/init`
- `PUT /api/v1/uploads/{storage_key}?token=...`
- `POST /api/v1/projects/{id}/uploads/complete`
- `PATCH /api/v1/projects/{id}/images/reorder`
- `POST /api/v1/projects/{id}/generate`
- `GET /api/v1/jobs/{id}` and `/artifacts`

### Storage

Local development uses a Docker volume mounted at `/data`:

- uploads under `/data/uploads/<storage_key>`
- artifacts under `/data/artifacts/jobs/<job_id>/...`

### Idempotency/retries

Worker build step clears existing slides in the target presentation before rebuilding, reducing duplication on retries.
