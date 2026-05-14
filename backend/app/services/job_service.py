from __future__ import annotations

import uuid
from typing import Any, Mapping

from app.core.auth import CurrentUser
from app.repositories.job_repo import JobRepository
from app.repositories.recruiter_repo import RecruiterRepository
from app.schemas.job import JobCreate, JobResponse, JobUpdate
from app.services.exceptions import BadRequestError, ForbiddenError, NotFoundError


class JobService:
    def __init__(
        self,
        job_repo: JobRepository,
        recruiter_repo: RecruiterRepository,
    ) -> None:
        self.job_repo = job_repo
        self.recruiter_repo = recruiter_repo

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

        job = await self.job_repo.create(
            JobCreate(
                title=job_create.title,
                description=job_create.description,
                required_skills=job_create.required_skills,
            ),
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

        updated_job = await self.job_repo.update(job_id, job_update.model_dump(exclude_unset=True))
        if updated_job is None:
            raise NotFoundError("Job not found")

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