from __future__ import annotations

import asyncio
import logging

from temporalio.worker import Worker

from app.core.config import get_settings
from app.temporal.activities import (
    delete_candidate_applications,
    delete_candidate_record,
    delete_candidate_resumes,
    delete_recruiter_record,
    list_recruiter_job_ids,
)
from app.temporal.client import TemporalClient
from app.temporal.workflows import (
    CandidateDeletionWorkflow,
    RecruiterDeletionWorkflow,
)


async def start_worker() -> None:
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()
    client = await TemporalClient.get_client()
    worker = Worker(
        client,
        task_queue=settings.temporal_user_deletion_task_queue,
        workflows=[CandidateDeletionWorkflow, RecruiterDeletionWorkflow],
        activities=[
            delete_candidate_resumes,
            delete_candidate_applications,
            delete_candidate_record,
            list_recruiter_job_ids,
            delete_recruiter_record,
        ],
    )
    await worker.run()


if __name__ == "__main__":
    asyncio.run(start_worker())
