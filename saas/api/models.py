from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Enum, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from saas.api.database import Base
import enum


class JobStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    google_sub = Column(String(255), unique=True, nullable=False, index=True)
    email = Column(String(255), nullable=False, index=True)
    name = Column(String(255))
    picture_url = Column(String(500))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    oauth_tokens = relationship("OAuthToken", back_populates="user", cascade="all, delete-orphan")
    projects = relationship("Project", back_populates="user", cascade="all, delete-orphan")


class OAuthToken(Base):
    __tablename__ = "oauth_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    provider = Column(String(50), nullable=False)  # 'google'
    access_token = Column(Text, nullable=False)  # Encrypted
    refresh_token = Column(Text)  # Encrypted
    token_type = Column(String(50))
    scope = Column(Text)
    expires_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="oauth_tokens")

    __table_args__ = (
        Index("ix_oauth_tokens_user_provider", "user_id", "provider"),
    )


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(255), nullable=False)
    page_size = Column(String(50), default="STANDARD_4_3")  # STANDARD_4_3, WIDE_16_9, WIDE_16_10
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="projects")
    images = relationship("ProjectImage", back_populates="project", cascade="all, delete-orphan", order_by="ProjectImage.ordinal")
    jobs = relationship("Job", back_populates="project", cascade="all, delete-orphan")


class ProjectImage(Base):
    __tablename__ = "project_images"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    original_filename = Column(String(255), nullable=False)
    storage_path = Column(String(500), nullable=False)
    ordinal = Column(Integer, nullable=False)
    width = Column(Integer)
    height = Column(Integer)
    mime_type = Column(String(100))
    file_hash = Column(String(64))  # SHA-256 hash
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    project = relationship("Project", back_populates="images")

    __table_args__ = (
        Index("ix_project_images_project_ordinal", "project_id", "ordinal"),
    )


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    status = Column(Enum(JobStatus), default=JobStatus.queued, nullable=False, index=True)
    page_size = Column(String(50))
    presentation_id = Column(String(255))
    presentation_url = Column(String(500))
    error_message = Column(Text)
    retry_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    project = relationship("Project", back_populates="jobs")
    events = relationship("JobEvent", back_populates="job", cascade="all, delete-orphan")
    artifacts = relationship("JobArtifact", back_populates="job", cascade="all, delete-orphan")


class JobEvent(Base):
    __tablename__ = "job_events"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    step = Column(String(100), nullable=False)  # validate_inputs, extract_layouts, etc.
    status = Column(String(50), nullable=False)  # started, completed, failed
    message = Column(Text)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    finished_at = Column(DateTime(timezone=True))
    duration_seconds = Column(Integer)

    # Relationships
    job = relationship("Job", back_populates="events")

    __table_args__ = (
        Index("ix_job_events_job_step", "job_id", "step"),
    )


class JobArtifact(Base):
    __tablename__ = "job_artifacts"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    artifact_type = Column(String(50), nullable=False)  # raw_layout, clean_layout, input_manifest, error_log
    name = Column(String(255), nullable=False)
    storage_path = Column(String(500), nullable=False)
    content_hash = Column(String(64))  # SHA-256 hash
    metadata = Column(Text)  # JSON string
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    job = relationship("Job", back_populates="artifacts")

    __table_args__ = (
        Index("ix_job_artifacts_job_type", "job_id", "artifact_type"),
    )
