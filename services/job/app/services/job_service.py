from __future__ import annotations

import asyncio
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from temporalio.exceptions import WorkflowAlreadyStartedError

from app.clients.application_client import ApplicationClient
from app.clients.recruiter_client import RecruiterClient
from app.core.config import Settings
from app.core.constants import STRUCTURED_JOB_METADATA_FIELDS
from app.core.enums import JobStatus
from app.core.state_machine import StateMachine
from app.repositories.job_repo import JobRepository
from app.schemas.job import (
    JobBreakdownFields,
    JobBreakdownValidationResponse,
    JobCreate,
    JobCreatePayload,
    JobResponse,
    JobUpdate,
    PublishJobResponse,
)
from app.services.job_breakdown_service import JobBreakdownService
from app.temporal.client import TemporalClient
from app.utils.job_description_pdf import JobDescriptionPdfConverter
from auth.header_auth import CurrentUser
from exceptions.http_exceptions import (
    BadRequestError,
    ForbiddenError,
    InvalidStateTransitionError,
    NotFoundError,
    PayloadTooLargeError,
    ServiceUnavailableError,
)


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

    async def create_job(self, job_create: JobCreate, current_user: CurrentUser) -> JobResponse:
        if current_user.role != "RECRUITER":
            raise ForbiddenError("Only recruiters can create jobs")

        try:
            recruiter_id = uuid.UUID(current_user.id)
        except ValueError as exc:
            raise BadRequestError("X-User-ID must be a valid recruiter UUID") from exc

        recruiter = await self.recruiter_client.get_recruiter(recruiter_id, current_user)
        if recruiter is None:
            raise NotFoundError("Recruiter not found")

        breakdown_fields = await self._build_breakdown_fields(
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
        owner_id = self._require_recruiter_user_id(current_user)
        existing_job = await self.job_repo.get_by_id(job_id)
        if existing_job is None:
            raise NotFoundError("Job not found")
        if existing_job.recruiter_id != owner_id:
            raise ForbiddenError("Not authorized to update this job")

        updates = job_update.model_dump(exclude_unset=True)
        needs_rebuild = "description" in updates or ("title" in updates and existing_job.description is not None)
        if needs_rebuild:
            effective_title = updates.get("title", existing_job.title)
            effective_description = updates.get("description", existing_job.description)
            effective_required_skills = (
                updates["required_skills"]
                if "required_skills" in updates and updates["required_skills"] is not None
                else existing_job.required_skills
            )
            breakdown_fields = await self._build_breakdown_fields(
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

        await self.application_client.delete_applications_for_job(job_id, current_user)

        was_deleted = await self.job_repo.delete(job_id)
        if not was_deleted:
            raise NotFoundError("Job not found")

    async def publish_job(self, job_id: uuid.UUID, current_user: CurrentUser) -> PublishJobResponse:
        owner_id = self._require_recruiter_user_id(current_user)
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

        try:
            client = await TemporalClient.get_client()
            from app.temporal.workflows import JobPublishingInput, JobPublishingWorkflow

            await client.start_workflow(
                JobPublishingWorkflow.run,
                JobPublishingInput(job_id=str(job_id)),
                id=workflow_id,
                task_queue=self.settings.temporal_job_task_queue,
                execution_timeout=timedelta(minutes=5),
            )
        except WorkflowAlreadyStartedError:
            logger.info(
                "Job publishing workflow already started",
                extra={"job_id": str(job_id), "workflow_id": workflow_id},
            )
        except Exception as exc:
            logger.exception(
                "Failed to start job publishing workflow",
                extra={"job_id": str(job_id), "workflow_id": workflow_id},
            )
            raise ServiceUnavailableError("Temporal workflow service is unavailable") from exc

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

        if job.jd_source_type == "pdf_upload":
            job = await self._finalize_pdf_breakdown(job)
        elif job.description_breakdown is None:
            if not job.description:
                raise BadRequestError("Job has no description content to publish")

            extracted_profile = await JobBreakdownService.extract_job_profile(
                title=job.title,
                description=job.description,
            )
            breakdown = extracted_profile["breakdown"]
            job = await self.job_repo.set_job_description_parsing_result(
                job,
                description=job.description,
                description_breakdown=breakdown.model_dump(mode="json"),
                required_skills=self._merge_required_skills(
                    job.required_skills,
                    [skill.name for skill in breakdown.skills],
                ),
                parsing_status="parsed",
                parsing_error=None,
                structured_updates=self._build_structured_updates(extracted_profile),
            )

        if job.description_breakdown is None:
            return JobBreakdownValidationResponse(
                job_id=job.id,
                breakdown_validated=False,
                jd_parsing_status=job.jd_parsing_status,
            )

        return JobBreakdownValidationResponse(
            job_id=job.id,
            breakdown_validated=self._is_breakdown_complete(job.description_breakdown),
            jd_parsing_status=job.jd_parsing_status,
        )

    async def update_job_status(self, job_id: uuid.UUID, target_status: JobStatus) -> JobResponse:
        job = await self.job_repo.get_by_id(job_id)
        if job is None:
            raise NotFoundError("Job not found")

        current_status = JobStatus(job.status)
        if current_status == target_status:
            return JobResponse.model_validate(job)

        if not StateMachine.can_transition(current_status, target_status):
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
    def _require_recruiter_user_id(current_user: CurrentUser) -> uuid.UUID:
        if current_user.role != "RECRUITER":
            raise ForbiddenError("Only recruiters can perform this action")

        try:
            return uuid.UUID(current_user.id)
        except ValueError as exc:
            raise BadRequestError("X-User-ID must be a valid recruiter UUID") from exc

    @staticmethod
    def _build_publish_workflow_id(job_id: uuid.UUID) -> str:
        return f"job-publishing-{job_id}"

    @staticmethod
    def _is_breakdown_complete(description_breakdown: dict[str, Any]) -> bool:
        skills = description_breakdown.get("skills") or []
        technologies = description_breakdown.get("technologies") or []
        responsibilities = description_breakdown.get("responsibilities") or []
        requirements = description_breakdown.get("requirements") or {}
        must_haves = requirements.get("must_haves") or []
        nice_to_haves = requirements.get("nice_to_haves") or []
        overview = description_breakdown.get("overview")
        return bool(skills or technologies or responsibilities or must_haves or nice_to_haves or overview)

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

    async def _finalize_pdf_breakdown(self, job: Any):
        try:
            file_bytes = await asyncio.to_thread(Path(job.jd_storage_path).read_bytes)
            description = JobDescriptionPdfConverter.convert_pdf_to_markdown(file_bytes)
            extracted_profile = await JobBreakdownService.extract_job_profile(
                title=job.title,
                description=description,
            )
            breakdown = extracted_profile["breakdown"]
        except Exception as exc:
            logger.exception(
                "Failed to finalize job description breakdown",
                extra={"job_id": str(job.id)},
            )
            failed_job = await self.job_repo.set_job_description_parsing_result(
                job,
                description=None,
                description_breakdown=None,
                required_skills=job.required_skills,
                parsing_status="failed",
                parsing_error=str(exc),
                structured_updates=self._empty_structured_updates(),
            )
            await self.job_repo.update(
                job.id,
                {
                    "publishing_failed_at": datetime.now(timezone.utc),
                    "publishing_error": str(exc),
                },
            )
            return failed_job

        return await self.job_repo.set_job_description_parsing_result(
            job,
            description=description,
            description_breakdown=breakdown.model_dump(mode="json"),
            required_skills=self._merge_required_skills(
                job.required_skills,
                [skill.name for skill in breakdown.skills],
            ),
            parsing_status="parsed",
            parsing_error=None,
            structured_updates=self._build_structured_updates(extracted_profile),
        )

    async def _build_breakdown_fields(
        self,
        *,
        title: str,
        description: str | None,
        required_skills: list[str],
        overrides: dict[str, Any] | None = None,
    ) -> JobBreakdownFields:
        override_values = dict(overrides or {})
        normalized_required_skills = self._merge_required_skills(required_skills, [])
        if not description:
            return JobBreakdownFields.model_validate(
                {
                    **self._empty_structured_updates(),
                    **override_values,
                    "description_breakdown": None,
                    "required_skills": normalized_required_skills,
                    "jd_parsing_status": "pending",
                    "jd_parsing_error": None,
                    "status": JobStatus.DRAFT.value,
                }
            )

        try:
            extracted_profile = await JobBreakdownService.extract_job_profile(
                title=title,
                description=description,
            )
            breakdown = extracted_profile["breakdown"]
        except Exception as exc:
            return JobBreakdownFields.model_validate(
                {
                    **self._empty_structured_updates(),
                    **override_values,
                    "description_breakdown": None,
                    "required_skills": normalized_required_skills,
                    "jd_parsing_status": "failed",
                    "jd_parsing_error": str(exc),
                    "status": JobStatus.DRAFT.value,
                }
            )

        extracted_skills = [skill.name for skill in breakdown.skills]
        return JobBreakdownFields.model_validate(
            {
                **self._build_structured_updates(extracted_profile),
                **override_values,
                "description_breakdown": breakdown.model_dump(mode="json"),
                "required_skills": self._merge_required_skills(required_skills, extracted_skills),
                "jd_parsing_status": "parsed",
                "jd_parsing_error": None,
                "status": JobStatus.DRAFT.value,
            }
        )

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

    @staticmethod
    def _empty_structured_updates() -> dict[str, Any]:
        return {field_name: None for field_name in STRUCTURED_JOB_METADATA_FIELDS}

    @classmethod
    def _build_structured_updates(cls, extracted_profile: dict[str, Any]) -> dict[str, Any]:
        return {
            "employment_type": extracted_profile.get("employment_type"),
            "seniority_level": extracted_profile.get("seniority_level"),
            "department": extracted_profile.get("department"),
            "job_category": extracted_profile.get("job_category"),
            "location": cls._dump_model(extracted_profile.get("location")),
            "compensation": cls._dump_model(extracted_profile.get("compensation")),
            "years_of_experience_required": extracted_profile.get("years_of_experience_required"),
            "application_deadline": extracted_profile.get("application_deadline"),
        }

    @staticmethod
    def _dump_model(value: Any) -> Any:
        if value is None:
            return None
        if hasattr(value, "model_dump"):
            return value.model_dump(mode="json")
        return value
