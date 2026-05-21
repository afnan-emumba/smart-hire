from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.core.application_states import ApplicationStatus
from app.core.enums import JobStatus


class Base(DeclarativeBase):
    pass


DEFAULT_MASTER_PROFILE_DATA: dict[str, Any] = {
    "summary": None,
    "skills": [],
    "contact": {
        "phone": None,
        "location": None,
    },
    "education": [],
    "work_experience": [],
    "links": {
        "linkedin": None,
        "github": None,
        "portfolio": None,
        "website": None,
    },
}
DEFAULT_MASTER_PROFILE_DATA_JSON = json.dumps(DEFAULT_MASTER_PROFILE_DATA)


def default_master_profile_data() -> dict[str, Any]:
    return json.loads(DEFAULT_MASTER_PROFILE_DATA_JSON)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class Recruiter(TimestampMixin, Base):
    __tablename__ = "recruiters"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    jobs: Mapped[list[Job]] = relationship(back_populates="recruiter")


class Candidate(TimestampMixin, Base):
    __tablename__ = "candidates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    master_profile_data: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=default_master_profile_data,
        server_default=text(f"'{DEFAULT_MASTER_PROFILE_DATA_JSON}'::jsonb"),
    )

    applications: Mapped[list[Application]] = relationship(back_populates="candidate")


class Job(TimestampMixin, Base):
    __tablename__ = "jobs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'processing', 'ready', 'archived')",
            name="ck_jobs_status_valid",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recruiter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("recruiters.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    employment_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    seniority_level: Mapped[str | None] = mapped_column(String(32), nullable=True)
    department: Mapped[str | None] = mapped_column(String(100), nullable=True)
    job_category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    location: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    compensation: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    years_of_experience_required: Mapped[int | None] = mapped_column(nullable=True)
    application_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    description_breakdown: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    required_skills: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    jd_source_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    jd_parsing_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="pending",
        server_default="pending",
    )
    jd_parsing_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    jd_file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    jd_content_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    jd_storage_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    jd_uploaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=JobStatus.DRAFT.value,
        server_default=JobStatus.DRAFT.value,
    )

    recruiter: Mapped[Recruiter] = relationship(back_populates="jobs")
    applications: Mapped[list[Application]] = relationship(back_populates="job")


class Application(TimestampMixin, Base):
    __tablename__ = "applications"
    __table_args__ = (
        UniqueConstraint("job_id", "candidate_id", name="uq_applications_job_candidate"),
        CheckConstraint(
            "status IN ('pending', 'screening', 'interview', 'offer', 'rejected', 'accepted')",
            name="ck_applications_status_valid",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("candidates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=ApplicationStatus.PENDING.value,
        server_default=ApplicationStatus.PENDING.value,
    )
    application_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    resume_file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    resume_content_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    resume_storage_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    resume_uploaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resume_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    job: Mapped[Job] = relationship(back_populates="applications")
    candidate: Mapped[Candidate] = relationship(back_populates="applications")
