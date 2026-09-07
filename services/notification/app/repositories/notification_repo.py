from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Notification
from app.schemas.notification import NotificationCreate
from contracts.enums import NotificationStatus


class NotificationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, notification_id: uuid.UUID) -> Notification | None:
        result = await self.session.execute(
            select(Notification).where(Notification.id == notification_id)
        )
        return result.scalar_one_or_none()

    async def get_by_dedupe_key(self, dedupe_key: str) -> Notification | None:
        result = await self.session.execute(
            select(Notification).where(Notification.dedupe_key == dedupe_key)
        )
        return result.scalar_one_or_none()

    async def create(self, notification_create: NotificationCreate) -> Notification:
        notification = Notification(
            recipient_user_id=notification_create.recipient_user_id,
            recipient_role=notification_create.recipient_role.value,
            notification_type=notification_create.notification_type.value,
            channel=notification_create.channel.value,
            payload=notification_create.payload,
            status=NotificationStatus.PENDING.value,
            dedupe_key=notification_create.dedupe_key,
        )
        self.session.add(notification)
        await self.session.flush()
        await self.session.refresh(notification)
        return notification

    async def mark_delivered(self, notification: Notification) -> Notification:
        notification.status = NotificationStatus.DELIVERED.value
        notification.delivered_at = datetime.now(timezone.utc)
        await self.session.flush()
        await self.session.refresh(notification)
        return notification

    async def list_for_recipient(
        self, recipient_user_id: uuid.UUID, *, limit: int, offset: int
    ) -> list[Notification]:
        result = await self.session.execute(
            select(Notification)
            .where(Notification.recipient_user_id == recipient_user_id)
            .order_by(Notification.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())
