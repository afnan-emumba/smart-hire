from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel


class AnalyticsNewApplicationsPoint(BaseModel):
    date: date
    applications: int


class AnalyticsMostAppliedJob(BaseModel):
    job_id: uuid.UUID
    job_title: str
    applications: int


class AnalyticsFailureSummary(BaseModel):
    total_failed_workflows_system_errors: int
    job_publishing_failures: int
    application_workflow_failures: int
    event_processing_failures: int
    outbox_publish_failures: int


class AnalyticsSummaryResponse(BaseModel):
    generated_at: datetime
    total_candidates: int
    total_recruiters: int
    total_jobs_published: int
    new_applications_over_time: list[AnalyticsNewApplicationsPoint]
    application_to_interview_rate: float
    average_time_to_hire_seconds: float | None
    average_time_to_hire_days: float | None
    most_applied_jobs: list[AnalyticsMostAppliedJob]
    average_applications_per_candidate: float
    failed_workflows_system_errors: AnalyticsFailureSummary
