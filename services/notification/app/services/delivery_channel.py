from __future__ import annotations

import logging
import random
from typing import Protocol

from app.core.config import Settings
from app.db.models import Notification
from exceptions.http_exceptions import ServiceUnavailableError

logger = logging.getLogger(__name__)


class DeliveryChannel(Protocol):
    async def deliver(self, notification: Notification) -> None: ...


class LoggingDeliveryChannel:
    """Default channel. Delivery is a log line until a real transport exists."""

    async def deliver(self, notification: Notification) -> None:
        logger.info(
            "Delivered notification",
            extra={
                "notification_id": str(notification.id),
                "recipient_user_id": str(notification.recipient_user_id),
                "notification_type": notification.notification_type,
            },
        )


class FlakyDeliveryChannel:
    """Fails a configurable share of deliveries so the workflow's retry loop is
    observable in the Temporal UI.

    Development only: ``NOTIFICATION_FAILURE_RATE`` defaults to 0.0 and must
    stay there outside local dev.
    """

    def __init__(self, failure_rate: float) -> None:
        self._failure_rate = failure_rate

    async def deliver(self, notification: Notification) -> None:
        if random.random() < self._failure_rate:
            logger.warning(
                "Simulated notification delivery failure",
                extra={"notification_id": str(notification.id)},
            )
            raise ServiceUnavailableError("Notification delivery failed")

        await LoggingDeliveryChannel().deliver(notification)


def build_delivery_channel(settings: Settings) -> DeliveryChannel:
    if settings.notification_failure_rate > 0:
        return FlakyDeliveryChannel(settings.notification_failure_rate)
    return LoggingDeliveryChannel()
