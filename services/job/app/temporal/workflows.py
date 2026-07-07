from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ApplicationError

from app.temporal.constants import (
    ACTIVITY_FINALIZE_JOB_BREAKDOWN,
    ACTIVITY_MARK_JOB_READY,
    JOB_PUBLISHING_WORKFLOW_NAME,
)
from temporal.constants import WORKFLOW_STATUS_SUCCESS
from temporal.schemas import (
    JobBreakdownActivityResult,
    JobPublishingWorkflowResult,
    JobStatusActivityResult,
)


@dataclass
class JobPublishingInput:
    job_id: str


@workflow.defn(name=JOB_PUBLISHING_WORKFLOW_NAME)
class JobPublishingWorkflow:
    @workflow.run
    async def run(self, input: JobPublishingInput) -> dict[str, str]:
        retry_policy = RetryPolicy(
            initial_interval=timedelta(seconds=1),
            backoff_coefficient=2.0,
            maximum_interval=timedelta(seconds=10),
            maximum_attempts=3,
        )

        breakdown_result = await workflow.execute_activity(
            ACTIVITY_FINALIZE_JOB_BREAKDOWN,
            input.job_id,
            start_to_close_timeout=timedelta(minutes=3),
            retry_policy=retry_policy,
        )
        validated_breakdown = JobBreakdownActivityResult.model_validate(
            breakdown_result
        )
        if not validated_breakdown.breakdown_validated:
            raise ApplicationError(
                "Job breakdown validation failed",
                type="JobBreakdownValidationError",
                non_retryable=True,
            )

        ready_result = await workflow.execute_activity(
            ACTIVITY_MARK_JOB_READY,
            input.job_id,
            start_to_close_timeout=timedelta(minutes=1),
            retry_policy=retry_policy,
        )
        updated_job = JobStatusActivityResult.model_validate(ready_result)
        return JobPublishingWorkflowResult(
            status=WORKFLOW_STATUS_SUCCESS,
            job_id=input.job_id,
            job_status=updated_job.status,
        ).model_dump(mode="json")
