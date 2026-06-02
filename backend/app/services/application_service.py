from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from datetime import timedelta
from pathlib import Path
from typing import Any

from app.core.auth import CurrentUser
from app.core.application_states import ApplicationStatus, is_valid_app_transition
from app.core.config import Settings
from app.core.metrics import queue_applications_received_increment, queue_workflow_duration
from app.core.tracing import build_event_context
from app.db.models import Application, CandidateResume
from app.repositories.application_repo import ApplicationRepository
from app.repositories.candidate_repo import CandidateRepository
from app.repositories.candidate_resume_repo import CandidateResumeRepository
from app.repositories.job_repo import JobRepository
from app.repositories.outbox_repo import OutboxRepository
from app.events.schemas import ApplicationReceivedEvent
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
    _RESUME_PARSER_VERSION = "resume_pdf.v1"
    _RESUME_SCHEMA_VERSION = "resume_profile.v1"

    def __init__(
        self,
        application_repo: ApplicationRepository,
        job_repo: JobRepository,
        candidate_repo: CandidateRepository,
        candidate_resume_repo: CandidateResumeRepository,
        outbox_repo: OutboxRepository,
        eligibility_service: EligibilityService,
        settings: Settings,
    ) -> None:
        self.application_repo = application_repo
        self.job_repo = job_repo
        self.candidate_repo = candidate_repo
        self.candidate_resume_repo = candidate_resume_repo
        self.outbox_repo = outbox_repo
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

        submission_eligibility = await self.eligibility_service.check_submission_eligibility(
            candidate_id,
            application_create.job_id,
        )
        if not submission_eligibility.is_eligible:
            if submission_eligibility.reason == "You have already applied to this job":
                raise ConflictError(submission_eligibility.reason)
            raise BadRequestError(f"Not eligible: {submission_eligibility.reason}")

        application = await self.application_repo.create(
            application_create,
            candidate_id=candidate_id,
            status=ApplicationStatus.PENDING,
            eligibility_result=submission_eligibility.model_dump(),
        )

        workflow_id = self._build_application_workflow_id(application.id)
        await self._create_application_received_event(
            application,
            current_user=current_user,
            workflow_id=workflow_id,
        )
        queue_applications_received_increment(self.application_repo.session)
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
            changed_by_user_id=recruiter_id,
            changed_by_role=current_user.role,
        )
        return ApplicationResponse.model_validate(updated_application)

    async def initialize_application_workflow_state(self, application_id: uuid.UUID) -> dict[str, Any]:
        application = await self.application_repo.get_by_id(application_id)
        if application is None:
            raise NotFoundError("Application not found")

        workflow_section = {
            "initialized": True,
            "state": "initialized",
        }
        application = await self.application_repo.set_workflow_tracking(
            application,
            workflow_initialized_at=datetime.now(timezone.utc),
            workflow_failed_at=None,
            workflow_error=None,
        )
        updated_application = await self.application_repo.update_metadata_section(
            application,
            section_name="workflow",
            section_value=workflow_section,
        )
        if "resume_parsing" not in updated_application.application_metadata:
            updated_application = await self.application_repo.update_metadata_section(
                updated_application,
                section_name="resume_parsing",
                section_value={
                    "status": "pending_upload",
                    "error": None,
                },
            )
        if updated_application.workflow_initialized_at is not None:
            queue_workflow_duration(
                self.application_repo.session,
                workflow_name="candidate_application_initialization",
                status="success",
                duration_seconds=max(
                    (updated_application.workflow_initialized_at - updated_application.created_at).total_seconds(),
                    0.0,
                ),
            )
        return {
            "application_id": str(updated_application.id),
            "status": updated_application.status,
        }

    async def process_uploaded_resume(self, application_id: uuid.UUID) -> dict[str, Any]:
        application = await self.application_repo.get_by_id(application_id)
        if application is None:
            raise NotFoundError("Application not found")

        resume_metadata = dict(application.application_metadata.get("resume_parsing", {}))
        resume = application.resume

        if resume is None:
            resume_metadata.update({
                "status": "pending_upload",
                "error": None,
            })
            await self.application_repo.update_metadata_section(
                application,
                section_name="resume_parsing",
                section_value=resume_metadata,
            )
            return {
                "application_id": str(application.id),
                "resume_parsing_status": resume_metadata["status"],
            }

        if resume.content_type != "application/pdf":
            resume_metadata.update({
                "status": "unsupported",
                "error": "Resume parsing currently supports PDF uploads only",
            })
            await self._update_resume_record(
                resume,
                parsing_status="unsupported",
                parsing_error=resume_metadata["error"],
                parsed_at=None,
                raw_markdown=None,
                structured_data=None,
            )
            await self.application_repo.update_metadata_section(
                application,
                section_name="resume_parsing",
                section_value=resume_metadata,
            )
            return {
                "application_id": str(application.id),
                "resume_parsing_status": resume_metadata["status"],
            }

        resume_metadata.update({
            "status": "processing",
            "error": None,
        })
        await self.application_repo.update_metadata_section(
            application,
            section_name="resume_parsing",
            section_value=resume_metadata,
        )

        if resume.storage_path is None:
            resume_metadata.update({
                "status": "failed",
                "error": "Resume storage path is missing",
            })
            await self._update_resume_record(
                resume,
                parsing_status="failed",
                parsing_error=resume_metadata["error"],
                parsed_at=None,
                raw_markdown=None,
                structured_data=None,
            )
            await self.application_repo.update_metadata_section(
                application,
                section_name="resume_parsing",
                section_value=resume_metadata,
            )
            return {
                "application_id": str(application.id),
                "resume_parsing_status": resume_metadata["status"],
            }

        resume_path = Path(resume.storage_path)
        if not resume_path.exists():
            resume_metadata.update({
                "status": "failed",
                "error": "Uploaded resume file is no longer available",
            })
            await self._update_resume_record(
                resume,
                parsing_status="failed",
                parsing_error=resume_metadata["error"],
                parsed_at=None,
                raw_markdown=None,
                structured_data=None,
            )
            await self.application_repo.update_metadata_section(
                application,
                section_name="resume_parsing",
                section_value=resume_metadata,
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
            await self._update_resume_record(
                resume,
                parsing_status="failed",
                parsing_error=resume_metadata["error"],
                parsed_at=None,
                raw_markdown=None,
                structured_data=None,
            )
            await self.application_repo.update_metadata_section(
                application,
                section_name="resume_parsing",
                section_value=resume_metadata,
            )
            return {
                "application_id": str(application.id),
                "resume_parsing_status": resume_metadata["status"],
            }

        parsed_at = datetime.now(timezone.utc)
        resume_metadata.update({
            "status": "parsed",
            "error": None,
            "parsed_at": parsed_at.isoformat(),
        })
        await self._update_resume_record(
            resume,
            parsing_status="parsed",
            parsing_error=None,
            parsed_at=parsed_at,
            raw_markdown=markdown,
            structured_data=parsed_resume,
        )
        updated_application = await self.application_repo.update_metadata_section(
            application,
            section_name="resume_parsing",
            section_value=resume_metadata,
        )
        eligibility_result = await self.eligibility_service.check_eligibility(
            updated_application.candidate_id,
            updated_application.job_id,
        )
        updated_application = await self.application_repo.update_eligibility_result(
            updated_application,
            eligibility_result=eligibility_result.model_dump(),
        )
        await self._enqueue_scoring_task(updated_application)
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

        resume_id = uuid.uuid4()
        stored_file_name = f"{resume_id}{suffix}"
        file_path = upload_dir / stored_file_name

        await asyncio.to_thread(file_path.write_bytes, file_bytes)

        uploaded_at = datetime.now(timezone.utc)
        resume = await self.candidate_resume_repo.create(
            resume_id=resume_id,
            candidate_id=candidate_id,
            source_application_id=application.id,
            file_name=sanitized_name,
            content_type=content_type,
            storage_path=file_path.as_posix(),
            uploaded_at=uploaded_at,
            parsing_status="pending",
            parser_version=self._RESUME_PARSER_VERSION,
            schema_version=self._RESUME_SCHEMA_VERSION,
            extraction_metadata={
                "source": "application_upload",
                "application_id": str(application.id),
            },
        )
        updated_application = await self.application_repo.attach_resume(
            application,
            resume=resume,
        )

        updated_application = await self.application_repo.update_metadata_section(
            updated_application,
            section_name="resume_parsing",
            section_value={
            "status": "pending",
            "error": None,
            "uploaded_at": uploaded_at.isoformat(),
            "resume_id": str(resume.id),
        },
        )

        await self._start_resume_processing_workflow(updated_application.id, uploaded_at)

        return ApplicationResponse.model_validate(updated_application)

    async def get_background_task_context(self, application_id: uuid.UUID) -> dict[str, Any]:
        application = await self.application_repo.get_by_id(application_id)
        if application is None:
            raise NotFoundError("Application not found")

        job = await self.job_repo.get_by_id(application.job_id)
        if job is None:
            raise NotFoundError("Job not found")

        candidate = await self.candidate_repo.get_by_id(application.candidate_id)
        if candidate is None:
            raise NotFoundError("Candidate not found")

        latest_resume = await self.candidate_resume_repo.get_latest_parsed_for_candidate(candidate.id)

        return {
            "application_id": str(application.id),
            "candidate_id": str(candidate.id),
            "job_id": str(job.id),
            "application_status": application.status,
            "eligibility_result": dict(application.eligibility_result or {}),
            "application_metadata": dict(application.application_metadata),
            "job_required_skills": list(job.required_skills or []),
            "candidate_master_profile": dict(candidate.master_profile_data or {}),
            "resume_structured_data": (
                dict(latest_resume.structured_data)
                if latest_resume is not None and latest_resume.structured_data is not None
                else None
            ),
        }

    async def record_scoring_result(
        self,
        application_id: uuid.UUID,
        *,
        scoring_result: dict[str, Any],
    ) -> dict[str, Any]:
        application = await self.application_repo.get_by_id(application_id)
        if application is None:
            raise NotFoundError("Application not found")

        updated_application = await self.application_repo.update_metadata_section(
            application,
            section_name="scoring",
            section_value=scoring_result,
        )
        return dict(updated_application.application_metadata)

    async def record_notification_result(
        self,
        application_id: uuid.UUID,
        *,
        notification_name: str,
        notification_result: dict[str, Any],
    ) -> dict[str, Any]:
        application = await self.application_repo.get_by_id(application_id)
        if application is None:
            raise NotFoundError("Application not found")

        notifications = dict(application.application_metadata.get("notifications", {}))
        notifications[notification_name] = notification_result
        updated_application = await self.application_repo.update_metadata_section(
            application,
            section_name="notifications",
            section_value=notifications,
        )
        return dict(updated_application.application_metadata)

    async def record_analytics_result(
        self,
        application_id: uuid.UUID,
        *,
        analytics_result: dict[str, Any],
    ) -> dict[str, Any]:
        application = await self.application_repo.get_by_id(application_id)
        if application is None:
            raise NotFoundError("Application not found")

        updated_application = await self.application_repo.update_metadata_section(
            application,
            section_name="analytics",
            section_value=analytics_result,
        )
        return dict(updated_application.application_metadata)

    async def _update_resume_record(
        self,
        resume: CandidateResume,
        *,
        parsing_status: str,
        parsing_error: str | None,
        parsed_at: datetime | None,
        raw_markdown: str | None,
        structured_data: dict[str, Any] | None,
    ) -> CandidateResume:
        extraction_metadata = dict(resume.extraction_metadata)
        extraction_metadata["last_processed_at"] = datetime.now(timezone.utc).isoformat()
        extraction_metadata["parser_version"] = self._RESUME_PARSER_VERSION
        extraction_metadata["schema_version"] = self._RESUME_SCHEMA_VERSION
        return await self.candidate_resume_repo.update_parsing_result(
            resume,
            parsing_status=parsing_status,
            parsing_error=parsing_error,
            parsed_at=parsed_at,
            raw_markdown=raw_markdown,
            structured_data=structured_data,
            extraction_metadata=extraction_metadata,
        )

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

    async def _create_application_received_event(
        self,
        application: Application,
        *,
        current_user: CurrentUser,
        workflow_id: str,
    ) -> None:
        event = ApplicationReceivedEvent(
            aggregate_id=application.id,
            application_id=application.id,
            job_id=application.job_id,
            candidate_id=application.candidate_id,
            status=application.status,
            workflow_id=workflow_id,
            context=build_event_context(
                correlation_id=workflow_id,
                user_id=current_user.id,
            ),
        )
        await self.outbox_repo.create_event(
            aggregate_type="application",
            aggregate_id=application.id,
            topic_name=self.settings.kafka_application_received_topic,
            event_type=event.event_type(),
            schema_version=event.schema_version,
            payload=event.payload(),
            headers=event.headers(),
            trace_context=event.trace_context(),
            idempotency_key=f"{event.event_type()}:{application.id}",
        )

    async def _enqueue_scoring_task(self, application: Application) -> None:
        from app.celery_app import celery_app
        from app.tasks import APPLICATION_SCORING_TASK

        workflow_id = application.workflow_id or self._build_application_workflow_id(application.id)
        event = ApplicationReceivedEvent(
            aggregate_id=application.id,
            application_id=application.id,
            job_id=application.job_id,
            candidate_id=application.candidate_id,
            status=application.status,
            workflow_id=workflow_id,
            context=build_event_context(
                correlation_id=workflow_id,
                user_id=str(application.candidate_id),
            ),
        )
        celery_app.send_task(
            APPLICATION_SCORING_TASK,
            kwargs={
                "payload": event.payload(),
                "headers": event.headers(),
            },
        )

    async def _start_application_workflow(self, application_id: uuid.UUID) -> None:
        workflow_id = self._build_application_workflow_id(application_id)
        application = await self.application_repo.get_by_id(application_id)
        if application is None:
            raise NotFoundError("Application not found")

        await self.application_repo.set_workflow_tracking(
            application,
            workflow_id=workflow_id,
        )

        client = await TemporalClient.get_client()
        from app.temporal.workflows import (
            CandidateApplicationWorkflow,
            CandidateApplicationWorkflowInput,
        )

        try:
            await client.start_workflow(
                CandidateApplicationWorkflow.run,
                CandidateApplicationWorkflowInput(application_id=str(application_id)),
                id=workflow_id,
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