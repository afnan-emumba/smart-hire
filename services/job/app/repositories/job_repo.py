from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Mapping

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import JobStatus
from app.db.models import Job, JobStatusHistory


class JobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        job_data: Mapping[str, Any],
        *,
        recruiter_id: uuid.UUID,
        changed_by_role: str | None = None,
    ) -> Job:
        job = Job(**dict(job_data), recruiter_id=recruiter_id)
        self.session.add(job)
        await self.session.flush()
        self._add_status_history_entry(
            job,
            from_status=None,
            to_status=job.status,
            changed_by_user_id=recruiter_id,
            changed_by_role=changed_by_role,
        )
        await self.session.flush()
        await self.session.refresh(job)
        return job

    async def get_by_id(self, job_id: uuid.UUID) -> Job | None:
        result = await self.session.execute(select(Job).where(Job.id == job_id))
        return result.scalar_one_or_none()

    async def list_by_recruiter(
        self,
        recruiter_id: uuid.UUID,
        *,
        status_filter: str | None,
        limit: int,
        offset: int,
    ) -> list[Job]:
        stmt = select(Job).where(Job.recruiter_id == recruiter_id)
        if status_filter is not None:
            stmt = stmt.where(Job.status == status_filter)
        result = await self.session.execute(
            stmt
            .order_by(Job.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def list_all(
        self,
        *,
        status_filter: str | None,
        limit: int,
        offset: int,
    ) -> list[Job]:
        stmt = select(Job)
        if status_filter is not None:
            stmt = stmt.where(Job.status == status_filter)
        result = await self.session.execute(
            stmt.order_by(Job.created_at.desc()).limit(limit).offset(offset)
        )
        return list(result.scalars().all())

    async def update(self, job_id: uuid.UUID, updates: Mapping[str, Any]) -> Job | None:
        update_values = dict(updates)
        if not update_values:
            return await self.get_by_id(job_id)

        job = await self.get_by_id(job_id)
        if job is None:
            return None

        for field_name, value in update_values.items():
            setattr(job, field_name, value)

        await self.session.flush()
        await self.session.refresh(job)
        return job

    async def attach_job_description_file(
        self,
        job: Job,
        *,
        file_name: str,
        content_type: str,
        storage_path: str,
        uploaded_at: datetime,
    ) -> Job:
        job.jd_source_type = "pdf_upload"
        job.jd_parsing_status = "pending"
        job.jd_parsing_error = None
        job.jd_file_name = file_name
        job.jd_content_type = content_type
        job.jd_storage_path = storage_path
        job.jd_uploaded_at = uploaded_at
        job.description = None
        job.employment_type = None
        job.seniority_level = None
        job.department = None
        job.job_category = None
        job.location = None
        job.compensation = None
        job.years_of_experience_required = None
        job.application_deadline = None
        job.description_breakdown = None
        job.required_skills = []

        await self.session.flush()
        await self.session.refresh(job)
        return job

    async def set_job_description_parsing_result(
        self,
        job: Job,
        *,
        description: str | None,
        description_breakdown: dict[str, Any] | None,
        required_skills: list[str],
        parsing_status: str,
        parsing_error: str | None = None,
        structured_updates: Mapping[str, Any] | None = None,
    ) -> Job:
        job.description = description
        job.description_breakdown = description_breakdown
        job.required_skills = required_skills
        job.jd_parsing_status = parsing_status
        job.jd_parsing_error = parsing_error

        if structured_updates:
            for field_name, value in structured_updates.items():
                setattr(job, field_name, value)

        await self.session.flush()
        await self.session.refresh(job)
        return job

    async def update_status(
        self,
        job: Job,
        *,
        status: JobStatus,
        changed_by_user_id: uuid.UUID | None = None,
        changed_by_role: str | None = None,
        reason: str | None = None,
        notes: str | None = None,
    ) -> Job:
        previous_status = job.status
        job.status = status.value
        self._apply_status_timestamps(job, status)
        self._add_status_history_entry(
            job,
            from_status=previous_status,
            to_status=status.value,
            changed_by_user_id=changed_by_user_id,
            changed_by_role=changed_by_role,
            reason=reason,
            notes=notes,
        )
        await self.session.flush()
        await self.session.refresh(job)
        return job

    async def set_publishing_workflow(
        self,
        job: Job,
        *,
        workflow_id: str,
    ) -> Job:
        job.publishing_workflow_id = workflow_id
        job.publishing_error = None
        job.publishing_failed_at = None
        if job.processing_started_at is None and job.status == JobStatus.PROCESSING.value:
            job.processing_started_at = datetime.now(timezone.utc)

        await self.session.flush()
        await self.session.refresh(job)
        return job

    async def delete(self, job_id: uuid.UUID) -> bool:
        job = await self.get_by_id(job_id)
        if job is None:
            return False

        await self.session.delete(job)
        await self.session.flush()
        return True

    def _apply_status_timestamps(self, job: Job, status: JobStatus) -> None:
        changed_at = datetime.now(timezone.utc)
        if status == JobStatus.PROCESSING and job.processing_started_at is None:
            job.processing_started_at = changed_at
        elif status == JobStatus.READY and job.ready_at is None:
            job.ready_at = changed_at
        elif status == JobStatus.ARCHIVED and job.archived_at is None:
            job.archived_at = changed_at

    def _add_status_history_entry(
        self,
        job: Job,
        *,
        from_status: str | None,
        to_status: str,
        changed_by_user_id: uuid.UUID | None,
        changed_by_role: str | None,
        reason: str | None = None,
        notes: str | None = None,
    ) -> None:
        self.session.add(
            JobStatusHistory(
                job_id=job.id,
                from_status=from_status,
                to_status=to_status,
                changed_by_user_id=changed_by_user_id,
                changed_by_role=changed_by_role,
                reason=reason,
                notes=notes,
            )
        )
