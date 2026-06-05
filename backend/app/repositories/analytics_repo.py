from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.application_states import ApplicationStatus
from app.core.enums import JobStatus
from app.db.models import Application, Candidate, EventProcessingRecord, Job, OutboxEvent, Recruiter


class AnalyticsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def count_candidates(self) -> int:
        result = await self.session.execute(select(func.count()).select_from(Candidate))
        return int(result.scalar_one())

    async def count_recruiters(self) -> int:
        result = await self.session.execute(select(func.count()).select_from(Recruiter))
        return int(result.scalar_one())

    async def count_total_applications(self) -> int:
        result = await self.session.execute(select(func.count()).select_from(Application))
        return int(result.scalar_one())

    async def count_published_jobs(self) -> int:
        result = await self.session.execute(
            select(func.count())
            .select_from(Job)
            .where((Job.status == JobStatus.READY.value) | Job.ready_at.is_not(None))
        )
        return int(result.scalar_one())

    async def count_interview_stage_applications(self) -> int:
        result = await self.session.execute(
            select(func.count())
            .select_from(Application)
            .where(
                (Application.status == ApplicationStatus.INTERVIEW.value)
                | Application.interview_started_at.is_not(None)
            )
        )
        return int(result.scalar_one())

    async def average_time_to_hire_seconds(self) -> float | None:
        result = await self.session.execute(
            select(func.avg(func.extract("epoch", Application.accepted_at - Application.created_at))).where(
                Application.accepted_at.is_not(None)
            )
        )
        value = result.scalar_one()
        return float(value) if value is not None else None

    async def list_new_applications_over_time(self) -> list[dict[str, Any]]:
        result = await self.session.execute(
            select(
                func.date(Application.created_at).label("application_date"),
                func.count(Application.id).label("application_count"),
            )
            .select_from(Application)
            .group_by(func.date(Application.created_at))
            .order_by(func.date(Application.created_at))
        )
        return [
            {
                "date": row.application_date,
                "applications": int(row.application_count),
            }
            for row in result.all()
        ]

    async def list_most_applied_jobs(self, *, limit: int = 5) -> list[dict[str, Any]]:
        result = await self.session.execute(
            select(
                Job.id.label("job_id"),
                Job.title.label("job_title"),
                func.count(Application.id).label("application_count"),
            )
            .select_from(Job)
            .join(Application, Application.job_id == Job.id)
            .group_by(Job.id, Job.title)
            .order_by(func.count(Application.id).desc(), Job.created_at.desc())
            .limit(limit)
        )
        return [
            {
                "job_id": row.job_id,
                "job_title": row.job_title,
                "applications": int(row.application_count),
            }
            for row in result.all()
        ]

    async def count_job_publishing_failures(self) -> int:
        result = await self.session.execute(
            select(func.count()).select_from(Job).where(
                Job.publishing_failed_at.is_not(None))
        )
        return int(result.scalar_one())

    async def count_application_workflow_failures(self) -> int:
        result = await self.session.execute(
            select(func.count()).select_from(Application).where(
                Application.workflow_failed_at.is_not(None))
        )
        return int(result.scalar_one())

    async def count_event_processing_failures(self) -> int:
        result = await self.session.execute(
            select(func.count())
            .select_from(EventProcessingRecord)
            .where(EventProcessingRecord.status == "failed")
        )
        return int(result.scalar_one())

    async def count_outbox_publish_failures(self) -> int:
        result = await self.session.execute(
            select(func.count()).select_from(OutboxEvent).where(
                OutboxEvent.publish_status == "failed")
        )
        return int(result.scalar_one())
