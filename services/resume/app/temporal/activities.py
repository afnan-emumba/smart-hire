from __future__ import annotations

import uuid
from typing import Any

from temporalio import activity

from app.clients.candidate_client import CandidateClient
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.repositories.resume_repo import ResumeRepository
from app.services.resume_service import ResumeService
from app.temporal.constants import ACTIVITY_PARSE_RESUME
from exceptions.http_exceptions import NotFoundError
from temporal.activity_runner import run_temporal_activity
from temporal.schemas import ResumeParsingActivityResult

_NON_RETRYABLE_ERRORS = (NotFoundError,)


@activity.defn(name=ACTIVITY_PARSE_RESUME)
async def parse_resume(resume_id: str) -> dict[str, Any]:
    parsed_resume_id = uuid.UUID(resume_id)
    activity.logger.info("Parsing uploaded resume", extra={"resume_id": resume_id})

    settings = get_settings()
    candidate_client = CandidateClient(settings)
    return await run_temporal_activity(
        session_factory=SessionLocal,
        build_service=lambda session: ResumeService(
            resume_repo=ResumeRepository(session),
            settings=settings,
            candidate_client=candidate_client,
        ),
        operation=lambda service: service.process_resume_parsing(parsed_resume_id),
        non_retryable_errors=_NON_RETRYABLE_ERRORS,
        clients=[candidate_client],
        serialize_result=lambda result: ResumeParsingActivityResult.model_validate(
            result
        ).model_dump(mode="json"),
    )
