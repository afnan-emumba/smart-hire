from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from contracts.enums import NotificationChannel, NotificationStatus
from db.base import Base, TimestampMixin

__all__ = ["Base", "Notification"]


class Notification(TimestampMixin, Base):
    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    recipient_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    recipient_role: Mapped[str] = mapped_column(String(32), nullable=False)
    notification_type: Mapped[str] = mapped_column(String(64), nullable=False)
    channel: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=NotificationChannel.IN_APP.value,
        server_default=NotificationChannel.IN_APP.value,
    )
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=NotificationStatus.PENDING.value,
        server_default=NotificationStatus.PENDING.value,
        index=True,
    )
    dedupe_key: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True, index=True
    )
    delivered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
