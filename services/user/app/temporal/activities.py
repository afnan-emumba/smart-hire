from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from temporalio import activity
from temporalio.exceptions import ApplicationError

from app.clients.application_client import ApplicationClient
from app.clients.job_client import JobClient
from app.clients.resume_client import ResumeClient
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.repositories.candidate_repo import CandidateRepository
from app.repositories.recruiter_repo import RecruiterRepository
from app.temporal.constants import (
    ACTIVITY_DELETE_CANDIDATE_APPLICATIONS,
    ACTIVITY_DELETE_CANDIDATE_RECORD,
    ACTIVITY_DELETE_CANDIDATE_RESUMES,
    ACTIVITY_DELETE_RECRUITER_RECORD,
    ACTIVITY_LIST_RECRUITER_JOB_IDS,
)
from app.temporal.dto import CandidateDeletionInput, RecruiterDeletionInput
from auth.header_auth import CurrentUser
from contracts.enums import UserRole
from exceptions.http_exceptions import BadRequestError, ForbiddenError
from temporal.schemas import (
    DeleteCascadeActivityResult,
    ListRecruiterJobsActivityResult,
)

_NON_RETRYABLE_ERRORS = (BadRequestError, ForbiddenError)


def _actor(user_id: str, role: str) -> CurrentUser:
    return CurrentUser(id=user_id, role=UserRole(role))


async def _run_client_activity(
    operation: Callable[[], Awaitable[Any]],
    clients: tuple[Any, ...],
) -> Any:
    """Run an activity that only talks to other services over HTTP.

    Mirrors ``run_temporal_activity``'s non-retryable-error contract for
    activities that need no database session.
    """
    try:
        return await operation()
    except _NON_RETRYABLE_ERRORS as exc:
        raise ApplicationError(
            str(exc), type=type(exc).__name__, non_retryable=True
        ) from exc
    finally:
        for client in clients:
            await client.aclose()


@activity.defn(name=ACTIVITY_DELETE_CANDIDATE_RESUMES)
async def delete_candidate_resumes(input: CandidateDeletionInput) -> dict[str, Any]:
    candidate_id = uuid.UUID(input.candidate_id)
    activity.logger.info(
        "Deleting resumes for candidate", extra={"candidate_id": input.candidate_id}
    )

    resume_client = ResumeClient(get_settings())
    await _run_client_activity(
        lambda: resume_client.delete_resumes_for_candidate(
            candidate_id, _actor(input.actor_user_id, input.actor_role)
        ),
        (resume_client,),
    )
    return DeleteCascadeActivityResult(
        resource_id=candidate_id, deleted=True
    ).model_dump(mode="json")


@activity.defn(name=ACTIVITY_DELETE_CANDIDATE_APPLICATIONS)
async def delete_candidate_applications(
    input: CandidateDeletionInput,
) -> dict[str, Any]:
    candidate_id = uuid.UUID(input.candidate_id)
    activity.logger.info(
        "Deleting applications for candidate",
        extra={"candidate_id": input.candidate_id},
    )

    application_client = ApplicationClient(get_settings())
    await _run_client_activity(
        lambda: application_client.delete_applications_for_candidate(
            candidate_id, _actor(input.actor_user_id, input.actor_role)
        ),
        (application_client,),
    )
    return DeleteCascadeActivityResult(
        resource_id=candidate_id, deleted=True
    ).model_dump(mode="json")


@activity.defn(name=ACTIVITY_DELETE_CANDIDATE_RECORD)
async def delete_candidate_record(input: CandidateDeletionInput) -> dict[str, Any]:
    candidate_id = uuid.UUID(input.candidate_id)
    activity.logger.info(
        "Deleting candidate record", extra={"candidate_id": input.candidate_id}
    )

    async with SessionLocal() as session:
        try:
            deleted = await CandidateRepository(session).delete(candidate_id)
            await session.commit()
        except Exception:
            await session.rollback()
            raise

    return DeleteCascadeActivityResult(
        resource_id=candidate_id, deleted=deleted
    ).model_dump(mode="json")


@activity.defn(name=ACTIVITY_LIST_RECRUITER_JOB_IDS)
async def list_recruiter_job_ids(input: RecruiterDeletionInput) -> dict[str, Any]:
    recruiter_id = uuid.UUID(input.recruiter_id)
    activity.logger.info(
        "Listing jobs owned by recruiter", extra={"recruiter_id": input.recruiter_id}
    )

    job_client = JobClient(get_settings())
    job_ids = await _run_client_activity(
        lambda: job_client.list_job_ids_for_recruiter(
            recruiter_id, _actor(input.actor_user_id, input.actor_role)
        ),
        (job_client,),
    )
    return ListRecruiterJobsActivityResult(
        recruiter_id=recruiter_id, job_ids=job_ids
    ).model_dump(mode="json")


@activity.defn(name=ACTIVITY_DELETE_RECRUITER_RECORD)
async def delete_recruiter_record(input: RecruiterDeletionInput) -> dict[str, Any]:
    recruiter_id = uuid.UUID(input.recruiter_id)
    activity.logger.info(
        "Deleting recruiter record", extra={"recruiter_id": input.recruiter_id}
    )

    async with SessionLocal() as session:
        try:
            deleted = await RecruiterRepository(session).delete(recruiter_id)
            await session.commit()
        except Exception:
            await session.rollback()
            raise

    return DeleteCascadeActivityResult(
        resource_id=recruiter_id, deleted=deleted
    ).model_dump(mode="json")
