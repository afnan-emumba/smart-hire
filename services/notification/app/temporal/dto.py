from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class NotificationDeliveryInput:
    """Payload sent by application-service when an application status changes.

    Field names are part of a cross-service contract: application-service
    serializes an identically-shaped dataclass into this workflow.
    """

    recipient_user_id: str
    recipient_role: str
    notification_type: str
    dedupe_key: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class DeliverNotificationInput:
    notification_id: str
