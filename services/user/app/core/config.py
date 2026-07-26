from __future__ import annotations

from functools import lru_cache

from pydantic import Field

from app.temporal.constants import USER_DELETION_TASK_QUEUE
from config.base import ServiceSettings


class Settings(ServiceSettings):
    app_name: str = "User Service"
    app_port: int = Field(default=8001, alias="APP_PORT")
    temporal_user_deletion_task_queue: str = Field(
        default=USER_DELETION_TASK_QUEUE,
        alias="TEMPORAL_USER_DELETION_TASK_QUEUE",
    )
    resume_service_url: str = Field(
        default="http://resume-service:8004",
        alias="RESUME_SERVICE_URL",
    )
    application_service_url: str = Field(
        default="http://application-service:8005",
        alias="APPLICATION_SERVICE_URL",
    )
    job_service_url: str = Field(
        default="http://job-service:8003",
        alias="JOB_SERVICE_URL",
    )
    http_client_timeout_seconds: float = Field(
        default=5.0,
        alias="HTTP_CLIENT_TIMEOUT_SECONDS",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
