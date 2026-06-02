from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from temporalio import activity

from app.core.config import get_settings
from app.core.enums import JobStatus
from app.core.logging import bind_log_context, reset_log_context
from app.core.tracing import start_trace_span
from app.db.session import SessionLocal
from app.repositories.job_repo import JobRepository
from app.repositories.application_repo import ApplicationRepository
from app.repositories.candidate_repo import CandidateRepository
from app.repositories.candidate_resume_repo import CandidateResumeRepository
from app.repositories.recruiter_repo import RecruiterRepository
from app.repositories.outbox_repo import OutboxRepository
from app.services.application_service import ApplicationService
from app.services.eligibility_service import EligibilityService
from app.services.job_service import JobService


async def _run_job_service_operation(
    operation: Callable[[JobService], Awaitable[dict[str, Any]]],
) -> dict[str, Any]:
    async with SessionLocal() as session:
        service = JobService(
            job_repo=JobRepository(session),
            recruiter_repo=RecruiterRepository(session),
            outbox_repo=OutboxRepository(session),
            settings=get_settings(),
        )
        try:
            result = await operation(service)
            await session.commit()
            return result
        except Exception:
            await session.rollback()
            raise


async def _run_application_service_operation(
    operation: Callable[[ApplicationService], Awaitable[dict[str, Any]]],
) -> dict[str, Any]:
    async with SessionLocal() as session:
        application_repo = ApplicationRepository(session)
        candidate_repo = CandidateRepository(session)
        candidate_resume_repo = CandidateResumeRepository(session)
        job_repo = JobRepository(session)
        service = ApplicationService(
            application_repo=application_repo,
            job_repo=job_repo,
            candidate_repo=candidate_repo,
            candidate_resume_repo=candidate_resume_repo,
            outbox_repo=OutboxRepository(session),
            eligibility_service=EligibilityService(
                job_repo=job_repo,
                candidate_repo=candidate_repo,
                candidate_resume_repo=candidate_resume_repo,
                application_repo=application_repo,
                settings=get_settings(),
            ),
            settings=get_settings(),
        )
        try:
            result = await operation(service)
            await session.commit()
            return result
        except Exception:
            await session.rollback()
            raise


@activity.defn
async def finalize_job_breakdown(job_id: str) -> dict[str, Any]:
    parsed_job_id = uuid.UUID(job_id)
    tokens = bind_log_context(workflow_id=activity.info().workflow_id, correlation_id=activity.info().workflow_id)
    try:
        with start_trace_span(
            "temporal.activity.finalize_job_breakdown",
            attributes={"smarthire.job_id": job_id, "smarthire.workflow_id": activity.info().workflow_id},
        ):
            activity.logger.info("Finalizing job breakdown", extra={"job_id": job_id})
            return await _run_job_service_operation(
                lambda service: service.finalize_job_breakdown(parsed_job_id),
            )
    finally:
        reset_log_context(tokens)


@activity.defn
async def mark_job_ready(job_id: str) -> dict[str, Any]:
    parsed_job_id = uuid.UUID(job_id)
    tokens = bind_log_context(workflow_id=activity.info().workflow_id, correlation_id=activity.info().workflow_id)

    async def _mark_ready(service: JobService) -> dict[str, Any]:
        job = await service.update_job_status(parsed_job_id, JobStatus.READY)
        await service.record_job_published_event(parsed_job_id)
        return {
            "job_id": str(job.id),
            "status": job.status,
        }

    try:
        with start_trace_span(
            "temporal.activity.mark_job_ready",
            attributes={"smarthire.job_id": job_id, "smarthire.workflow_id": activity.info().workflow_id},
        ):
            activity.logger.info("Marking job ready", extra={"job_id": job_id})
            return await _run_job_service_operation(_mark_ready)
    finally:
        reset_log_context(tokens)


@activity.defn
async def initialize_application_processing(application_id: str) -> dict[str, Any]:
    parsed_application_id = uuid.UUID(application_id)
    tokens = bind_log_context(workflow_id=activity.info().workflow_id, correlation_id=activity.info().workflow_id)
    try:
        with start_trace_span(
            "temporal.activity.initialize_application_processing",
            attributes={
                "smarthire.application_id": application_id,
                "smarthire.workflow_id": activity.info().workflow_id,
            },
        ):
            activity.logger.info(
                "Initializing application workflow state",
                extra={"application_id": application_id},
            )
            return await _run_application_service_operation(
                lambda service: service.initialize_application_workflow_state(parsed_application_id),
            )
    finally:
        reset_log_context(tokens)


@activity.defn
async def parse_application_resume(application_id: str) -> dict[str, Any]:
    parsed_application_id = uuid.UUID(application_id)
    tokens = bind_log_context(workflow_id=activity.info().workflow_id, correlation_id=activity.info().workflow_id)
    try:
        with start_trace_span(
            "temporal.activity.parse_application_resume",
            attributes={
                "smarthire.application_id": application_id,
                "smarthire.workflow_id": activity.info().workflow_id,
            },
        ):
            activity.logger.info(
                "Parsing uploaded application resume",
                extra={"application_id": application_id},
            )
            return await _run_application_service_operation(
                lambda service: service.process_uploaded_resume(parsed_application_id),
            )
    finally:
        reset_log_context(tokens)