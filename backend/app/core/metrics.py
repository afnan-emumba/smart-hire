from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from time import perf_counter
from typing import Any

from fastapi import Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session


logger = logging.getLogger(__name__)

_PENDING_METRICS_KEY = "smarthire_pending_metrics"

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

JOBS_PUBLISHED_TOTAL = Counter(
    "jobs_published_total",
    "Total jobs published after durable state transition to ready.",
)

APPLICATIONS_RECEIVED_TOTAL = Counter(
    "applications_received_total",
    "Total applications received after durable persistence.",
)

WORKFLOW_EXECUTION_TIME_SECONDS = Histogram(
    "workflow_execution_time_seconds",
    "Workflow execution duration in seconds.",
    labelnames=("workflow_name", "status"),
)

TASK_EXECUTIONS_TOTAL = Counter(
    "smarthire_task_executions_total",
    "Background task executions by outcome.",
    labelnames=("task_name", "status"),
)


@dataclass(slots=True)
class _DeferredMetric:
    callback: Callable[[], None]


@event.listens_for(Session, "after_commit")
def _flush_pending_metrics(session: Session) -> None:
    callbacks: list[_DeferredMetric] = session.info.pop(_PENDING_METRICS_KEY, [])
    for deferred_metric in callbacks:
        try:
            deferred_metric.callback()
        except Exception:
            logger.exception("Deferred metric callback failed")


@event.listens_for(Session, "after_rollback")
def _clear_pending_metrics(session: Session) -> None:
    session.info.pop(_PENDING_METRICS_KEY, None)


def queue_post_commit_metric(session: AsyncSession, callback: Callable[[], None]) -> None:
    pending_callbacks = session.sync_session.info.setdefault(_PENDING_METRICS_KEY, [])
    pending_callbacks.append(_DeferredMetric(callback=callback))


def queue_jobs_published_increment(session: AsyncSession) -> None:
    """
    Directly increment jobs published counter.
    Called after job state transitions to READY.
    """
    JOBS_PUBLISHED_TOTAL.inc()


def queue_applications_received_increment(session: AsyncSession) -> None:
    """
    Directly increment applications received counter.
    Called after application is persisted.
    """
    APPLICATIONS_RECEIVED_TOTAL.inc()


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


def build_metrics_response() -> Response:
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