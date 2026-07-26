from __future__ import annotations

import uuid

from app.core.config import Settings
from app.repositories.notification_repo import NotificationRepository
from app.schemas.notification import NotificationCreate, NotificationResponse
from app.services.delivery_channel import DeliveryChannel, build_delivery_channel
from exceptions.http_exceptions import NotFoundError
from temporal.schemas import NotificationRecordActivityResult


class NotificationService:
    def __init__(
        self,
        notification_repo: NotificationRepository,
        settings: Settings,
        delivery_channel: DeliveryChannel | None = None,
    ) -> None:
        self.notification_repo = notification_repo
        self.settings = settings
        self.delivery_channel = delivery_channel or build_delivery_channel(settings)

    async def record_notification(
        self, notification_create: NotificationCreate
    ) -> NotificationRecordActivityResult:
        """Persist the notification, or return the existing row for this dedupe key.

        Idempotent so a retried activity never produces a duplicate.
        """
        existing = await self.notification_repo.get_by_dedupe_key(
            notification_create.dedupe_key
        )
        notification = existing or await self.notification_repo.create(
            notification_create
        )
        return NotificationRecordActivityResult(
            notification_id=notification.id, status=notification.status
        )

    async def deliver_notification(
        self, notification_id: uuid.UUID
    ) -> NotificationRecordActivityResult:
        notification = await self.notification_repo.get_by_id(notification_id)
        if notification is None:
            raise NotFoundError("Notification not found")

        await self.delivery_channel.deliver(notification)
        delivered = await self.notification_repo.mark_delivered(notification)
        return NotificationRecordActivityResult(
            notification_id=delivered.id, status=delivered.status
        )

    async def create_notification(
        self, notification_create: NotificationCreate
    ) -> NotificationResponse:
        existing = await self.notification_repo.get_by_dedupe_key(
            notification_create.dedupe_key
        )
        notification = existing or await self.notification_repo.create(
            notification_create
        )
        return NotificationResponse.model_validate(notification)

    async def list_notifications(
        self, recipient_user_id: uuid.UUID, *, limit: int, offset: int
    ) -> list[NotificationResponse]:
        notifications = await self.notification_repo.list_for_recipient(
            recipient_user_id, limit=limit, offset=offset
        )
        return [
            NotificationResponse.model_validate(notification)
            for notification in notifications
        ]
