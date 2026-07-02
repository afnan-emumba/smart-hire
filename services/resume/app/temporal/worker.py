from __future__ import annotations

import asyncio

from temporalio.worker import Worker

from app.core.config import get_settings
from app.temporal.activities import parse_resume
from app.temporal.client import TemporalClient
from app.temporal.workflows import ResumeParsingWorkflow


async def start_worker() -> None:
    settings = get_settings()
    client = await TemporalClient.get_client()
    worker = Worker(
        client,
        task_queue=settings.temporal_resume_task_queue,
        workflows=[ResumeParsingWorkflow],
        activities=[parse_resume],
    )
    await worker.run()


if __name__ == "__main__":
    asyncio.run(start_worker())
