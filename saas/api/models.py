from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Column, String, Integer, DateTime, Text, ForeignKey, 
    Boolean, JSON, Enum as SQLEnum, Float, Index
)
from sqlalchemy.orm import relationship
from database import Base
import enum


class JobStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"


class PageSize(str, enum.Enum):
    standard_4_3 = "standard_4_3"
    standard_16_9 = "standard_16_9"
    widescreen_16_10 = "widescreen_16_10"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    google_sub = Column(String(255), unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    name = Column(String(255))
    picture_url = Column(String(512))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    projects = relationship("Project", back_populates="owner")
    oauth_tokens = relationship("OAuthToken", back_populates="user", cascade="all, delete-orphan")


class OAuthToken(Base):
    __tablename__ = "oauth_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    access_token = Column(Text, nullable=False)
    refresh_token = Column(Text)
    expires_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="oauth_tokens")


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(255), nullable=False)
    page_size = Column(String(50), default="standard_16_9")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    owner = relationship("User", back_populates="projects")
    images = relationship("ProjectImage", back_populates="project", cascade="all, delete-orphan", order_by="ProjectImage.ordinal")
    jobs = relationship("Job", back_populates="project", cascade="all, delete-orphan")


class ProjectImage(Base):
    __tablename__ = "project_images"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    original_filename = Column(String(255), nullable=False)
    storage_path = Column(String(512), nullable=False)
    ordinal = Column(Integer, nullable=False)
    width = Column(Integer)
    height = Column(Integer)
    mime_type = Column(String(50))
    file_hash = Column(String(64))
    created_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("Project", back_populates="images")

    __table_args__ = (
        Index('ix_project_images_project_ordinal', 'project_id', 'ordinal'),
    )


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    status = Column(SQLEnum(JobStatus), default=JobStatus.queued, nullable=False)
    page_size = Column(String(50))
    presentation_id = Column(String(255))
    presentation_url = Column(String(512))
    error_message = Column(Text)
    retry_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project = relationship("Project", back_populates="jobs")
    events = relationship("JobEvent", back_populates="job", cascade="all, delete-orphan", order_by="JobEvent.created_at")
    artifacts = relationship("JobArtifact", back_populates="job", cascade="all, delete-orphan")


class JobEvent(Base):
    __tablename__ = "job_events"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False)
    step = Column(String(100), nullable=False)
    status = Column(String(50), nullable=False)
    message = Column(Text)
    started_at = Column(DateTime, default=datetime.utcnow)
    finished_at = Column(DateTime)
    duration_seconds = Column(Float)

    job = relationship("Job", back_populates="events")

    __table_args__ = (
        Index('ix_job_events_job_created', 'job_id', 'created_at'),
    )


class JobArtifact(Base):
    __tablename__ = "job_artifacts"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False)
    artifact_type = Column(String(100), nullable=False)
    name = Column(String(255), nullable=False)
    storage_path = Column(String(512), nullable=False)
    content_hash = Column(String(64))
    metadata = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)

    job = relationship("Job", back_populates="artifacts")

    __table_args__ = (
        Index('ix_job_artifacts_job_type', 'job_id', 'artifact_type'),
    )
