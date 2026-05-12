from __future__ import annotations

import uuid

from fastapi import HTTPException, status

from app.core.auth import CurrentUser
from app.repositories.application_repo import ApplicationRepository
from app.repositories.candidate_repo import CandidateRepository
from app.repositories.job_repo import JobRepository
from app.schemas.application import ApplicationCreate, ApplicationResponse


class ApplicationService:
    def __init__(
        self,
        application_repo: ApplicationRepository,
        job_repo: JobRepository,
        candidate_repo: CandidateRepository,
    ) -> None:
        self.application_repo = application_repo
        self.job_repo = job_repo
        self.candidate_repo = candidate_repo

    async def apply_to_job(
        self,
        application_create: ApplicationCreate,
        current_user: CurrentUser,
    ) -> ApplicationResponse:
        if current_user.role != "CANDIDATE":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only candidates can apply to jobs",
            )

        job = await self.job_repo.get_by_id(application_create.job_id)
        if job is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job not found",
            )

        candidate = await self.candidate_repo.get_by_id(application_create.candidate_id)
        if candidate is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Candidate not found",
            )

        existing_application = await self.application_repo.get_by_job_and_candidate(
            application_create.job_id,
            application_create.candidate_id,
        )
        if existing_application is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Candidate already applied to this job",
            )

        application = await self.application_repo.create(application_create)
        return ApplicationResponse.model_validate(application)

    async def get_application(self, application_id: uuid.UUID) -> ApplicationResponse:
        application = await self.application_repo.get_by_id(application_id)
        if application is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Application not found",
            )

        return ApplicationResponse.model_validate(application)

    async def list_applications(
        self,
        candidate_id: uuid.UUID | None = None,
        job_id: uuid.UUID | None = None,
    ) -> list[ApplicationResponse]:
        if candidate_id is not None and job_id is not None:
            application = await self.application_repo.get_by_job_and_candidate(job_id, candidate_id)
            applications = [] if application is None else [application]
        elif candidate_id is not None:
            applications = await self.application_repo.list_by_candidate(candidate_id)
        elif job_id is not None:
            applications = await self.application_repo.list_by_job(job_id)
        else:
            applications = await self.application_repo.list_all()

        return [ApplicationResponse.model_validate(application) for application in applications]