from __future__ import annotations

import asyncio
import logging

from temporalio.worker import Worker

from app.core.config import get_settings
from app.temporal.activities import (
    delete_job_applications,
    delete_job_description_file,
    delete_job_record,
    finalize_job_breakdown,
    mark_job_ready,
)
from app.temporal.client import TemporalClient
from app.temporal.workflows import JobDeletionWorkflow, JobPublishingWorkflow
from contracts.temporal import JOB_DELETION_TASK_QUEUE


async def start_worker() -> None:
    """Serve both job task queues from one process.

    Publishing and deletion are separate queues so their names stay honest, but
    they share a worker process because they share this service's code and
    database connections.
    """
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()
    client = await TemporalClient.get_client()

    publishing_worker = Worker(
        client,
        task_queue=settings.temporal_job_task_queue,
        workflows=[JobPublishingWorkflow],
        activities=[finalize_job_breakdown, mark_job_ready],
    )
    deletion_worker = Worker(
        client,
        task_queue=JOB_DELETION_TASK_QUEUE,
        workflows=[JobDeletionWorkflow],
        activities=[
            delete_job_applications,
            delete_job_description_file,
            delete_job_record,
        ],
    )

    await asyncio.gather(publishing_worker.run(), deletion_worker.run())


if __name__ == "__main__":
    asyncio.run(start_worker())
