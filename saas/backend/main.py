from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .routers import artifacts, health, jobs, me, oauth, projects, uploads

settings = get_settings()

app = FastAPI(title="images2slides SaaS API", version="0.1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.app_base_url,
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"] ,
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(me.router, prefix="/api/v1", tags=["auth"])
app.include_router(oauth.router, prefix="/api/v1", tags=["auth"])
app.include_router(projects.router, prefix="/api/v1", tags=["projects"])
app.include_router(uploads.router, prefix="/api/v1", tags=["uploads"])
app.include_router(jobs.router, prefix="/api/v1", tags=["jobs"])
app.include_router(artifacts.router, prefix="/api/v1", tags=["artifacts"])
