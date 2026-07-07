from __future__ import annotations

import logging
import uuid

from sqlalchemy.exc import IntegrityError

from app.repositories.recruiter_repo import RecruiterRepository
from app.schemas.recruiter import RecruiterCreate, RecruiterResponse
from db.base import is_unique_violation
from exceptions.http_exceptions import ConflictError, NotFoundError

logger = logging.getLogger(__name__)


class RecruiterService:
    def __init__(self, recruiter_repo: RecruiterRepository) -> None:
        self.recruiter_repo = recruiter_repo

    async def create_recruiter(
        self, recruiter_create: RecruiterCreate
    ) -> RecruiterResponse:
        existing_recruiter = await self.recruiter_repo.get_by_email(
            recruiter_create.email
        )
        if existing_recruiter is not None:
            raise ConflictError("Recruiter with this email already exists")

        try:
            recruiter = await self.recruiter_repo.create(recruiter_create)
        except IntegrityError as exc:
            if is_unique_violation(exc):
                logger.info(
                    "Recruiter creation conflicted with a concurrent request",
                    extra={"email": recruiter_create.email},
                )
                raise ConflictError("Recruiter with this email already exists") from exc
            logger.exception(
                "Failed to create recruiter",
                extra={"email": recruiter_create.email},
            )
            raise

        return RecruiterResponse.model_validate(recruiter)

    async def get_recruiter(self, recruiter_id: uuid.UUID) -> RecruiterResponse:
        recruiter = await self.recruiter_repo.get_by_id(recruiter_id)
        if recruiter is None:
            raise NotFoundError("Recruiter not found")

        return RecruiterResponse.model_validate(recruiter)

    async def list_recruiters(
        self, *, limit: int, offset: int
    ) -> list[RecruiterResponse]:
        recruiters = await self.recruiter_repo.list_all(limit=limit, offset=offset)
        return [RecruiterResponse.model_validate(recruiter) for recruiter in recruiters]
