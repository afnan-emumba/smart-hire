from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from temporalio import activity

from app.core.config import get_settings
from app.core.enums import JobStatus
from app.db.session import SessionLocal
from app.repositories.job_repo import JobRepository
from app.repositories.recruiter_repo import RecruiterRepository
from app.services.job_service import JobService


async def _run_job_service_operation(
    operation: Callable[[JobService], Awaitable[dict[str, Any]]],
) -> dict[str, Any]:
    async with SessionLocal() as session:
        service = JobService(
            job_repo=JobRepository(session),
            recruiter_repo=RecruiterRepository(session),
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
    activity.logger.info("Finalizing job breakdown", extra={"job_id": job_id})
    return await _run_job_service_operation(
        lambda service: service.finalize_job_breakdown(parsed_job_id),
    )


@activity.defn
async def mark_job_ready(job_id: str) -> dict[str, Any]:
    parsed_job_id = uuid.UUID(job_id)
    activity.logger.info("Marking job ready", extra={"job_id": job_id})

    async def _mark_ready(service: JobService) -> dict[str, Any]:
        job = await service.update_job_status(parsed_job_id, JobStatus.READY)
        return {
            "job_id": str(job.id),
            "status": job.status,
        }

    return await _run_job_service_operation(_mark_ready)