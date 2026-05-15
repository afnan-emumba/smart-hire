from __future__ import annotations

import asyncio
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.core.auth import CurrentUser
from app.core.config import Settings
from app.repositories.application_repo import ApplicationRepository
from app.repositories.candidate_repo import CandidateRepository
from app.repositories.job_repo import JobRepository
from app.schemas.application import ApplicationCreate, ApplicationResponse
from app.services.exceptions import (
    BadRequestError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    PayloadTooLargeError,
)


class ApplicationService:
    def __init__(
        self,
        application_repo: ApplicationRepository,
        job_repo: JobRepository,
        candidate_repo: CandidateRepository,
        settings: Settings,
    ) -> None:
        self.application_repo = application_repo
        self.job_repo = job_repo
        self.candidate_repo = candidate_repo
        self.settings = settings

    async def apply_to_job(
        self,
        application_create: ApplicationCreate,
        current_user: CurrentUser,
    ) -> ApplicationResponse:
        if current_user.role != "CANDIDATE":
            raise ForbiddenError("Only candidates can apply to jobs")

        job = await self.job_repo.get_by_id(application_create.job_id)
        if job is None:
            raise NotFoundError("Job not found")

        if job.status != "published":
            raise BadRequestError("Can only apply to published jobs")

        try:
            candidate_id = uuid.UUID(current_user.id)
        except ValueError as exc:
            raise BadRequestError("X-User-ID must be a valid candidate UUID") from exc

        candidate = await self.candidate_repo.get_by_id(candidate_id)
        if candidate is None:
            raise NotFoundError("Candidate not found")

        existing_application = await self.application_repo.get_by_job_and_candidate(
            application_create.job_id,
            candidate_id,
        )
        if existing_application is not None:
            raise ConflictError("Candidate already applied to this job")

        application = await self.application_repo.create(
            application_create,
            candidate_id=candidate_id,
        )
        return ApplicationResponse.model_validate(application)

    async def get_application(
        self,
        application_id: uuid.UUID,
        current_user: CurrentUser,
    ) -> ApplicationResponse:
        application = await self.application_repo.get_by_id(application_id)
        if application is None:
            raise NotFoundError("Application not found")

        await self._authorize_application_access(application, current_user)

        return ApplicationResponse.model_validate(application)

    async def list_applications(
        self,
        current_user: CurrentUser,
        *,
        candidate_id: uuid.UUID | None = None,
        job_id: uuid.UUID | None = None,
        limit: int,
        offset: int,
    ) -> list[ApplicationResponse]:
        recruiter_id: uuid.UUID | None = None

        if current_user.role == "CANDIDATE":
            candidate_id = self._require_candidate_user_id(current_user)
        else:
            recruiter_id = self._require_recruiter_user_id(current_user)
            if candidate_id is not None and job_id is None:
                raise BadRequestError("Recruiters must provide job_id when filtering by candidate_id")
            if job_id is not None:
                job = await self.job_repo.get_by_id(job_id)
                if job is None:
                    raise NotFoundError("Job not found")
                if job.recruiter_id != recruiter_id:
                    raise ForbiddenError("Not authorized to view applications for this job")

        if candidate_id is not None and job_id is not None:
            application = await self.application_repo.get_by_job_and_candidate(job_id, candidate_id)
            applications = [] if application is None else [application]
        elif candidate_id is not None:
            applications = await self.application_repo.list_by_candidate(
                candidate_id,
                limit=limit,
                offset=offset,
            )
        elif job_id is not None:
            applications = await self.application_repo.list_by_job(
                job_id,
                limit=limit,
                offset=offset,
            )
        elif recruiter_id is not None:
            applications = await self.application_repo.list_by_recruiter(
                recruiter_id,
                limit=limit,
                offset=offset,
            )
        else:
            applications = await self.application_repo.list_all(limit=limit, offset=offset)

        return [ApplicationResponse.model_validate(application) for application in applications]

    async def upload_resume(
        self,
        application_id: uuid.UUID,
        *,
        file_name: str,
        content_type: str,
        file_bytes: bytes,
        current_user: CurrentUser,
    ) -> ApplicationResponse:
        if current_user.role != "CANDIDATE":
            raise ForbiddenError("Only candidates can upload resumes")

        candidate_id = self._require_candidate_user_id(current_user)

        if len(file_bytes) > self.settings.max_resume_size_bytes:
            raise PayloadTooLargeError("Resume file exceeds the configured size limit")

        if not file_bytes:
            raise BadRequestError("Resume file is empty")

        application = await self.application_repo.get_by_id(application_id)
        if application is None:
            raise NotFoundError("Application not found")

        if application.candidate_id != candidate_id:
            raise ForbiddenError("Not authorized to modify this application")

        if content_type not in {
            "application/pdf",
            "application/msword",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        }:
            raise BadRequestError("Unsupported resume file type")

        upload_dir = Path(self.settings.resume_upload_dir)
        await asyncio.to_thread(upload_dir.mkdir, parents=True, exist_ok=True)

        sanitized_name = Path(file_name).name
        suffix = Path(sanitized_name).suffix.lower()
        if not suffix:
            raise BadRequestError("Resume file must include an extension")

        stored_file_name = f"{application.id}{suffix}"
        file_path = upload_dir / stored_file_name
        previous_storage_path = application.resume_storage_path

        await asyncio.to_thread(file_path.write_bytes, file_bytes)

        uploaded_at = datetime.now(timezone.utc)
        updated_application = await self.application_repo.attach_resume(
            application,
            file_name=sanitized_name,
            content_type=content_type,
            storage_path=file_path.as_posix(),
            uploaded_at=uploaded_at,
        )

        if previous_storage_path and previous_storage_path != file_path.as_posix():
            previous_path = Path(previous_storage_path)
            if previous_path.exists():
                await asyncio.to_thread(os.remove, previous_path)

        return ApplicationResponse.model_validate(updated_application)

    async def _authorize_application_access(
        self,
        application,
        current_user: CurrentUser,
    ) -> None:
        if current_user.role == "CANDIDATE":
            candidate_id = self._require_candidate_user_id(current_user)
            if application.candidate_id != candidate_id:
                raise ForbiddenError("Not authorized to view this application")
            return

        recruiter_id = self._require_recruiter_user_id(current_user)
        job = await self.job_repo.get_by_id(application.job_id)
        if job is None:
            raise NotFoundError("Job not found")
        if job.recruiter_id != recruiter_id:
            raise ForbiddenError("Not authorized to view this application")

    @staticmethod
    def _require_candidate_user_id(current_user: CurrentUser) -> uuid.UUID:
        if current_user.role != "CANDIDATE":
            raise ForbiddenError("Only candidates can perform this action")

        try:
            return uuid.UUID(current_user.id)
        except ValueError as exc:
            raise BadRequestError("X-User-ID must be a valid candidate UUID") from exc

    @staticmethod
    def _require_recruiter_user_id(current_user: CurrentUser) -> uuid.UUID:
        if current_user.role != "RECRUITER":
            raise ForbiddenError("Only recruiters can perform this action")

        try:
            return uuid.UUID(current_user.id)
        except ValueError as exc:
            raise BadRequestError("X-User-ID must be a valid recruiter UUID") from exc