"""FastAPI backend for images2slides SaaS."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .db.session import engine
from .db import models
from .routers import health, auth, projects, jobs, oauth, files


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Create tables on startup (for development)
    # In production, use alembic migrations
    async with engine.begin() as conn:
        await conn.run_sync(models.Base.metadata.create_all)
    yield
    # Cleanup on shutdown
    await engine.dispose()


app = FastAPI(
    title="images2slides API",
    version="0.1.0",
    description="Convert infographic images to editable Google Slides",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.app_base_url, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(auth.router, prefix="/api/v1", tags=["auth"])
app.include_router(oauth.router, prefix="/api/v1/oauth", tags=["oauth"])
app.include_router(projects.router, prefix="/api/v1", tags=["projects"])
app.include_router(jobs.router, prefix="/api/v1", tags=["jobs"])
app.include_router(files.router, prefix="/api/v1", tags=["files"])