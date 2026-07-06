from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from app.clients.application_client import ApplicationClient
from app.clients.recruiter_client import RecruiterClient
from app.core.config import Settings
from app.core.constants import STRUCTURED_JOB_METADATA_FIELDS
from app.core.enums import JobStatus, is_valid_transition
from app.repositories.job_repo import JobRepository
from app.schemas.job import (
    JobBreakdownValidationResponse,
    JobCreate,
    JobCreatePayload,
    JobResponse,
    JobUpdate,
    PublishJobResponse,
)
from app.services.job_breakdown_orchestrator import JobBreakdownOrchestrator
from app.services.job_file_service import JobFileService
from app.temporal.client import TemporalClient
from app.temporal.workflows import JobPublishingInput, JobPublishingWorkflow
from auth.actors import require_recruiter_user_id
from auth.header_auth import CurrentUser
from exceptions.http_exceptions import (
    BadRequestError,
    ForbiddenError,
    InvalidStateTransitionError,
    NotFoundError,
)
from temporal.workflow_launcher import start_workflow_with_retryable_error_mapping


logger = logging.getLogger(__name__)


class JobService:
    def __init__(
        self,
        job_repo: JobRepository,
        settings: Settings,
        recruiter_client: RecruiterClient,
        application_client: ApplicationClient,
    ) -> None:
        self.job_repo = job_repo
        self.settings = settings
        self.recruiter_client = recruiter_client
        self.application_client = application_client
        self.breakdown_orchestrator = JobBreakdownOrchestrator(job_repo)
        self.file_service = JobFileService(settings)

    async def create_job(self, job_create: JobCreate, current_user: CurrentUser) -> JobResponse:
        recruiter_id = require_recruiter_user_id(current_user)

        recruiter = await self.recruiter_client.get_recruiter(recruiter_id, current_user)
        if recruiter is None:
            raise NotFoundError("Recruiter not found")

        breakdown_fields = await self.breakdown_orchestrator.build_breakdown_fields(
            title=job_create.title,
            description=job_create.description,
            required_skills=job_create.required_skills,
            overrides=job_create.model_dump(
                exclude={"title", "description", "required_skills"},
                exclude_none=True,
            ),
        )
        job_data = JobCreatePayload.model_validate(
            {
                **job_create.model_dump(mode="json"),
                **breakdown_fields.model_dump(mode="json"),
                "jd_source_type": "manual_text" if job_create.description else None,
            }
        )
        job = await self.job_repo.create(
            job_data.model_dump(mode="json"),
            recruiter_id=recruiter_id,
            changed_by_role=current_user.role,
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
        owner_id = require_recruiter_user_id(current_user)
        existing_job = await self.job_repo.get_by_id(job_id)
        if existing_job is None:
            raise NotFoundError("Job not found")
        if existing_job.recruiter_id != owner_id:
            raise ForbiddenError("Not authorized to update this job")

        updates = job_update.model_dump(exclude_unset=True)
        needs_rebuild = "description" in updates or ("title" in updates and existing_job.description is not None)
        if needs_rebuild and existing_job.status != JobStatus.DRAFT.value:
            raise BadRequestError(
                "Job description can only be edited while the job is in draft status"
            )
        if needs_rebuild:
            effective_title = updates.get("title", existing_job.title)
            effective_description = updates.get("description", existing_job.description)
            effective_required_skills = (
                updates["required_skills"]
                if "required_skills" in updates and updates["required_skills"] is not None
                else existing_job.required_skills
            )
            breakdown_fields = await self.breakdown_orchestrator.build_breakdown_fields(
                title=effective_title,
                description=effective_description,
                required_skills=effective_required_skills,
                overrides={
                    field_name: value
                    for field_name, value in updates.items()
                    if field_name in STRUCTURED_JOB_METADATA_FIELDS and value is not None
                },
            )
            if "description" in updates and updates["description"] is not None:
                updates["jd_source_type"] = "manual_text"
            updates["jd_parsing_status"] = breakdown_fields.jd_parsing_status
            updates["jd_parsing_error"] = breakdown_fields.jd_parsing_error
            updates["description_breakdown"] = (
                breakdown_fields.description_breakdown.model_dump(mode="json")
                if breakdown_fields.description_breakdown is not None
                else None
            )
            updates["employment_type"] = breakdown_fields.employment_type
            updates["seniority_level"] = breakdown_fields.seniority_level
            updates["department"] = breakdown_fields.department
            updates["job_category"] = breakdown_fields.job_category
            updates["location"] = (
                breakdown_fields.location.model_dump(mode="json")
                if breakdown_fields.location is not None
                else None
            )
            updates["compensation"] = (
                breakdown_fields.compensation.model_dump(mode="json")
                if breakdown_fields.compensation is not None
                else None
            )
            updates["years_of_experience_required"] = breakdown_fields.years_of_experience_required
            updates["application_deadline"] = breakdown_fields.application_deadline
            updates["required_skills"] = breakdown_fields.required_skills
            if existing_job.status == JobStatus.DRAFT.value:
                updates["status"] = breakdown_fields.status

        if "status" in updates:
            try:
                current_status = JobStatus(existing_job.status)
                target_status = JobStatus(updates["status"])
            except ValueError as exc:
                raise BadRequestError("Invalid job status") from exc

            if current_status != target_status and not is_valid_transition(
                current_status, target_status
            ):
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
        owner_id = require_recruiter_user_id(current_user)

        sanitized_name = await self.file_service.validate_pdf_upload(
            file_name=file_name,
            content_type=content_type,
            file_bytes=file_bytes,
        )

        job = await self.job_repo.get_by_id(job_id)
        if job is None:
            raise NotFoundError("Job not found")

        if job.recruiter_id != owner_id:
            raise ForbiddenError("Not authorized to modify this job")

        if job.status != JobStatus.DRAFT.value:
            raise BadRequestError("Job description files can only be uploaded while the job is in draft")

        previous_storage_path = job.jd_storage_path
        storage_path = await self.file_service.write_job_pdf(job_id=job.id, file_bytes=file_bytes)

        updated_job = None
        try:
            uploaded_at = datetime.now(timezone.utc)
            updated_job = await self.job_repo.attach_job_description_file(
                job,
                file_name=sanitized_name,
                content_type=content_type,
                storage_path=storage_path,
                uploaded_at=uploaded_at,
            )
        except Exception:
            try:
                await self.file_service.remove_if_exists(storage_path)
            except Exception:
                logger.exception(
                    "Failed to clean up orphaned job description file after a failed upload",
                    extra={"job_id": str(job.id), "storage_path": storage_path},
                )
            raise

        if previous_storage_path and previous_storage_path != storage_path:
            await self.file_service.remove_if_exists(previous_storage_path)

        return JobResponse.model_validate(updated_job)

    async def delete_job(self, job_id: uuid.UUID, current_user: CurrentUser) -> None:
        owner_id = require_recruiter_user_id(current_user)
        existing_job = await self.job_repo.get_by_id(job_id)
        if existing_job is None:
            raise NotFoundError("Job not found")
        if existing_job.recruiter_id != owner_id:
            raise ForbiddenError("Not authorized to delete this job")

        await self.application_client.delete_applications_for_job(job_id, current_user)

        was_deleted = await self.job_repo.delete(job_id)
        if not was_deleted:
            raise NotFoundError("Job not found")

        try:
            await self.file_service.remove_if_exists(existing_job.jd_storage_path)
        except Exception:
            logger.exception(
                "Failed to remove job description file after deleting job",
                extra={"job_id": str(job_id), "storage_path": existing_job.jd_storage_path},
            )

    async def publish_job(self, job_id: uuid.UUID, current_user: CurrentUser) -> PublishJobResponse:
        owner_id = require_recruiter_user_id(current_user)
        job = await self.job_repo.get_by_id(job_id)
        if job is None:
            raise NotFoundError("Job not found")
        if job.recruiter_id != owner_id:
            raise ForbiddenError("Not authorized to publish this job")

        self._ensure_publishable(job)

        updated_job = job
        workflow_id = self._build_publish_workflow_id(job_id)
        if job.status == JobStatus.DRAFT.value:
            processing_updates: dict[str, Any] = {}
            if job.jd_source_type == "pdf_upload" and job.jd_parsing_status == "pending":
                processing_updates["jd_parsing_status"] = "processing"
                processing_updates["jd_parsing_error"] = None
            updated_job = await self.job_repo.update_status(
                job,
                status=JobStatus.PROCESSING,
                changed_by_user_id=owner_id,
                changed_by_role=current_user.role,
            )
            if processing_updates:
                updated_job = await self.job_repo.update(job_id, processing_updates)
                if updated_job is None:
                    raise NotFoundError("Job not found")

        updated_job = await self.job_repo.set_publishing_workflow(
            updated_job,
            workflow_id=workflow_id,
        )

        client = await TemporalClient.get_client()

        await start_workflow_with_retryable_error_mapping(
            client=client,
            workflow=JobPublishingWorkflow.run,
            workflow_input=JobPublishingInput(job_id=str(job_id)),
            workflow_id=workflow_id,
            task_queue=self.settings.temporal_job_task_queue,
            execution_timeout=timedelta(minutes=5),
            logger=logger,
            context={"job_id": str(job_id), "workflow_id": workflow_id},
            conflict_log_message="Job publishing workflow already started",
            failure_log_message="Failed to start job publishing workflow",
            unavailable_message="Temporal workflow service is unavailable",
        )

        return PublishJobResponse(
            job_id=job_id,
            workflow_id=workflow_id,
            status=updated_job.status,
        )

    async def finalize_job_breakdown(self, job_id: uuid.UUID) -> JobBreakdownValidationResponse:
        job = await self.job_repo.get_by_id(job_id)
        if job is None:
            raise NotFoundError("Job not found")

        self._ensure_publishable(job)

        if job.description_breakdown is None and not job.description and job.jd_source_type != "pdf_upload":
            raise BadRequestError("Job has no description content to publish")

        job = await self.breakdown_orchestrator.finalize_for_publish(job)

        if job.description_breakdown is None:
            return JobBreakdownValidationResponse(
                job_id=job.id,
                breakdown_validated=False,
                jd_parsing_status=job.jd_parsing_status,
            )

        return JobBreakdownValidationResponse(
            job_id=job.id,
            breakdown_validated=self.breakdown_orchestrator.is_breakdown_complete(job.description_breakdown),
            jd_parsing_status=job.jd_parsing_status,
        )

    async def update_job_status(self, job_id: uuid.UUID, target_status: JobStatus) -> JobResponse:
        job = await self.job_repo.get_by_id(job_id)
        if job is None:
            raise NotFoundError("Job not found")

        current_status = JobStatus(job.status)
        if current_status == target_status:
            return JobResponse.model_validate(job)

        if not is_valid_transition(current_status, target_status):
            raise InvalidStateTransitionError(
                f"Invalid job state transition from '{job.status}' to '{target_status.value}'"
            )

        updated_job = await self.job_repo.update_status(
            job,
            status=target_status,
            changed_by_role="SYSTEM",
        )

        return JobResponse.model_validate(updated_job)

    @staticmethod
    def _build_publish_workflow_id(job_id: uuid.UUID) -> str:
        return f"job-publishing-{job_id}"

    @staticmethod
    def _ensure_publishable(job: Any) -> None:
        if job.status == JobStatus.READY.value:
            raise BadRequestError("Job is already ready")
        if job.status == JobStatus.ARCHIVED.value:
            raise BadRequestError("Archived jobs cannot be published")
        if job.status not in {JobStatus.DRAFT.value, JobStatus.PROCESSING.value}:
            raise BadRequestError("Job is not in a publishable state")
        if job.jd_source_type == "pdf_upload":
            if not job.jd_storage_path:
                raise BadRequestError("Uploaded job description file is missing")
            return
        if job.description or job.description_breakdown:
            return
        raise BadRequestError("Job must have a manual description or uploaded PDF before publishing")
