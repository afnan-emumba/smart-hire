from __future__ import annotations

from datetime import UTC, datetime

from app.repositories.analytics_repo import AnalyticsRepository
from app.schemas.analytics import (
    AnalyticsFailureSummary,
    AnalyticsMostAppliedJob,
    AnalyticsNewApplicationsPoint,
    AnalyticsSummaryResponse,
)


class AnalyticsService:
    def __init__(self, analytics_repo: AnalyticsRepository) -> None:
        self.analytics_repo = analytics_repo

    async def get_summary(self) -> AnalyticsSummaryResponse:
        total_candidates = await self.analytics_repo.count_candidates()
        total_recruiters = await self.analytics_repo.count_recruiters()
        total_jobs_published = await self.analytics_repo.count_published_jobs()
        total_applications = await self.analytics_repo.count_total_applications()
        interview_stage_applications = await self.analytics_repo.count_interview_stage_applications()
        average_time_to_hire_seconds = await self.analytics_repo.average_time_to_hire_seconds()
        new_applications_over_time_rows = await self.analytics_repo.list_new_applications_over_time()
        most_applied_job_rows = await self.analytics_repo.list_most_applied_jobs()
        job_publishing_failures = await self.analytics_repo.count_job_publishing_failures()
        application_workflow_failures = await self.analytics_repo.count_application_workflow_failures()
        event_processing_failures = await self.analytics_repo.count_event_processing_failures()
        outbox_publish_failures = await self.analytics_repo.count_outbox_publish_failures()

        failure_total = (
            job_publishing_failures
            + application_workflow_failures
            + event_processing_failures
            + outbox_publish_failures
        )
        application_to_interview_rate = (
            interview_stage_applications / total_applications if total_applications else 0.0
        )
        average_applications_per_candidate = (
            total_applications / total_candidates if total_candidates else 0.0
        )

        return AnalyticsSummaryResponse(
            generated_at=datetime.now(UTC),
            total_candidates=total_candidates,
            total_recruiters=total_recruiters,
            total_jobs_published=total_jobs_published,
            new_applications_over_time=[
                AnalyticsNewApplicationsPoint(**row) for row in new_applications_over_time_rows
            ],
            application_to_interview_rate=application_to_interview_rate,
            average_time_to_hire_seconds=average_time_to_hire_seconds,
            average_time_to_hire_days=(
                average_time_to_hire_seconds /
                86400 if average_time_to_hire_seconds is not None else None
            ),
            most_applied_jobs=[AnalyticsMostAppliedJob(
                **row) for row in most_applied_job_rows],
            average_applications_per_candidate=average_applications_per_candidate,
            failed_workflows_system_errors=AnalyticsFailureSummary(
                total_failed_workflows_system_errors=failure_total,
                job_publishing_failures=job_publishing_failures,
                application_workflow_failures=application_workflow_failures,
                event_processing_failures=event_processing_failures,
                outbox_publish_failures=outbox_publish_failures,
            ),
        )
