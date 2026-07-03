from __future__ import annotations

from functools import lru_cache

from config.base import ServiceSettings
from pydantic import Field


class Settings(ServiceSettings):
    app_name: str = "Job Service"
    app_port: int = Field(default=8003, alias="APP_PORT")
    temporal_job_task_queue: str = Field(
        default="job-publishing",
        alias="TEMPORAL_JOB_TASK_QUEUE",
    )
    jd_upload_dir: str = Field(default="uploads/job_descriptions", alias="JD_UPLOAD_DIR")
    max_jd_size_bytes: int = Field(default=10 * 1024 * 1024, alias="MAX_JD_SIZE_BYTES")
    recruiter_service_url: str = Field(
        default="http://recruiter-service:8001",
        alias="RECRUITER_SERVICE_URL",
    )
    application_service_url: str = Field(
        default="http://application-service:8005",
        alias="APPLICATION_SERVICE_URL",
    )
    http_client_timeout_seconds: float = Field(
        default=5.0,
        alias="HTTP_CLIENT_TIMEOUT_SECONDS",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
