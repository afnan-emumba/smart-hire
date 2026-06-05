from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.events.topics import APPLICATION_RECEIVED_TOPIC, JOB_PUBLISHED_TOPIC


class Settings(BaseSettings):
    app_name: str = "SmartHire API"
    app_version: str = "0.1.0"
    app_env: str = Field(default="development", alias="APP_ENV")
    app_host: str = Field(default="0.0.0.0", alias="APP_HOST")
    app_port: int = Field(default=8000, alias="APP_PORT")
    database_url: str = Field(alias="DATABASE_URL")
    temporal_address: str = Field(
        default="localhost:7233", alias="TEMPORAL_ADDRESS")
    temporal_namespace: str = Field(
        default="default", alias="TEMPORAL_NAMESPACE")
    temporal_job_task_queue: str = Field(
        default="job-publishing",
        alias="TEMPORAL_JOB_TASK_QUEUE",
    )
    temporal_application_task_queue: str = Field(
        default="candidate-application",
        alias="TEMPORAL_APPLICATION_TASK_QUEUE",
    )
    temporal_job_workflow_execution_timeout_seconds: int = Field(
        default=1800,
        alias="TEMPORAL_JOB_WORKFLOW_EXECUTION_TIMEOUT_SECONDS",
    )
    temporal_application_workflow_execution_timeout_seconds: int = Field(
        default=1800,
        alias="TEMPORAL_APPLICATION_WORKFLOW_EXECUTION_TIMEOUT_SECONDS",
    )
    temporal_workflow_task_timeout_seconds: int = Field(
        default=30,
        alias="TEMPORAL_WORKFLOW_TASK_TIMEOUT_SECONDS",
    )
    temporal_worker_max_concurrent_workflow_tasks: int = Field(
        default=200,
        alias="TEMPORAL_WORKER_MAX_CONCURRENT_WORKFLOW_TASKS",
    )
    temporal_worker_max_concurrent_activities: int = Field(
        default=40,
        alias="TEMPORAL_WORKER_MAX_CONCURRENT_ACTIVITIES",
    )
    temporal_worker_max_concurrent_workflow_task_polls: int = Field(
        default=20,
        alias="TEMPORAL_WORKER_MAX_CONCURRENT_WORKFLOW_TASK_POLLS",
    )
    temporal_worker_max_concurrent_activity_task_polls: int = Field(
        default=8,
        alias="TEMPORAL_WORKER_MAX_CONCURRENT_ACTIVITY_TASK_POLLS",
    )
    kafka_bootstrap_servers: str = Field(alias="KAFKA_BOOTSTRAP_SERVERS")
    schema_registry_url: str = Field(alias="SCHEMA_REGISTRY_URL")
    kafka_job_published_topic: str = Field(
        default=JOB_PUBLISHED_TOPIC,
        alias="KAFKA_JOB_PUBLISHED_TOPIC",
    )
    kafka_application_received_topic: str = Field(
        default=APPLICATION_RECEIVED_TOPIC,
        alias="KAFKA_APPLICATION_RECEIVED_TOPIC",
    )
    rabbitmq_url: str = Field(alias="RABBITMQ_URL")
    redis_url: str = Field(alias="REDIS_URL")
    celery_broker_url: str = Field(
        alias="CELERY_BROKER_URL",
    )
    celery_result_backend: str = Field(
        alias="CELERY_RESULT_BACKEND",
    )
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_json: bool = Field(default=True, alias="LOG_JSON")
    metrics_enabled: bool = Field(default=True, alias="METRICS_ENABLED")
    tracing_enabled: bool = Field(default=False, alias="TRACING_ENABLED")
    otel_service_name: str = Field(
        default="smarthire-backend", alias="OTEL_SERVICE_NAME")
    otel_exporter_otlp_endpoint: str = Field(
        alias="OTEL_EXPORTER_OTLP_ENDPOINT",
    )
    healthcheck_timeout_seconds: float = Field(
        default=5.0,
        alias="HEALTHCHECK_TIMEOUT_SECONDS",
    )
    event_relay_batch_size: int = Field(
        default=50, alias="EVENT_RELAY_BATCH_SIZE")
    event_relay_poll_interval_seconds: float = Field(
        default=2.0,
        alias="EVENT_RELAY_POLL_INTERVAL_SECONDS",
    )
    event_relay_max_retries: int = Field(
        default=5, alias="EVENT_RELAY_MAX_RETRIES")
    event_relay_retry_backoff_seconds: float = Field(
        default=5.0,
        alias="EVENT_RELAY_RETRY_BACKOFF_SECONDS",
    )
    kafka_consumer_group_id: str = Field(
        default="smarthire-consumer",
        alias="KAFKA_CONSUMER_GROUP_ID",
    )
    kafka_consumer_poll_timeout_ms: int = Field(
        default=1000,
        alias="KAFKA_CONSUMER_POLL_TIMEOUT_MS",
    )
    celery_task_max_retries: int = Field(
        default=3,
        alias="CELERY_TASK_MAX_RETRIES",
    )
    celery_task_retry_backoff: int = Field(
        default=2,
        alias="CELERY_TASK_RETRY_BACKOFF",
    )
    resume_upload_dir: str = Field(
        default="uploads/resumes", alias="RESUME_UPLOAD_DIR")
    max_resume_size_bytes: int = Field(
        default=10 * 1024 * 1024, alias="MAX_RESUME_SIZE_BYTES")
    jd_upload_dir: str = Field(
        default="uploads/job_descriptions", alias="JD_UPLOAD_DIR")
    max_jd_size_bytes: int = Field(
        default=10 * 1024 * 1024, alias="MAX_JD_SIZE_BYTES")
    max_applications_per_candidate: int = Field(
        default=5,
        alias="MAX_APPLICATIONS_PER_CANDIDATE",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
