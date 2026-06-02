from __future__ import annotations

from celery import Celery

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.tracing import configure_tracing
from app.db.session import engine


settings = get_settings()
configure_logging(settings)

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

configure_tracing(settings, celery_app=celery_app, sqlalchemy_engine=engine)

import app.tasks.analytics  # noqa: E402,F401
import app.tasks.notifications  # noqa: E402,F401
import app.tasks.scoring  # noqa: E402,F401
