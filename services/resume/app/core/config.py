from __future__ import annotations

from functools import lru_cache

from pydantic import Field

from app.temporal.constants import RESUME_PARSING_TASK_QUEUE
from config.base import ServiceSettings


class Settings(ServiceSettings):
    app_name: str = "Resume Service"
    app_port: int = Field(default=8004, alias="APP_PORT")
    temporal_resume_task_queue: str = Field(
        default=RESUME_PARSING_TASK_QUEUE,
        alias="TEMPORAL_RESUME_TASK_QUEUE",
    )
    resume_upload_dir: str = Field(default="uploads/resumes", alias="RESUME_UPLOAD_DIR")
    max_resume_size_bytes: int = Field(
        default=10 * 1024 * 1024, alias="MAX_RESUME_SIZE_BYTES"
    )
    candidate_service_url: str = Field(
        default="http://user-service:8001",
        alias="CANDIDATE_SERVICE_URL",
    )
    http_client_timeout_seconds: float = Field(
        default=5.0,
        alias="HTTP_CLIENT_TIMEOUT_SECONDS",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
