from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from threading import local
from typing import Any, TypeVar

from sqlalchemy.ext.asyncio import AsyncSession

try:
    from celery.signals import worker_process_shutdown
except ImportError:  # pragma: no cover
    worker_process_shutdown = None

from app.core.config import get_settings
from app.repositories.application_repo import ApplicationRepository
from app.repositories.candidate_repo import CandidateRepository
from app.repositories.candidate_resume_repo import CandidateResumeRepository
from app.repositories.job_repo import JobRepository
from app.repositories.outbox_repo import OutboxRepository
from app.repositories.recruiter_repo import RecruiterRepository
from app.services.application_service import ApplicationService
from app.services.eligibility_service import EligibilityService
from app.services.job_service import JobService


APPLICATION_SCORING_TASK = "app.tasks.scoring.process_application_scoring"
APPLICATION_RECEIVED_NOTIFICATION_TASK = "app.tasks.notifications.send_application_received_notification"
APPLICATION_ANALYTICS_TASK = "app.tasks.analytics.process_application_analytics"
JOB_ANALYTICS_TASK = "app.tasks.analytics.process_job_published_analytics"

TaskResult = TypeVar("TaskResult")

_task_runtime = local()


def _get_task_event_loop() -> asyncio.AbstractEventLoop:
    event_loop = getattr(_task_runtime, "event_loop", None)
    if event_loop is None or event_loop.is_closed():
        event_loop = asyncio.new_event_loop()
        _task_runtime.event_loop = event_loop
    return event_loop


def run_async_task(awaitable: Awaitable[TaskResult]) -> TaskResult:
    event_loop = _get_task_event_loop()
    return event_loop.run_until_complete(awaitable)


def close_task_event_loop() -> None:
    event_loop = getattr(_task_runtime, "event_loop", None)
    if event_loop is None or event_loop.is_closed():
        return

    event_loop.run_until_complete(event_loop.shutdown_asyncgens())
    event_loop.close()
    _task_runtime.event_loop = None


if worker_process_shutdown is not None:

    @worker_process_shutdown.connect
    def _close_worker_event_loop(**_: Any) -> None:
        close_task_event_loop()


def build_application_service(session: AsyncSession) -> ApplicationService:
    settings = get_settings()
    application_repo = ApplicationRepository(session)
    job_repo = JobRepository(session)
    candidate_repo = CandidateRepository(session)
    candidate_resume_repo = CandidateResumeRepository(session)
    return ApplicationService(
        application_repo=application_repo,
        job_repo=job_repo,
        candidate_repo=candidate_repo,
        candidate_resume_repo=candidate_resume_repo,
        outbox_repo=OutboxRepository(session),
        eligibility_service=EligibilityService(
            job_repo=job_repo,
            candidate_repo=candidate_repo,
            candidate_resume_repo=candidate_resume_repo,
            application_repo=application_repo,
            settings=settings,
        ),
        settings=settings,
    )


def build_job_service(session: AsyncSession) -> JobService:
    settings = get_settings()
    job_repo = JobRepository(session)
    return JobService(
        job_repo=job_repo,
        recruiter_repo=RecruiterRepository(session),
        outbox_repo=OutboxRepository(session),
        settings=settings,
    )


def normalize_skills(skills: list[Any] | None) -> set[str]:
    normalized: set[str] = set()
    for skill in skills or []:
        if isinstance(skill, str):
            cleaned = skill.strip().lower()
            if cleaned:
                normalized.add(cleaned)
    return normalized
