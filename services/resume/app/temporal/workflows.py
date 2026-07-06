from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy


@dataclass
class ResumeParsingWorkflowInput:
    resume_id: str


@workflow.defn(name="resume-parsing-workflow")
class ResumeParsingWorkflow:
    @workflow.run
    async def run(self, input: ResumeParsingWorkflowInput) -> dict[str, str]:
        retry_policy = RetryPolicy(
            initial_interval=timedelta(seconds=1),
            backoff_coefficient=2.0,
            maximum_interval=timedelta(seconds=10),
            maximum_attempts=5,
        )

        result = await workflow.execute_activity(
            "parse_resume",
            input.resume_id,
            start_to_close_timeout=timedelta(minutes=3),
            retry_policy=retry_policy,
        )
        return {
            "status": "success",
            "resume_id": input.resume_id,
            "parsing_status": result.get("parsing_status", "failed"),
        }
