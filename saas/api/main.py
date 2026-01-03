from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os

from saas.api.database import engine, Base
from saas.api.routers import health, auth, projects, jobs


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    # Create tables (in production, use Alembic migrations)
    Base.metadata.create_all(bind=engine)
    yield
    # Shutdown
    pass


app = FastAPI(
    title="Images2Slides API",
    description="SaaS API for converting infographic images to Google Slides",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("APP_BASE_URL", "http://localhost:3000")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(auth.router, prefix="/api/v1", tags=["auth"])
app.include_router(projects.router, prefix="/api/v1", tags=["projects"])
app.include_router(jobs.router, prefix="/api/v1", tags=["jobs"])


@app.get("/")
async def root():
    return {"message": "Images2Slides API", "version": "0.1.0"}
