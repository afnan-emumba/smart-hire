from __future__ import annotations

from functools import lru_cache

from config.base import ServiceSettings
from pydantic import Field


class Settings(ServiceSettings):
    app_name: str = "Application Service"
    app_port: int = Field(default=8005, alias="APP_PORT")
    max_applications_per_candidate: int = Field(
        default=5,
        alias="MAX_APPLICATIONS_PER_CANDIDATE",
    )
    job_service_url: str = Field(default="http://job-service:8003", alias="JOB_SERVICE_URL")
    candidate_service_url: str = Field(
        default="http://candidate-service:8002",
        alias="CANDIDATE_SERVICE_URL",
    )
    resume_service_url: str = Field(
        default="http://resume-service:8004",
        alias="RESUME_SERVICE_URL",
    )
    http_client_timeout_seconds: float = Field(
        default=5.0,
        alias="HTTP_CLIENT_TIMEOUT_SECONDS",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
