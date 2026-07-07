from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from app.temporal.constants import (ACTIVITY_PARSE_RESUME,
                                    RESUME_PARSING_WORKFLOW_NAME)
from contracts.enums import ResumeParsingStatus
from temporal.constants import WORKFLOW_STATUS_SUCCESS
from temporal.schemas import (ResumeParsingActivityResult,
                              ResumeParsingWorkflowResult)
from temporalio import workflow
from temporalio.common import RetryPolicy


@dataclass
class ResumeParsingWorkflowInput:
    resume_id: str


@workflow.defn(name=RESUME_PARSING_WORKFLOW_NAME)
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
            ACTIVITY_PARSE_RESUME,
            input.resume_id,
            start_to_close_timeout=timedelta(minutes=3),
            retry_policy=retry_policy,
        )
        parsed_result = ResumeParsingActivityResult.model_validate(result)
        return ResumeParsingWorkflowResult(
            status=WORKFLOW_STATUS_SUCCESS,
            resume_id=input.resume_id,
            parsing_status=parsed_result.parsing_status or ResumeParsingStatus.FAILED.value,
        ).model_dump(mode="json")
