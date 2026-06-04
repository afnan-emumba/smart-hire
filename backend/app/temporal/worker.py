from __future__ import annotations

import asyncio
import logging

from temporalio.worker import Worker

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.tracing import configure_tracing
from app.db.session import engine
from app.temporal.activities import (
    finalize_job_breakdown,
    initialize_application_processing,
    mark_application_workflow_failed,
    mark_job_publishing_failed,
    mark_job_ready,
    parse_application_resume,
)
from app.temporal.client import TemporalClient
from app.temporal.workflows import CandidateApplicationWorkflow, JobPublishingWorkflow


settings = get_settings()
configure_logging(settings)
configure_tracing(settings, sqlalchemy_engine=engine)
logger = logging.getLogger(__name__)


async def start_worker() -> None:
    client = await TemporalClient.get_client()
    logger.info("Starting Temporal workers")
    job_worker = Worker(
        client,
        task_queue=settings.temporal_job_task_queue,
        workflows=[JobPublishingWorkflow],
        activities=[finalize_job_breakdown, mark_job_ready, mark_job_publishing_failed],
        max_concurrent_workflow_tasks=settings.temporal_worker_max_concurrent_workflow_tasks,
        max_concurrent_activities=settings.temporal_worker_max_concurrent_activities,
        max_concurrent_workflow_task_polls=settings.temporal_worker_max_concurrent_workflow_task_polls,
        max_concurrent_activity_task_polls=settings.temporal_worker_max_concurrent_activity_task_polls,
    )
    application_worker = Worker(
        client,
        task_queue=settings.temporal_application_task_queue,
        workflows=[CandidateApplicationWorkflow],
        activities=[initialize_application_processing, parse_application_resume, mark_application_workflow_failed],
        max_concurrent_workflow_tasks=settings.temporal_worker_max_concurrent_workflow_tasks,
        max_concurrent_activities=settings.temporal_worker_max_concurrent_activities,
        max_concurrent_workflow_task_polls=settings.temporal_worker_max_concurrent_workflow_task_polls,
        max_concurrent_activity_task_polls=settings.temporal_worker_max_concurrent_activity_task_polls,
    )
    await asyncio.gather(job_worker.run(), application_worker.run())


if __name__ == "__main__":
    asyncio.run(start_worker())