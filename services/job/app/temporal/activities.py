from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from temporalio import activity

from app.clients.application_client import ApplicationClient
from app.clients.recruiter_client import RecruiterClient
from app.core.config import get_settings
from app.core.enums import JobStatus
from app.db.session import SessionLocal
from app.repositories.job_repo import JobRepository
from app.services.job_service import JobService
from app.temporal.constants import (
    ACTIVITY_FINALIZE_JOB_BREAKDOWN,
    ACTIVITY_MARK_JOB_READY,
)
from exceptions.http_exceptions import (
    BadRequestError,
    ConflictError,
    ForbiddenError,
    InvalidStateTransitionError,
    NotFoundError,
    PayloadTooLargeError,
)
from temporal.activity_runner import run_temporal_activity
from temporal.schemas import JobStatusActivityResult

_NON_RETRYABLE_ERRORS = (
    BadRequestError,
    ForbiddenError,
    NotFoundError,
    ConflictError,
    PayloadTooLargeError,
    InvalidStateTransitionError,
)


async def _run_job_service_operation(
    operation: Callable[[JobService], Awaitable[Any]],
) -> Any:
    settings = get_settings()
    recruiter_client = RecruiterClient(settings)
    application_client = ApplicationClient(settings)
    return await run_temporal_activity(
        session_factory=SessionLocal,
        build_service=lambda session: JobService(
            job_repo=JobRepository(session),
            settings=settings,
            recruiter_client=recruiter_client,
            application_client=application_client,
        ),
        operation=operation,
        non_retryable_errors=_NON_RETRYABLE_ERRORS,
        clients=[recruiter_client, application_client],
        serialize_result=_serialize_result,
    )


@activity.defn(name=ACTIVITY_FINALIZE_JOB_BREAKDOWN)
async def finalize_job_breakdown(job_id: str) -> dict[str, Any]:
    parsed_job_id = uuid.UUID(job_id)
    activity.logger.info("Finalizing job breakdown", extra={"job_id": job_id})
    return await _run_job_service_operation(
        lambda service: service.finalize_job_breakdown(parsed_job_id),
    )


@activity.defn(name=ACTIVITY_MARK_JOB_READY)
async def mark_job_ready(job_id: str) -> dict[str, Any]:
    parsed_job_id = uuid.UUID(job_id)
    activity.logger.info("Marking job ready", extra={"job_id": job_id})

    async def _mark_ready(service: JobService) -> dict[str, Any]:
        job = await service.update_job_status(parsed_job_id, JobStatus.READY)
        return JobStatusActivityResult(job_id=job.id, status=job.status).model_dump(
            mode="json"
        )

    return await _run_job_service_operation(_mark_ready)


def _serialize_result(result: Any) -> Any:
    if hasattr(result, "model_dump"):
        return result.model_dump(mode="json")
    return result
