from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.celery_app import celery_app
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.events.schemas import ApplicationReceivedEvent, JobPublishedEvent
from app.repositories.event_processing_repo import EventProcessingRepository
from app.tasks import (
    APPLICATION_ANALYTICS_TASK,
    JOB_ANALYTICS_TASK,
    build_application_service,
    build_job_service,
    run_async_task,
)



settings = get_settings()


@celery_app.task(
    autoretry_for=(Exception,),
    bind=True,
    max_retries=settings.celery_task_max_retries,
    name=APPLICATION_ANALYTICS_TASK,
    retry_backoff=settings.celery_task_retry_backoff,
    retry_jitter=False,
)
def process_application_analytics(
    self,
    payload: dict[str, Any],
    headers: dict[str, str],
) -> dict[str, Any]:
    return run_async_task(
        _process_application_analytics(
            payload=payload,
            headers=headers,
            celery_task_id=self.request.id,
        )
    )


@celery_app.task(
    autoretry_for=(Exception,),
    bind=True,
    max_retries=settings.celery_task_max_retries,
    name=JOB_ANALYTICS_TASK,
    retry_backoff=settings.celery_task_retry_backoff,
    retry_jitter=False,
)
def process_job_published_analytics(
    self,
    payload: dict[str, Any],
    headers: dict[str, str],
) -> dict[str, Any]:
    return run_async_task(
        _process_job_published_analytics(
            payload=payload,
            headers=headers,
            celery_task_id=self.request.id,
        )
    )


async def _process_application_analytics(
    *,
    payload: dict[str, Any],
    headers: dict[str, str],
    celery_task_id: str | None,
) -> dict[str, Any]:
    event = ApplicationReceivedEvent.model_validate(payload)

    async with SessionLocal() as session:
        processing_repo = EventProcessingRepository(session)
        record, claimed = await processing_repo.claim_for_processing(
            event_id=event.event_id,
            handler_name=APPLICATION_ANALYTICS_TASK,
        )
        if record is None:
            record, _ = await processing_repo.get_or_create(
                event_id=event.event_id,
                handler_name=APPLICATION_ANALYTICS_TASK,
                event_type=event.event_type(),
                topic_name=event.topic_name(),
                aggregate_id=event.aggregate_id,
                schema_version=event.schema_version,
                metadata={"celery_task_id": celery_task_id},
            )
            record, claimed = await processing_repo.claim_for_processing(
                event_id=event.event_id,
                handler_name=APPLICATION_ANALYTICS_TASK,
            )

        if record is None or not claimed:
            await session.commit()
            return {"application_id": str(event.application_id), "status": "skipped"}

        try:
            application_service = build_application_service(session)
            analytics_result = {
                "status": "updated",
                "event_id": str(event.event_id),
                "event_type": event.event_type(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "application_status": event.status,
                "job_id": str(event.job_id),
                "candidate_id": str(event.candidate_id),
            }
            await application_service.record_analytics_result(
                event.application_id,
                analytics_result=analytics_result,
            )
            await processing_repo.mark_completed(
                record,
                metadata={
                    "celery_task_id": celery_task_id,
                    "event_type": event.event_type(),
                    "headers": headers,
                },
            )
            await session.commit()
            return {
                "application_id": str(event.application_id),
                "event_id": str(event.event_id),
                "status": analytics_result["status"],
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
            await session.commit()
            raise


async def _process_job_published_analytics(
    *,
    payload: dict[str, Any],
    headers: dict[str, str],
    celery_task_id: str | None,
) -> dict[str, Any]:
    event = JobPublishedEvent.model_validate(payload)

    async with SessionLocal() as session:
        processing_repo = EventProcessingRepository(session)
        record, claimed = await processing_repo.claim_for_processing(
            event_id=event.event_id,
            handler_name=JOB_ANALYTICS_TASK,
        )
        if record is None:
            record, _ = await processing_repo.get_or_create(
                event_id=event.event_id,
                handler_name=JOB_ANALYTICS_TASK,
                event_type=event.event_type(),
                topic_name=event.topic_name(),
                aggregate_id=event.aggregate_id,
                schema_version=event.schema_version,
                metadata={"celery_task_id": celery_task_id},
            )
            record, claimed = await processing_repo.claim_for_processing(
                event_id=event.event_id,
                handler_name=JOB_ANALYTICS_TASK,
            )

        if record is None or not claimed:
            await session.commit()
            return {"job_id": str(event.job_id), "status": "skipped"}

        try:
            job_service = build_job_service(session)
            analytics_result = {
                "status": "updated",
                "event_id": str(event.event_id),
                "event_type": event.event_type(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "job_id": str(event.job_id),
                "recruiter_id": str(event.recruiter_id),
                "job_status": event.status,
            }
            await job_service.record_analytics_result(
                event.job_id,
                analytics_result=analytics_result,
            )
            await processing_repo.mark_completed(
                record,
                metadata={
                    "celery_task_id": celery_task_id,
                    "event_type": event.event_type(),
                    "headers": headers,
                    "status": event.status,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                },
            )
            await session.commit()
            return {
                "job_id": str(event.job_id),
                "event_id": str(event.event_id),
                "status": "updated",
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
            await session.commit()
            raise