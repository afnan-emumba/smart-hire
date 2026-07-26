from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class NotificationDeliveryInput:
    """Payload for notification-service's delivery workflow.

    Field names are part of a cross-service contract: notification-service
    deserializes an identically-shaped dataclass from this.
    """

    recipient_user_id: str
    recipient_role: str
    notification_type: str
    dedupe_key: str
    payload: dict[str, Any] = field(default_factory=dict)
