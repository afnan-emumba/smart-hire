from __future__ import annotations

import uuid
from typing import Any

from temporalio import activity

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.repositories.notification_repo import NotificationRepository
from app.schemas.notification import NotificationCreate
from app.services.notification_service import NotificationService
from app.temporal.constants import (
    ACTIVITY_DELIVER_NOTIFICATION,
    ACTIVITY_RECORD_NOTIFICATION,
)
from app.temporal.dto import DeliverNotificationInput, NotificationDeliveryInput
from exceptions.http_exceptions import BadRequestError, NotFoundError
from temporal.activity_runner import run_temporal_activity
from temporal.schemas import NotificationRecordActivityResult

_NON_RETRYABLE_ERRORS = (BadRequestError,)


def _build_service(session: Any) -> NotificationService:
    return NotificationService(
        notification_repo=NotificationRepository(session),
        settings=get_settings(),
    )


@activity.defn(name=ACTIVITY_RECORD_NOTIFICATION)
async def record_notification(input: NotificationDeliveryInput) -> dict[str, Any]:
    activity.logger.info(
        "Recording notification", extra={"dedupe_key": input.dedupe_key}
    )
    notification_create = NotificationCreate(
        recipient_user_id=uuid.UUID(input.recipient_user_id),
        recipient_role=input.recipient_role,
        notification_type=input.notification_type,
        dedupe_key=input.dedupe_key,
        payload=input.payload,
    )
    return await run_temporal_activity(
        session_factory=SessionLocal,
        build_service=_build_service,
        operation=lambda service: service.record_notification(notification_create),
        non_retryable_errors=_NON_RETRYABLE_ERRORS,
        serialize_result=lambda result: NotificationRecordActivityResult.model_validate(
            result
        ).model_dump(mode="json"),
    )


@activity.defn(name=ACTIVITY_DELIVER_NOTIFICATION)
async def deliver_notification(input: DeliverNotificationInput) -> dict[str, Any]:
    notification_id = uuid.UUID(input.notification_id)
    activity.logger.info(
        "Delivering notification", extra={"notification_id": input.notification_id}
    )
    return await run_temporal_activity(
        session_factory=SessionLocal,
        build_service=_build_service,
        operation=lambda service: service.deliver_notification(notification_id),
        non_retryable_errors=(*_NON_RETRYABLE_ERRORS, NotFoundError),
        serialize_result=lambda result: NotificationRecordActivityResult.model_validate(
            result
        ).model_dump(mode="json"),
    )
