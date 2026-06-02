from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.celery_app import celery_app
from app.core.config import get_settings
from app.core.logging import bind_log_context, reset_log_context
from app.core.metrics import record_task_execution
from app.db.session import SessionLocal
from app.events.schemas import ApplicationReceivedEvent
from app.repositories.event_processing_repo import EventProcessingRepository
from app.tasks import (
    APPLICATION_RECEIVED_NOTIFICATION_TASK,
    build_application_service,
    run_async_task,
)

settings = get_settings()


@celery_app.task(
    autoretry_for=(Exception,),
    bind=True,
    max_retries=settings.celery_task_max_retries,
    name=APPLICATION_RECEIVED_NOTIFICATION_TASK,
    retry_backoff=settings.celery_task_retry_backoff,
    retry_jitter=False,
)
def send_application_received_notification(
    self,
    payload: dict[str, Any],
    headers: dict[str, str],
) -> dict[str, Any]:
    return run_async_task(
        _send_application_received_notification(
            payload=payload,
            headers=headers,
            celery_task_id=self.request.id,
        )
    )


async def _send_application_received_notification(
    *,
    payload: dict[str, Any],
    headers: dict[str, str],
    celery_task_id: str | None,
) -> dict[str, Any]:
    event = ApplicationReceivedEvent.model_validate(payload)
    tokens = bind_log_context(
        user_id=headers.get("user_id"),
        workflow_id=headers.get("workflow_id"),
        correlation_id=headers.get("correlation_id"),
    )

    try:
        async with SessionLocal() as session:
            processing_repo = EventProcessingRepository(session)
            record, claimed = await processing_repo.claim_for_processing(
                event_id=event.event_id,
                handler_name=APPLICATION_RECEIVED_NOTIFICATION_TASK,
            )
            if record is None:
                await processing_repo.get_or_create(
                    event_id=event.event_id,
                    handler_name=APPLICATION_RECEIVED_NOTIFICATION_TASK,
                    event_type=event.event_type(),
                    topic_name=event.topic_name(),
                    aggregate_id=event.aggregate_id,
                    schema_version=event.schema_version,
                    metadata={"celery_task_id": celery_task_id},
                )
                record, claimed = await processing_repo.claim_for_processing(
                    event_id=event.event_id,
                    handler_name=APPLICATION_RECEIVED_NOTIFICATION_TASK,
                )

            if record is None or not claimed:
                record_task_execution(task_name=APPLICATION_RECEIVED_NOTIFICATION_TASK, status="skipped")
                await session.commit()
                return {"application_id": str(event.application_id), "status": "skipped"}

            try:
                application_service = build_application_service(session)
                notification_result = {
                    "status": "sent",
                    "delivery": "simulated",
                    "event_id": str(event.event_id),
                    "application_id": str(event.application_id),
                    "candidate_id": str(event.candidate_id),
                    "sent_at": datetime.now(timezone.utc).isoformat(),
                }
                await application_service.record_notification_result(
                    event.application_id,
                    notification_name="application_received",
                    notification_result=notification_result,
                )
                await processing_repo.mark_completed(
                    record,
                    metadata={
                        "celery_task_id": celery_task_id,
                        "event_type": event.event_type(),
                        "headers": headers,
                    },
                )
                record_task_execution(task_name=APPLICATION_RECEIVED_NOTIFICATION_TASK, status="success")
                await session.commit()
                return {
                    "application_id": str(event.application_id),
                    "event_id": str(event.event_id),
                    "status": notification_result["status"],
                }
            except Exception as exc:
                await processing_repo.mark_failed(
                    record,
                    error_message=str(exc),
                    metadata={
                        "celery_task_id": celery_task_id,
                        "failed_at": datetime.now(timezone.utc).isoformat(),
                    },
                )
                record_task_execution(task_name=APPLICATION_RECEIVED_NOTIFICATION_TASK, status="failure")
                await session.commit()
                raise
    finally:
        reset_log_context(tokens)
