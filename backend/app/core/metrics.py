from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from time import perf_counter
from typing import Any

from fastapi import Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from sqlalchemy import event, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.core.enums import JobStatus
from app.core.health import collect_dependency_results
from app.db.models import Application, CandidateResume, EventProcessingRecord, Job
from app.db.session import SessionLocal


logger = logging.getLogger(__name__)

FAILURE_METRIC_WINDOW_SECONDS = 300

_PENDING_METRICS_KEY = "smarthire_pending_metrics"

TASK_HANDLER_DISPLAY_NAMES = {
    "app.tasks.analytics.process_application_analytics": "Application Analytics",
    "app.tasks.analytics.process_job_published_analytics": "Job Analytics",
    "app.tasks.notifications.send_application_received_notification": "Application Notification",
    "app.tasks.scoring.process_application_scoring": "Application Scoring",
}

WORKFLOW_DISPLAY_NAMES = {
    "job_publishing": "Job Publishing",
    "candidate_application_initialization": "Application Initialization",
}

DEPENDENCY_DISPLAY_NAMES = {
    "database": "PostgreSQL",
    "temporal": "Temporal",
    "kafka": "Kafka",
    "schema_registry": "Schema Registry",
    "rabbitmq": "RabbitMQ",
    "redis": "Redis",
}

PROCESSING_STATUS_DISPLAY_NAMES = {
    "pending": "Pending",
    "processing": "Processing",
    "parsed": "Parsed",
    "failed": "Failed",
    "unsupported": "Unsupported",
}


def get_task_display_name(handler_name: str) -> str:
    """Map Celery handler name to user-friendly display name."""
    return TASK_HANDLER_DISPLAY_NAMES.get(handler_name, handler_name)


def get_workflow_display_name(workflow_name: str) -> str:
    """Map workflow name to user-friendly display name."""
    return WORKFLOW_DISPLAY_NAMES.get(workflow_name, workflow_name)


HTTP_REQUESTS_TOTAL = Counter(
    "smarthire_http_requests_total",
    "Total HTTP requests handled by the API.",
    labelnames=("method", "path", "status_code"),
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "smarthire_http_request_duration_seconds",
    "HTTP request latency in seconds.",
    labelnames=("method", "path"),
)

HTTP_ERRORS_TOTAL = Counter(
    "smarthire_http_errors_total",
    "Total HTTP responses that returned 4xx or 5xx status codes.",
    labelnames=("method", "path", "status_code", "status_class"),
)

JOBS_PUBLISHED_TOTAL = Gauge(
    "jobs_published_total",
    "Total jobs published after durable state transition to ready.",
)

APPLICATIONS_RECEIVED_TOTAL = Gauge(
    "applications_received_total",
    "Total applications received after durable persistence.",
)

WORKFLOW_EXECUTION_TIME_SECONDS = Histogram(
    "workflow_execution_time_seconds",
    "Workflow execution duration in seconds.",
    labelnames=("workflow_name", "status"),
)

WORKFLOW_AVERAGE_DURATION_SECONDS = Gauge(
    "smarthire_workflow_average_duration_seconds",
    "Average workflow duration derived from durable workflow timestamps.",
    labelnames=("workflow_name", "status"),
)

TASK_EXECUTIONS_TOTAL = Counter(
    "smarthire_task_executions_total",
    "Background task executions by outcome.",
    labelnames=("task_name", "status"),
)

TASK_OUTCOMES_TOTAL = Gauge(
    "smarthire_task_outcomes_total",
    "Current durable task outcome totals derived from event processing records.",
    labelnames=("task_name", "status"),
)

JOB_PUBLISHING_FAILURES_TOTAL = Gauge(
    "smarthire_job_publishing_failures_total",
    "Current number of jobs with a recorded publishing failure.",
)

APPLICATION_WORKFLOW_FAILURES_TOTAL = Gauge(
    "smarthire_application_workflow_failures_total",
    "Current number of applications with a recorded workflow failure.",
)

RESUME_PROCESSING_TOTAL = Gauge(
    "smarthire_resume_processing_total",
    "Current candidate resume totals by parsing status.",
    labelnames=("status",),
)

JOB_DESCRIPTION_PROCESSING_TOTAL = Gauge(
    "smarthire_job_description_processing_total",
    "Current job description totals by parsing status.",
    labelnames=("status",),
)

DEPENDENCY_HEALTH_STATUS = Gauge(
    "smarthire_dependency_health_status",
    "Current dependency health where 1 is healthy and 0 is unhealthy.",
    labelnames=("dependency",),
)


@dataclass(slots=True)
class _DeferredMetric:
    callback: Callable[[], None]


@event.listens_for(Session, "after_commit")
def _flush_pending_metrics(session: Session) -> None:
    callbacks: list[_DeferredMetric] = session.info.pop(
        _PENDING_METRICS_KEY, [])
    for deferred_metric in callbacks:
        try:
            deferred_metric.callback()
        except Exception:
            logger.exception("Deferred metric callback failed")


@event.listens_for(Session, "after_rollback")
def _clear_pending_metrics(session: Session) -> None:
    session.info.pop(_PENDING_METRICS_KEY, None)


def queue_post_commit_metric(session: AsyncSession, callback: Callable[[], None]) -> None:
    pending_callbacks = session.sync_session.info.setdefault(
        _PENDING_METRICS_KEY, [])
    pending_callbacks.append(_DeferredMetric(callback=callback))


def queue_jobs_published_increment(session: AsyncSession) -> None:
    queue_post_commit_metric(
        session,
        JOBS_PUBLISHED_TOTAL.inc,
    )


def queue_applications_received_increment(session: AsyncSession) -> None:
    queue_post_commit_metric(
        session,
        APPLICATIONS_RECEIVED_TOTAL.inc,
    )


def queue_workflow_duration(
    session: AsyncSession,
    *,
    workflow_name: str,
    status: str,
    duration_seconds: float,
) -> None:
    queue_post_commit_metric(
        session,
        lambda: WORKFLOW_EXECUTION_TIME_SECONDS.labels(
            workflow_name=workflow_name,
            status=status,
        ).observe(duration_seconds),
    )


def record_task_execution(*, task_name: str, status: str) -> None:
    TASK_EXECUTIONS_TOTAL.labels(task_name=task_name, status=status).inc()


async def refresh_domain_metrics() -> None:
    failure_window_start = datetime.now(
        timezone.utc) - timedelta(seconds=FAILURE_METRIC_WINDOW_SECONDS)
    async with SessionLocal() as session:
        published_jobs_result = await session.execute(
            select(func.count()).select_from(Job).where(
                (Job.status == JobStatus.READY.value) | Job.ready_at.is_not(None)
            )
        )
        applications_received_result = await session.execute(
            select(func.count()).select_from(Application)
        )
        job_publishing_avg_result = await session.execute(
            select(func.avg(func.extract("epoch", Job.ready_at - Job.processing_started_at))).where(
                Job.processing_started_at.is_not(None),
                Job.ready_at.is_not(None),
            )
        )
        application_initialization_avg_result = await session.execute(
            select(func.avg(func.extract("epoch", Application.workflow_initialized_at - Application.created_at))).where(
                Application.workflow_initialized_at.is_not(None)
            )
        )
        task_outcomes_result = await session.execute(
            select(
                EventProcessingRecord.handler_name,
                EventProcessingRecord.status,
                func.count(),
            )
            .select_from(EventProcessingRecord)
            .group_by(
                EventProcessingRecord.handler_name,
                EventProcessingRecord.status,
            )
        )
        job_publishing_failures_result = await session.execute(
            select(func.count()).select_from(Job).where(
                Job.publishing_failed_at >= failure_window_start)
        )
        application_workflow_failures_result = await session.execute(
            select(func.count()).select_from(Application).where(
                Application.workflow_failed_at >= failure_window_start)
        )
        resume_processing_result = await session.execute(
            select(CandidateResume.parsing_status, func.count())
            .select_from(CandidateResume)
            .group_by(CandidateResume.parsing_status)
        )
        job_description_processing_result = await session.execute(
            select(Job.jd_parsing_status, func.count())
            .select_from(Job)
            .group_by(Job.jd_parsing_status)
        )
        dependency_results = await collect_dependency_results(session)

    JOBS_PUBLISHED_TOTAL.set(float(published_jobs_result.scalar_one()))
    APPLICATIONS_RECEIVED_TOTAL.set(
        float(applications_received_result.scalar_one()))
    JOB_PUBLISHING_FAILURES_TOTAL.set(
        float(job_publishing_failures_result.scalar_one()))
    APPLICATION_WORKFLOW_FAILURES_TOTAL.set(
        float(application_workflow_failures_result.scalar_one()))
    WORKFLOW_AVERAGE_DURATION_SECONDS.labels(
        workflow_name=get_workflow_display_name("job_publishing"),
        status="success",
    ).set(float(job_publishing_avg_result.scalar_one() or 0.0))
    WORKFLOW_AVERAGE_DURATION_SECONDS.labels(
        workflow_name=get_workflow_display_name(
            "candidate_application_initialization"),
        status="success",
    ).set(float(application_initialization_avg_result.scalar_one() or 0.0))
    TASK_OUTCOMES_TOTAL.clear()
    for task_name, status, total in task_outcomes_result.all():
        TASK_OUTCOMES_TOTAL.labels(
            task_name=get_task_display_name(task_name),
            status=status,
        ).set(float(total))
    RESUME_PROCESSING_TOTAL.clear()
    for status, total in resume_processing_result.all():
        RESUME_PROCESSING_TOTAL.labels(
            status=PROCESSING_STATUS_DISPLAY_NAMES.get(status, status.title()),
        ).set(float(total))
    JOB_DESCRIPTION_PROCESSING_TOTAL.clear()
    for status, total in job_description_processing_result.all():
        JOB_DESCRIPTION_PROCESSING_TOTAL.labels(
            status=PROCESSING_STATUS_DISPLAY_NAMES.get(status, status.title()),
        ).set(float(total))
    DEPENDENCY_HEALTH_STATUS.clear()
    for dependency_name, result in dependency_results.items():
        DEPENDENCY_HEALTH_STATUS.labels(
            dependency=DEPENDENCY_DISPLAY_NAMES.get(
                dependency_name, dependency_name.replace("_", " ").title()),
        ).set(1.0 if result["status"] == "up" else 0.0)


async def build_metrics_response() -> Response:
    try:
        await refresh_domain_metrics()
    except SQLAlchemyError:
        logger.exception(
            "Failed to refresh domain metrics; returning last known metric values")
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


async def record_http_metrics(request: Request, call_next: Callable[[Request], Any]) -> Response:
    started_at = perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        route = request.scope.get("route")
        route_path = getattr(route, "path", request.url.path)
        HTTP_REQUESTS_TOTAL.labels(
            method=request.method,
            path=route_path,
            status_code=str(status_code),
        ).inc()
        HTTP_REQUEST_DURATION_SECONDS.labels(
            method=request.method,
            path=route_path,
        ).observe(perf_counter() - started_at)
        if status_code >= 400:
            HTTP_ERRORS_TOTAL.labels(
                method=request.method,
                path=route_path,
                status_code=str(status_code),
                status_class=f"{status_code // 100}xx",
            ).inc()
