from __future__ import annotations

import asyncio
import logging

from temporalio.worker import Worker

from app.core.config import get_settings
from app.temporal.activities import deliver_notification, record_notification
from app.temporal.client import TemporalClient
from app.temporal.workflows import NotificationDeliveryWorkflow


async def start_worker() -> None:
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()
    client = await TemporalClient.get_client()
    worker = Worker(
        client,
        task_queue=settings.temporal_notification_task_queue,
        workflows=[NotificationDeliveryWorkflow],
        activities=[record_notification, deliver_notification],
    )
    await worker.run()


if __name__ == "__main__":
    asyncio.run(start_worker())
