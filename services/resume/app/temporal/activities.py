from __future__ import annotations

import uuid
from typing import Any

from temporalio import activity
from temporalio.exceptions import ApplicationError

from app.clients.candidate_client import CandidateClient
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.repositories.resume_repo import ResumeRepository
from app.services.resume_service import ResumeService
from exceptions.http_exceptions import NotFoundError


_NON_RETRYABLE_ERRORS = (NotFoundError,)


@activity.defn
async def parse_resume(resume_id: str) -> dict[str, Any]:
    parsed_resume_id = uuid.UUID(resume_id)
    activity.logger.info("Parsing uploaded resume", extra={"resume_id": resume_id})

    settings = get_settings()
    candidate_client = CandidateClient(settings)
    try:
        async with SessionLocal() as session:
            service = ResumeService(
                resume_repo=ResumeRepository(session),
                settings=settings,
                candidate_client=candidate_client,
            )
            try:
                result = await service.process_resume_parsing(parsed_resume_id)
                await session.commit()
                return result
            except _NON_RETRYABLE_ERRORS as exc:
                await session.rollback()
                raise ApplicationError(str(exc), type=type(exc).__name__, non_retryable=True) from exc
            except Exception:
                await session.rollback()
                raise
    finally:
        await candidate_client.aclose()
