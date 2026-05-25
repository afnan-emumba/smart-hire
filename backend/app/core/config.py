from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "SmartHire API"
    app_version: str = "0.1.0"
    app_env: str = Field(default="development", alias="APP_ENV")
    app_host: str = Field(default="0.0.0.0", alias="APP_HOST")
    app_port: int = Field(default=8000, alias="APP_PORT")
    database_url: str = Field(alias="DATABASE_URL")
    temporal_address: str = Field(default="localhost:7233", alias="TEMPORAL_ADDRESS")
    temporal_namespace: str = Field(default="default", alias="TEMPORAL_NAMESPACE")
    temporal_job_task_queue: str = Field(
        default="job-publishing",
        alias="TEMPORAL_JOB_TASK_QUEUE",
    )
    temporal_application_task_queue: str = Field(
        default="candidate-application",
        alias="TEMPORAL_APPLICATION_TASK_QUEUE",
    )
    resume_upload_dir: str = Field(default="uploads/resumes", alias="RESUME_UPLOAD_DIR")
    max_resume_size_bytes: int = Field(default=10 * 1024 * 1024, alias="MAX_RESUME_SIZE_BYTES")
    jd_upload_dir: str = Field(default="uploads/job_descriptions", alias="JD_UPLOAD_DIR")
    max_jd_size_bytes: int = Field(default=10 * 1024 * 1024, alias="MAX_JD_SIZE_BYTES")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()