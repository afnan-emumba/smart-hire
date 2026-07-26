from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from contracts.enums import (
    NotificationChannel,
    NotificationStatus,
    NotificationType,
    UserRole,
)

DedupeKey = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
]


class NotificationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recipient_user_id: uuid.UUID
    recipient_role: UserRole
    notification_type: NotificationType
    dedupe_key: DedupeKey
    channel: NotificationChannel = NotificationChannel.IN_APP
    payload: dict[str, Any] = Field(default_factory=dict)


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    recipient_user_id: uuid.UUID
    recipient_role: UserRole
    notification_type: NotificationType
    channel: NotificationChannel
    payload: dict[str, Any]
    status: NotificationStatus
    dedupe_key: str
    delivered_at: datetime | None
    created_at: datetime
    updated_at: datetime
