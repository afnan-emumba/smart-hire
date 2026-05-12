from __future__ import annotations

import uuid
from typing import Any, Mapping

from fastapi import HTTPException, status

from app.core.auth import CurrentUser
from app.repositories.job_repo import JobRepository
from app.repositories.recruiter_repo import RecruiterRepository
from app.schemas.job import JobCreate, JobResponse


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
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only recruiters can create jobs",
            )

        recruiter = await self.recruiter_repo.get_by_id(job_create.recruiter_id)
        if recruiter is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Recruiter not found",
            )

        job = await self.job_repo.create(job_create)
        return JobResponse.model_validate(job)

    async def get_job(self, job_id: uuid.UUID) -> JobResponse:
        job = await self.job_repo.get_by_id(job_id)
        if job is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job not found",
            )

        return JobResponse.model_validate(job)

    async def list_jobs(
        self,
        recruiter_id: uuid.UUID | None = None,
        status_filter: str | None = None,
    ) -> list[JobResponse]:
        if recruiter_id is not None:
            jobs = await self.job_repo.list_by_recruiter(recruiter_id)
        else:
            jobs = await self.job_repo.list_all()

        if status_filter is not None:
            jobs = [job for job in jobs if job.status == status_filter]

        return [JobResponse.model_validate(job) for job in jobs]

    async def update_job(self, job_id: uuid.UUID, updates: Mapping[str, Any]) -> JobResponse:
        update_values = dict(updates)
        recruiter_id = update_values.get("recruiter_id")
        if recruiter_id is not None:
            recruiter = await self.recruiter_repo.get_by_id(recruiter_id)
            if recruiter is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Recruiter not found",
                )

        updated_job = await self.job_repo.update(job_id, update_values)
        if updated_job is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job not found",
            )

        return JobResponse.model_validate(updated_job)

    async def delete_job(self, job_id: uuid.UUID) -> None:
        was_deleted = await self.job_repo.delete(job_id)
        if not was_deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job not found",
            )