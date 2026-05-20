from __future__ import annotations

import asyncio
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.auth import CurrentUser
from app.core.config import Settings
from app.core.enums import JobStatus
from app.core.state_machine import StateMachine
from app.repositories.job_repo import JobRepository
from app.repositories.recruiter_repo import RecruiterRepository
from app.schemas.job import JobCreate, JobResponse, JobUpdate
from app.services.job_breakdown_service import JobBreakdownService
from app.services.exceptions import (
    BadRequestError,
    ForbiddenError,
    InvalidStateTransitionError,
    NotFoundError,
    PayloadTooLargeError,
)


class JobService:
    def __init__(
        self,
        job_repo: JobRepository,
        recruiter_repo: RecruiterRepository,
        settings: Settings,
    ) -> None:
        self.job_repo = job_repo
        self.recruiter_repo = recruiter_repo
        self.settings = settings

    async def create_job(self, job_create: JobCreate, current_user: CurrentUser) -> JobResponse:
        if current_user.role != "RECRUITER":
            raise ForbiddenError("Only recruiters can create jobs")

        try:
            recruiter_id = uuid.UUID(current_user.id)
        except ValueError as exc:
            raise BadRequestError("X-User-ID must be a valid recruiter UUID") from exc

        recruiter = await self.recruiter_repo.get_by_id(recruiter_id)
        if recruiter is None:
            raise NotFoundError("Recruiter not found")

        breakdown_fields = await self._build_breakdown_fields(
            description=job_create.description,
            required_skills=job_create.required_skills,
        )
        job_data = {
            "title": job_create.title,
            "description": job_create.description,
            "required_skills": breakdown_fields["required_skills"],
            "jd_source_type": "manual_text" if job_create.description else None,
            "jd_parsing_status": breakdown_fields["jd_parsing_status"],
            "jd_parsing_error": breakdown_fields["jd_parsing_error"],
            "description_breakdown": breakdown_fields["description_breakdown"],
            "status": breakdown_fields["status"],
        }
        job = await self.job_repo.create(
            job_data,
            recruiter_id=recruiter_id,
        )
        return JobResponse.model_validate(job)

    async def get_job(self, job_id: uuid.UUID) -> JobResponse:
        job = await self.job_repo.get_by_id(job_id)
        if job is None:
            raise NotFoundError("Job not found")

        return JobResponse.model_validate(job)

    async def list_jobs(
        self,
        recruiter_id: uuid.UUID | None = None,
        status_filter: str | None = None,
        *,
        limit: int,
        offset: int,
    ) -> list[JobResponse]:
        if recruiter_id is not None:
            jobs = await self.job_repo.list_by_recruiter(
                recruiter_id,
                status_filter=status_filter,
                limit=limit,
                offset=offset,
            )
        else:
            jobs = await self.job_repo.list_all(
                status_filter=status_filter,
                limit=limit,
                offset=offset,
            )

        return [JobResponse.model_validate(job) for job in jobs]

    async def update_job(
        self,
        job_id: uuid.UUID,
        job_update: JobUpdate,
        current_user: CurrentUser,
    ) -> JobResponse:
        owner_id = self._require_recruiter_user_id(current_user)
        existing_job = await self.job_repo.get_by_id(job_id)
        if existing_job is None:
            raise NotFoundError("Job not found")
        if existing_job.recruiter_id != owner_id:
            raise ForbiddenError("Not authorized to update this job")

        updates = job_update.model_dump(exclude_unset=True)
        if "description" in updates and updates["description"] is not None:
            breakdown_fields = await self._build_breakdown_fields(
                description=updates["description"],
                required_skills=updates.get("required_skills") or existing_job.required_skills,
            )
            updates["jd_source_type"] = "manual_text"
            updates["jd_parsing_status"] = breakdown_fields["jd_parsing_status"]
            updates["jd_parsing_error"] = breakdown_fields["jd_parsing_error"]
            updates["description_breakdown"] = breakdown_fields["description_breakdown"]
            updates["required_skills"] = breakdown_fields["required_skills"]
            if existing_job.status != JobStatus.PROCESSING.value:
                updates["status"] = breakdown_fields["status"]

        if "status" in updates:
            try:
                current_status = JobStatus(existing_job.status)
                target_status = JobStatus(updates["status"])
            except ValueError as exc:
                raise BadRequestError("Invalid job status") from exc

            if not StateMachine.can_transition(current_status, target_status):
                raise InvalidStateTransitionError(
                    f"Invalid job state transition from '{existing_job.status}' to '{updates['status']}'"
                )

        updated_job = await self.job_repo.update(job_id, updates)
        if updated_job is None:
            raise NotFoundError("Job not found")

        return JobResponse.model_validate(updated_job)

    async def upload_job_description(
        self,
        job_id: uuid.UUID,
        *,
        file_name: str,
        content_type: str,
        file_bytes: bytes,
        current_user: CurrentUser,
    ) -> JobResponse:
        owner_id = self._require_recruiter_user_id(current_user)

        if len(file_bytes) > self.settings.max_jd_size_bytes:
            raise PayloadTooLargeError("Job description file exceeds the configured size limit")

        if not file_bytes:
            raise BadRequestError("Job description file is empty")

        job = await self.job_repo.get_by_id(job_id)
        if job is None:
            raise NotFoundError("Job not found")

        if job.recruiter_id != owner_id:
            raise ForbiddenError("Not authorized to modify this job")

        if job.status != JobStatus.DRAFT.value:
            raise BadRequestError("Job description files can only be uploaded while the job is in draft")

        if content_type != "application/pdf":
            raise BadRequestError("Job description files must be uploaded as PDFs")

        upload_dir = Path(self.settings.jd_upload_dir)
        await asyncio.to_thread(upload_dir.mkdir, parents=True, exist_ok=True)

        sanitized_name = Path(file_name).name
        suffix = Path(sanitized_name).suffix.lower()
        if suffix != ".pdf":
            raise BadRequestError("Job description file must use a .pdf extension")

        stored_file_name = f"{job.id}{suffix}"
        file_path = upload_dir / stored_file_name
        previous_storage_path = job.jd_storage_path

        await asyncio.to_thread(file_path.write_bytes, file_bytes)

        uploaded_at = datetime.now(timezone.utc)
        updated_job = await self.job_repo.attach_job_description_file(
            job,
            file_name=sanitized_name,
            content_type=content_type,
            storage_path=file_path.as_posix(),
            uploaded_at=uploaded_at,
        )

        if previous_storage_path and previous_storage_path != file_path.as_posix():
            previous_path = Path(previous_storage_path)
            if previous_path.exists():
                await asyncio.to_thread(os.remove, previous_path)

        return JobResponse.model_validate(updated_job)

    async def delete_job(self, job_id: uuid.UUID, current_user: CurrentUser) -> None:
        owner_id = self._require_recruiter_user_id(current_user)
        existing_job = await self.job_repo.get_by_id(job_id)
        if existing_job is None:
            raise NotFoundError("Job not found")
        if existing_job.recruiter_id != owner_id:
            raise ForbiddenError("Not authorized to delete this job")

        was_deleted = await self.job_repo.delete(job_id)
        if not was_deleted:
            raise NotFoundError("Job not found")

    @staticmethod
    def _require_recruiter_user_id(current_user: CurrentUser) -> uuid.UUID:
        if current_user.role != "RECRUITER":
            raise ForbiddenError("Only recruiters can perform this action")

        try:
            return uuid.UUID(current_user.id)
        except ValueError as exc:
            raise BadRequestError("X-User-ID must be a valid recruiter UUID") from exc

    async def _build_breakdown_fields(
        self,
        *,
        description: str | None,
        required_skills: list[str],
    ) -> dict[str, Any]:
        normalized_required_skills = self._merge_required_skills(required_skills, [])
        if not description:
            return {
                "description_breakdown": None,
                "required_skills": normalized_required_skills,
                "jd_parsing_status": "pending",
                "jd_parsing_error": None,
                "status": JobStatus.DRAFT.value,
            }

        try:
            breakdown = await JobBreakdownService.breakdown_job_description(description)
        except Exception as exc:
            return {
                "description_breakdown": None,
                "required_skills": normalized_required_skills,
                "jd_parsing_status": "failed",
                "jd_parsing_error": str(exc),
                "status": JobStatus.PROCESSING.value,
            }

        extracted_skills = [skill.name for skill in breakdown.skills]
        return {
            "description_breakdown": breakdown.model_dump(),
            "required_skills": self._merge_required_skills(required_skills, extracted_skills),
            "jd_parsing_status": "parsed",
            "jd_parsing_error": None,
            "status": JobStatus.PROCESSING.value,
        }

    @staticmethod
    def _merge_required_skills(base_skills: list[str], extracted_skills: list[str]) -> list[str]:
        merged_skills: list[str] = []
        seen: set[str] = set()

        for skill in [*base_skills, *extracted_skills]:
            normalized_skill = skill.strip()
            if not normalized_skill:
                continue

            key = normalized_skill.casefold()
            if key in seen:
                continue

            seen.add(key)
            merged_skills.append(normalized_skill)

        return merged_skills