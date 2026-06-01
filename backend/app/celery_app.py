from __future__ import annotations

from celery import Celery

from app.core.config import get_settings


settings = get_settings()

celery_app = Celery(
    "smarthire",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.tasks.scoring",
        "app.tasks.notifications",
        "app.tasks.analytics",
    ],
)

celery_app.conf.update(
    accept_content=["json"],
    broker_connection_retry_on_startup=True,
    result_serializer="json",
    task_acks_late=True,
    task_default_queue="smarthire",
    task_serializer="json",
    task_track_started=True,
    worker_prefetch_multiplier=1,
)

import app.tasks.analytics  # noqa: E402,F401
import app.tasks.notifications  # noqa: E402,F401
import app.tasks.scoring  # noqa: E402,F401
