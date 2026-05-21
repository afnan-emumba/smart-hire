from __future__ import annotations

import asyncio
import os
import uuid
from datetime import datetime, timezone
from datetime import timedelta
from pathlib import Path
from typing import Any

from app.core.auth import CurrentUser
from app.core.application_states import ApplicationStatus, is_valid_app_transition
from app.core.config import Settings
from app.db.models import Application
from app.repositories.application_repo import ApplicationRepository
from app.repositories.candidate_repo import CandidateRepository
from app.repositories.job_repo import JobRepository
from app.schemas.application import ApplicationCreate, ApplicationResponse
from app.services.eligibility_service import EligibilityService
from app.services.resume_parsing_service import ResumeParsingService
from app.services.exceptions import (
    BadRequestError,
    ConflictError,
    ForbiddenError,
    InvalidStateTransition,
    NotFoundError,
    PayloadTooLargeError,
)
from app.temporal.client import TemporalClient
from app.utils.resume_pdf import ResumePdfConverter
from temporalio.exceptions import WorkflowAlreadyStartedError


class ApplicationService:
    def __init__(
        self,
        application_repo: ApplicationRepository,
        job_repo: JobRepository,
        candidate_repo: CandidateRepository,
        eligibility_service: EligibilityService,
        settings: Settings,
    ) -> None:
        self.application_repo = application_repo
        self.job_repo = job_repo
        self.candidate_repo = candidate_repo
        self.eligibility_service = eligibility_service
        self.settings = settings

    async def apply_to_job(
        self,
        application_create: ApplicationCreate,
        current_user: CurrentUser,
    ) -> ApplicationResponse:
        if current_user.role != "CANDIDATE":
            raise ForbiddenError("Only candidates can apply to jobs")

        try:
            candidate_id = uuid.UUID(current_user.id)
        except ValueError as exc:
            raise BadRequestError("X-User-ID must be a valid candidate UUID") from exc

        eligibility = await self.eligibility_service.check_eligibility(
            candidate_id,
            application_create.job_id,
        )
        if not eligibility.is_eligible:
            if eligibility.reason == "You have already applied to this job":
                raise ConflictError(eligibility.reason)
            raise BadRequestError(f"Not eligible: {eligibility.reason}")

        application = await self.application_repo.create(
            application_create,
            candidate_id=candidate_id,
            status=ApplicationStatus.PENDING,
        )

        await self._start_application_workflow(application.id)
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
        status: ApplicationStatus | None = None,
        limit: int,
        offset: int,
    ) -> list[ApplicationResponse]:
        recruiter_id: uuid.UUID | None = None
        status_filter = status.value if status is not None else None

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
            applications = self._filter_single_application(application, status_filter)
        elif candidate_id is not None:
            applications = await self.application_repo.list_by_candidate(
                candidate_id,
                status_filter=status_filter,
                limit=limit,
                offset=offset,
            )
        elif job_id is not None:
            applications = await self.application_repo.list_by_job(
                job_id,
                status_filter=status_filter,
                limit=limit,
                offset=offset,
            )
        elif recruiter_id is not None:
            applications = await self.application_repo.list_by_recruiter(
                recruiter_id,
                status_filter=status_filter,
                limit=limit,
                offset=offset,
            )
        else:
            applications = await self.application_repo.list_all(
                status_filter=status_filter,
                limit=limit,
                offset=offset,
            )

        return [ApplicationResponse.model_validate(application) for application in applications]

    async def update_application_status(
        self,
        application_id: uuid.UUID,
        new_status: ApplicationStatus,
        current_user: CurrentUser,
    ) -> ApplicationResponse:
        recruiter_id = self._require_recruiter_user_id(current_user)
        application = await self.application_repo.get_by_id(application_id)
        if application is None:
            raise NotFoundError("Application not found")

        job = await self.job_repo.get_by_id(application.job_id)
        if job is None:
            raise NotFoundError("Job not found")
        if job.recruiter_id != recruiter_id:
            raise ForbiddenError("Not authorized to update this application")

        current_status = ApplicationStatus(application.status)
        if current_status == new_status:
            return ApplicationResponse.model_validate(application)
        if not is_valid_app_transition(current_status, new_status):
            raise InvalidStateTransition(
                f"Cannot transition application from '{current_status.value}' to '{new_status.value}'"
            )

        updated_application = await self.application_repo.update_status(
            application,
            status=new_status,
        )
        return ApplicationResponse.model_validate(updated_application)

    async def initialize_application_workflow_state(self, application_id: uuid.UUID) -> dict[str, Any]:
        application = await self.application_repo.get_by_id(application_id)
        if application is None:
            raise NotFoundError("Application not found")

        workflow_metadata = dict(application.application_metadata)
        workflow_metadata["workflow"] = {
            "initialized": True,
            "state": "initialized",
        }
        if "resume_parsing" not in workflow_metadata:
            workflow_metadata["resume_parsing"] = {
                "status": "pending_upload",
                "error": None,
            }
        updated_application = await self.application_repo.update_metadata(
            application,
            metadata=workflow_metadata,
        )
        return {
            "application_id": str(updated_application.id),
            "status": updated_application.status,
        }

    async def process_uploaded_resume(self, application_id: uuid.UUID) -> dict[str, Any]:
        application = await self.application_repo.get_by_id(application_id)
        if application is None:
            raise NotFoundError("Application not found")

        workflow_metadata = dict(application.application_metadata)
        resume_metadata = dict(workflow_metadata.get("resume_parsing", {}))

        if application.resume_storage_path is None:
            resume_metadata.update({
                "status": "pending_upload",
                "error": None,
            })
            workflow_metadata["resume_parsing"] = resume_metadata
            await self.application_repo.update_resume_parsing(
                application,
                resume_data=application.resume_data,
                metadata=workflow_metadata,
            )
            return {
                "application_id": str(application.id),
                "resume_parsing_status": resume_metadata["status"],
            }

        if application.resume_content_type != "application/pdf":
            resume_metadata.update({
                "status": "unsupported",
                "error": "Resume parsing currently supports PDF uploads only",
            })
            workflow_metadata["resume_parsing"] = resume_metadata
            await self.application_repo.update_resume_parsing(
                application,
                resume_data=None,
                metadata=workflow_metadata,
            )
            return {
                "application_id": str(application.id),
                "resume_parsing_status": resume_metadata["status"],
            }

        resume_metadata.update({
            "status": "processing",
            "error": None,
        })
        workflow_metadata["resume_parsing"] = resume_metadata
        await self.application_repo.update_resume_parsing(
            application,
            resume_data=None,
            metadata=workflow_metadata,
        )

        resume_path = Path(application.resume_storage_path)
        if not resume_path.exists():
            resume_metadata.update({
                "status": "failed",
                "error": "Uploaded resume file is no longer available",
            })
            workflow_metadata["resume_parsing"] = resume_metadata
            await self.application_repo.update_resume_parsing(
                application,
                resume_data=None,
                metadata=workflow_metadata,
            )
            return {
                "application_id": str(application.id),
                "resume_parsing_status": resume_metadata["status"],
            }

        try:
            file_bytes = await asyncio.to_thread(resume_path.read_bytes)
            markdown = await asyncio.to_thread(ResumePdfConverter.convert_pdf_to_markdown, file_bytes)
            parsed_resume = await ResumeParsingService.extract_resume_profile(markdown)
        except ValueError as exc:
            resume_metadata.update({
                "status": "failed",
                "error": str(exc),
            })
            workflow_metadata["resume_parsing"] = resume_metadata
            await self.application_repo.update_resume_parsing(
                application,
                resume_data=None,
                metadata=workflow_metadata,
            )
            return {
                "application_id": str(application.id),
                "resume_parsing_status": resume_metadata["status"],
            }

        resume_metadata.update({
            "status": "parsed",
            "error": None,
            "parsed_at": datetime.now(timezone.utc).isoformat(),
        })
        workflow_metadata["resume_parsing"] = resume_metadata
        updated_application = await self.application_repo.update_resume_parsing(
            application,
            resume_data=parsed_resume,
            metadata=workflow_metadata,
        )
        return {
            "application_id": str(updated_application.id),
            "resume_parsing_status": resume_metadata["status"],
        }

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

        updated_metadata = dict(updated_application.application_metadata)
        updated_metadata["resume_parsing"] = {
            "status": "pending",
            "error": None,
            "uploaded_at": uploaded_at.isoformat(),
        }
        updated_application = await self.application_repo.update_resume_parsing(
            updated_application,
            resume_data=None,
            metadata=updated_metadata,
        )

        await self._start_resume_processing_workflow(updated_application.id, uploaded_at)

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

    async def _start_application_workflow(self, application_id: uuid.UUID) -> None:
        client = await TemporalClient.get_client()
        from app.temporal.workflows import (
            CandidateApplicationWorkflow,
            CandidateApplicationWorkflowInput,
        )

        try:
            await client.start_workflow(
                CandidateApplicationWorkflow.run,
                CandidateApplicationWorkflowInput(application_id=str(application_id)),
                id=self._build_application_workflow_id(application_id),
                task_queue=self.settings.temporal_application_task_queue,
                execution_timeout=timedelta(minutes=5),
            )
        except WorkflowAlreadyStartedError:
            pass

    async def _start_resume_processing_workflow(
        self,
        application_id: uuid.UUID,
        uploaded_at: datetime,
    ) -> None:
        client = await TemporalClient.get_client()
        from app.temporal.workflows import (
            CandidateApplicationWorkflow,
            CandidateApplicationWorkflowInput,
        )

        try:
            await client.start_workflow(
                CandidateApplicationWorkflow.run,
                CandidateApplicationWorkflowInput(
                    application_id=str(application_id),
                    parse_resume=True,
                ),
                id=self._build_resume_workflow_id(application_id, uploaded_at),
                task_queue=self.settings.temporal_application_task_queue,
                execution_timeout=timedelta(minutes=5),
            )
        except WorkflowAlreadyStartedError:
            pass

    @staticmethod
    def _build_application_workflow_id(application_id: uuid.UUID) -> str:
        return f"candidate-application:{application_id}"

    @staticmethod
    def _build_resume_workflow_id(application_id: uuid.UUID, uploaded_at: datetime) -> str:
        return f"candidate-application-resume:{application_id}:{int(uploaded_at.timestamp())}"

    @staticmethod
    def _filter_single_application(
        application: Application | None,
        status_filter: str | None,
    ) -> list[Application]:
        if application is None:
            return []
        if status_filter is not None and application.status != status_filter:
            return []
        return [application]

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