from __future__ import annotations

from functools import lru_cache

from pydantic import Field

from config.base import ServiceSettings
from contracts.temporal import NOTIFICATION_DELIVERY_TASK_QUEUE


class Settings(ServiceSettings):
    app_name: str = "Notification Service"
    app_port: int = Field(default=8006, alias="APP_PORT")
    temporal_notification_task_queue: str = Field(
        default=NOTIFICATION_DELIVERY_TASK_QUEUE,
        alias="TEMPORAL_NOTIFICATION_TASK_QUEUE",
    )
    notification_failure_rate: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        alias="NOTIFICATION_FAILURE_RATE",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
