from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from app.temporal.activities import finalize_job_breakdown, mark_job_ready


@dataclass
class JobPublishingInput:
    job_id: str


@workflow.defn(name="job-publishing-workflow")
class JobPublishingWorkflow:
    @workflow.run
    async def run(self, input: JobPublishingInput) -> dict[str, str]:
        retry_policy = RetryPolicy(
            initial_interval=timedelta(seconds=1),
            backoff_coefficient=2.0,
            maximum_interval=timedelta(seconds=10),
            maximum_attempts=3,
        )

        try:
            breakdown_result = await workflow.execute_activity(
                finalize_job_breakdown,
                input.job_id,
                start_to_close_timeout=timedelta(minutes=3),
                retry_policy=retry_policy,
            )
            if not breakdown_result.get("breakdown_validated"):
                return {
                    "status": "failed",
                    "job_id": input.job_id,
                    "error": "Job breakdown validation failed",
                }

            ready_result = await workflow.execute_activity(
                mark_job_ready,
                input.job_id,
                start_to_close_timeout=timedelta(minutes=1),
                retry_policy=retry_policy,
            )
            return {
                "status": "success",
                "job_id": input.job_id,
                "job_status": ready_result["status"],
            }
        except Exception as exc:
            return {
                "status": "failed",
                "job_id": input.job_id,
                "error": str(exc),
            }