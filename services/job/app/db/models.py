from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from db.base import Base, TimestampMixin
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import JobStatus


class Job(TimestampMixin, Base):
    __tablename__ = "jobs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'processing', 'ready', 'archived')",
            name="ck_jobs_status_valid",
        ),
        CheckConstraint(
            "jd_parsing_status IN ('pending', 'processing', 'parsed', 'failed')",
            name="ck_jobs_jd_parsing_status_valid",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recruiter_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
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
    processing_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    publishing_workflow_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    publishing_failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    publishing_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=JobStatus.DRAFT.value,
        server_default=JobStatus.DRAFT.value,
    )

    status_history: Mapped[list[JobStatusHistory]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="JobStatusHistory.changed_at",
    )


class JobStatusHistory(Base):
    __tablename__ = "job_status_history"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    from_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    to_status: Mapped[str] = mapped_column(String(32), nullable=False)
    changed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    changed_by_role: Mapped[str | None] = mapped_column(String(32), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    job: Mapped[Job] = relationship(back_populates="status_history")
