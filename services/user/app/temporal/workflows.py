from __future__ import annotations

import asyncio
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

from app.temporal.constants import (
    ACTIVITY_DELETE_CANDIDATE_APPLICATIONS,
    ACTIVITY_DELETE_CANDIDATE_RECORD,
    ACTIVITY_DELETE_CANDIDATE_RESUMES,
    ACTIVITY_DELETE_RECRUITER_RECORD,
    ACTIVITY_LIST_RECRUITER_JOB_IDS,
    CANDIDATE_DELETION_WORKFLOW_NAME,
    RECRUITER_DELETION_WORKFLOW_NAME,
)
from app.temporal.dto import (
    CandidateDeletionInput,
    JobDeletionInput,
    RecruiterDeletionInput,
)
from contracts.temporal import JOB_DELETION_TASK_QUEUE, JOB_DELETION_WORKFLOW_NAME
from temporal.constants import WORKFLOW_STATUS_SUCCESS
from temporal.schemas import (
    CandidateDeletionWorkflowResult,
    ListRecruiterJobsActivityResult,
    RecruiterDeletionWorkflowResult,
)

# Cascade steps retry until they succeed rather than giving up after N attempts;
# the workflow execution timeout is the real bound. A downstream service being
# down for minutes is an expected condition here, not a failure.
CASCADE_RETRY_POLICY = RetryPolicy(
    initial_interval=timedelta(seconds=1),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(minutes=1),
    maximum_attempts=0,
)

_DOWNSTREAM_ACTIVITY_TIMEOUT = timedelta(minutes=2)
_LOCAL_ACTIVITY_TIMEOUT = timedelta(minutes=1)


@workflow.defn(name=CANDIDATE_DELETION_WORKFLOW_NAME)
class CandidateDeletionWorkflow:
    @workflow.run
    async def run(self, input: CandidateDeletionInput) -> dict[str, str]:
        await asyncio.gather(
            workflow.execute_activity(
                ACTIVITY_DELETE_CANDIDATE_RESUMES,
                input,
                start_to_close_timeout=_DOWNSTREAM_ACTIVITY_TIMEOUT,
                retry_policy=CASCADE_RETRY_POLICY,
            ),
            workflow.execute_activity(
                ACTIVITY_DELETE_CANDIDATE_APPLICATIONS,
                input,
                start_to_close_timeout=_DOWNSTREAM_ACTIVITY_TIMEOUT,
                retry_policy=CASCADE_RETRY_POLICY,
            ),
        )

        await workflow.execute_activity(
            ACTIVITY_DELETE_CANDIDATE_RECORD,
            input,
            start_to_close_timeout=_LOCAL_ACTIVITY_TIMEOUT,
            retry_policy=CASCADE_RETRY_POLICY,
        )

        return CandidateDeletionWorkflowResult(
            status=WORKFLOW_STATUS_SUCCESS,
            candidate_id=input.candidate_id,
        ).model_dump(mode="json")


@workflow.defn(name=RECRUITER_DELETION_WORKFLOW_NAME)
class RecruiterDeletionWorkflow:
    @workflow.run
    async def run(self, input: RecruiterDeletionInput) -> dict[str, str]:
        listed = await workflow.execute_activity(
            ACTIVITY_LIST_RECRUITER_JOB_IDS,
            input,
            start_to_close_timeout=_DOWNSTREAM_ACTIVITY_TIMEOUT,
            retry_policy=CASCADE_RETRY_POLICY,
        )
        job_ids = ListRecruiterJobsActivityResult.model_validate(listed).job_ids

        if job_ids:
            await asyncio.gather(
                *(
                    workflow.execute_child_workflow(
                        JOB_DELETION_WORKFLOW_NAME,
                        JobDeletionInput(
                            job_id=str(job_id),
                            actor_user_id=input.actor_user_id,
                            actor_role=input.actor_role,
                        ),
                        id=f"job-deletion-{job_id}",
                        task_queue=JOB_DELETION_TASK_QUEUE,
                        execution_timeout=timedelta(hours=1),
                    )
                    for job_id in job_ids
                )
            )

        await workflow.execute_activity(
            ACTIVITY_DELETE_RECRUITER_RECORD,
            input,
            start_to_close_timeout=_LOCAL_ACTIVITY_TIMEOUT,
            retry_policy=CASCADE_RETRY_POLICY,
        )

        return RecruiterDeletionWorkflowResult(
            status=WORKFLOW_STATUS_SUCCESS,
            recruiter_id=input.recruiter_id,
            deleted_job_count=len(job_ids),
        ).model_dump(mode="json")
