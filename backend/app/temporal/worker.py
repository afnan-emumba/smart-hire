from __future__ import annotations

import asyncio

from temporalio.worker import Worker

from app.core.config import get_settings
from app.temporal.activities import (
    finalize_job_breakdown,
    initialize_application_processing,
    mark_job_ready,
    parse_application_resume,
)
from app.temporal.client import TemporalClient
from app.temporal.workflows import CandidateApplicationWorkflow, JobPublishingWorkflow


async def start_worker() -> None:
    settings = get_settings()
    client = await TemporalClient.get_client()
    job_worker = Worker(
        client,
        task_queue=settings.temporal_job_task_queue,
        workflows=[JobPublishingWorkflow],
        activities=[finalize_job_breakdown, mark_job_ready],
    )
    application_worker = Worker(
        client,
        task_queue=settings.temporal_application_task_queue,
        workflows=[CandidateApplicationWorkflow],
        activities=[initialize_application_processing, parse_application_resume],
    )
    await asyncio.gather(job_worker.run(), application_worker.run())


if __name__ == "__main__":
    asyncio.run(start_worker())