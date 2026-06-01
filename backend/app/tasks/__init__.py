from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from typing import Any, TypeVar

from sqlalchemy.ext.asyncio import AsyncSession

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


def run_async_task(awaitable: Awaitable[TaskResult]) -> TaskResult:
    return asyncio.run(awaitable)


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