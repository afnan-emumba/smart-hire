from __future__ import annotations

import asyncio

from temporalio.worker import Worker

from app.core.config import get_settings
from app.temporal.activities import finalize_job_breakdown, mark_job_ready
from app.temporal.client import TemporalClient
from app.temporal.workflows import JobPublishingWorkflow


async def start_worker() -> None:
    settings = get_settings()
    client = await TemporalClient.get_client()
    worker = Worker(
        client,
        task_queue=settings.temporal_job_task_queue,
        workflows=[JobPublishingWorkflow],
        activities=[finalize_job_breakdown, mark_job_ready],
    )
    await worker.run()


if __name__ == "__main__":
    asyncio.run(start_worker())
