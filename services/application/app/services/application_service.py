from __future__ import annotations

import uuid

from sqlalchemy.exc import IntegrityError

from app.clients.job_client import JobClient
from app.core.application_states import ApplicationStatus, is_valid_app_transition
from app.core.config import Settings
from app.repositories.application_repo import ApplicationRepository
from app.schemas.application import (
    ApplicationCreate,
    ApplicationResponse,
    EligibilityReasonCode,
)
from app.services.eligibility_service import EligibilityService
from auth.actors import require_candidate_user_id, require_recruiter_user_id
from auth.header_auth import CurrentUser
from contracts.service_responses import JobResponseContract
from db.base import is_unique_violation
from exceptions.http_exceptions import (
    BadRequestError,
    ConflictError,
    ForbiddenError,
    InvalidStateTransitionError,
    NotFoundError,
)


class ApplicationService:
    def __init__(
        self,
        application_repo: ApplicationRepository,
        job_client: JobClient,
        eligibility_service: EligibilityService,
        settings: Settings,
    ) -> None:
        self.application_repo = application_repo
        self.job_client = job_client
        self.eligibility_service = eligibility_service
        self.settings = settings

    async def apply_to_job(
        self,
        application_create: ApplicationCreate,
        current_user: CurrentUser,
    ) -> ApplicationResponse:
        candidate_id = require_candidate_user_id(current_user)

        eligibility = await self.eligibility_service.check_eligibility(
            candidate_id,
            application_create.job_id,
            current_user,
        )
        if not eligibility.is_eligible:
            if eligibility.reason_code == EligibilityReasonCode.DUPLICATE_APPLICATION:
                raise ConflictError(eligibility.reason)
            raise BadRequestError(
                f"Not eligible: {eligibility.reason}",
                detail={
                    "reason_code": eligibility.reason_code.value,
                    "match_score": eligibility.match_score,
                    "missing_skills": eligibility.missing_skills,
                },
            )

        try:
            application = await self.application_repo.create(
                application_create,
                candidate_id=candidate_id,
                status=ApplicationStatus.PENDING,
                eligibility_result=eligibility,
                resume_id=eligibility.resume_id,
            )
        except IntegrityError as exc:
            if is_unique_violation(exc):
                raise ConflictError("You have already applied to this job") from exc
            raise

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
            candidate_id = require_candidate_user_id(current_user)
        else:
            recruiter_id = require_recruiter_user_id(current_user)
            if candidate_id is not None and job_id is None:
                raise BadRequestError(
                    "Recruiters must provide job_id when filtering by candidate_id"
                )
            if job_id is not None:
                await self._get_job_owned_by_recruiter(
                    job_id,
                    recruiter_id,
                    current_user,
                    forbidden_message="Not authorized to view applications for this job",
                )

        if candidate_id is not None and job_id is not None:
            application = await self.application_repo.get_by_job_and_candidate(
                job_id, candidate_id
            )
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
        else:
            recruiter_jobs = await self.job_client.list_by_recruiter(
                recruiter_id, current_user
            )
            job_ids = [job.id for job in recruiter_jobs]
            applications = await self.application_repo.list_by_job_ids(
                job_ids,
                status_filter=status_filter,
                limit=limit,
                offset=offset,
            )

        return [
            ApplicationResponse.model_validate(application)
            for application in applications
        ]

    async def update_application_status(
        self,
        application_id: uuid.UUID,
        new_status: ApplicationStatus,
        current_user: CurrentUser,
    ) -> ApplicationResponse:
        recruiter_id = require_recruiter_user_id(current_user)
        application = await self.application_repo.get_by_id(application_id)
        if application is None:
            raise NotFoundError("Application not found")

        await self._get_job_owned_by_recruiter(
            application.job_id,
            recruiter_id,
            current_user,
            forbidden_message="Not authorized to update this application",
        )

        current_status = ApplicationStatus(application.status)
        if current_status == new_status:
            return ApplicationResponse.model_validate(application)
        if not is_valid_app_transition(current_status, new_status):
            raise InvalidStateTransitionError(
                f"Cannot transition application from '{current_status.value}' to '{new_status.value}'"
            )

        updated_application = await self.application_repo.update_status(
            application,
            status=new_status,
            changed_by_user_id=recruiter_id,
            changed_by_role=current_user.role,
        )
        return ApplicationResponse.model_validate(updated_application)

    async def delete_applications(
        self,
        *,
        job_id: uuid.UUID | None,
        candidate_id: uuid.UUID | None,
        current_user: CurrentUser,
    ) -> None:
        if (job_id is None) == (candidate_id is None):
            raise BadRequestError("Provide exactly one of job_id or candidate_id")

        if job_id is not None:
            recruiter_id = require_recruiter_user_id(current_user)
            await self._get_job_owned_by_recruiter(
                job_id,
                recruiter_id,
                current_user,
                forbidden_message="Not authorized to delete applications for this job",
            )
            await self.application_repo.delete_by_job(job_id)
            return

        owner_id = require_candidate_user_id(current_user)
        if owner_id != candidate_id:
            raise ForbiddenError(
                "Not authorized to delete another candidate's applications"
            )
        await self.application_repo.delete_by_candidate(candidate_id)

    async def _authorize_application_access(
        self,
        application,
        current_user: CurrentUser,
    ) -> None:
        if current_user.role == "CANDIDATE":
            candidate_id = require_candidate_user_id(current_user)
            if application.candidate_id != candidate_id:
                raise NotFoundError("Application not found")
            return

        recruiter_id = require_recruiter_user_id(current_user)
        try:
            await self._get_job_owned_by_recruiter(
                application.job_id,
                recruiter_id,
                current_user,
                forbidden_message="Not authorized to view this application",
            )
        except ForbiddenError as exc:
            raise NotFoundError("Application not found") from exc

    async def _get_job_owned_by_recruiter(
        self,
        job_id: uuid.UUID,
        recruiter_id: uuid.UUID,
        current_user: CurrentUser,
        *,
        forbidden_message: str,
    ) -> JobResponseContract:
        job = await self.job_client.get_job(job_id, current_user)
        if job is None:
            raise NotFoundError("Job not found")
        if job.recruiter_id != recruiter_id:
            raise ForbiddenError(forbidden_message)
        return job

    @staticmethod
    def _filter_single_application(application, status_filter: str | None) -> list:
        if application is None:
            return []
        if status_filter is not None and application.status != status_filter:
            return []
        return [application]
