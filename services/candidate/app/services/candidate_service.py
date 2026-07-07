from __future__ import annotations

import asyncio
import logging
import uuid

from app.clients.application_client import ApplicationClient
from app.clients.resume_client import ResumeClient
from app.repositories.candidate_repo import CandidateRepository
from app.schemas.candidate import (CandidateCreate, CandidateResponse,
                                   CandidateUpdate)
from auth.actors import require_candidate_user_id
from auth.header_auth import CurrentUser
from db.base import is_unique_violation
from exceptions.http_exceptions import (ConflictError, ForbiddenError,
                                        NotFoundError, ServiceUnavailableError)
from sqlalchemy.exc import IntegrityError

logger = logging.getLogger(__name__)


class CandidateService:
    def __init__(
        self,
        candidate_repo: CandidateRepository,
        resume_client: ResumeClient,
        application_client: ApplicationClient,
    ) -> None:
        self.candidate_repo = candidate_repo
        self.resume_client = resume_client
        self.application_client = application_client

    async def create_candidate(self, candidate_create: CandidateCreate) -> CandidateResponse:
        existing_candidate = await self.candidate_repo.get_by_email(candidate_create.email)
        if existing_candidate is not None:
            raise ConflictError("Candidate with this email already exists")

        try:
            candidate = await self.candidate_repo.create(candidate_create)
        except IntegrityError as exc:
            if is_unique_violation(exc):
                logger.info(
                    "Candidate creation conflicted with a concurrent request",
                    extra={"email": candidate_create.email},
                )
                raise ConflictError("Candidate with this email already exists") from exc
            logger.exception(
                "Failed to create candidate",
                extra={"email": candidate_create.email},
            )
            raise

        return CandidateResponse.model_validate(candidate)

    async def get_candidate(
        self,
        candidate_id: uuid.UUID,
        current_user: CurrentUser,
    ) -> CandidateResponse:
        if current_user.role == "CANDIDATE" and current_user.id != str(candidate_id):
            raise ForbiddenError("Candidates can only view their own profile")

        candidate = await self.candidate_repo.get_by_id(candidate_id)
        if candidate is None:
            raise NotFoundError("Candidate not found")

        return CandidateResponse.model_validate(candidate)

    async def list_candidates(self, *, limit: int, offset: int) -> list[CandidateResponse]:
        candidates = await self.candidate_repo.list_all(limit=limit, offset=offset)
        return [CandidateResponse.model_validate(candidate) for candidate in candidates]

    async def update_candidate(
        self,
        candidate_id: uuid.UUID,
        candidate_update: CandidateUpdate,
        current_user: CurrentUser,
    ) -> CandidateResponse:
        owner_id = require_candidate_user_id(current_user)
        if owner_id != candidate_id:
            raise ForbiddenError("Not authorized to update this candidate")

        candidate = await self.candidate_repo.get_by_id(candidate_id)
        if candidate is None:
            raise NotFoundError("Candidate not found")

        if candidate_update.email is not None:
            existing_candidate = await self.candidate_repo.get_by_email(candidate_update.email)
            if existing_candidate is not None and existing_candidate.id != candidate_id:
                raise ConflictError("Candidate with this email already exists")

        try:
            updated_candidate = await self.candidate_repo.update(
                candidate_id,
                candidate_update.model_dump(mode="json", exclude_unset=True),
            )
        except IntegrityError as exc:
            if is_unique_violation(exc):
                logger.info(
                    "Candidate update conflicted with a concurrent request",
                    extra={"candidate_id": str(candidate_id), "email": candidate_update.email},
                )
                raise ConflictError("Candidate with this email already exists") from exc
            logger.exception(
                "Failed to update candidate",
                extra={"candidate_id": str(candidate_id)},
            )
            raise

        if updated_candidate is None:
            raise NotFoundError("Candidate not found")

        return CandidateResponse.model_validate(updated_candidate)

    async def delete_candidate(self, candidate_id: uuid.UUID, current_user: CurrentUser) -> None:
        owner_id = require_candidate_user_id(current_user)
        if owner_id != candidate_id:
            raise ForbiddenError("Not authorized to delete this candidate")

        candidate = await self.candidate_repo.get_by_id(candidate_id)
        if candidate is None:
            raise NotFoundError("Candidate not found")

        results = await asyncio.gather(
            self.resume_client.delete_resumes_for_candidate(candidate_id, current_user),
            self.application_client.delete_applications_for_candidate(candidate_id, current_user),
            return_exceptions=True,
        )
        failures = [result for result in results if isinstance(result, Exception)]
        if failures:
            logger.error(
                "Failed to cascade-delete one or more of the candidate's dependents; "
                "candidate was not deleted, safe to retry",
                extra={"candidate_id": str(candidate_id)},
                exc_info=failures[0],
            )
            raise ServiceUnavailableError(
                "Failed to delete the candidate's resumes or applications; "
                "the candidate was not deleted, please retry"
            ) from failures[0]

        was_deleted = await self.candidate_repo.delete(candidate_id)
        if not was_deleted:
            raise NotFoundError("Candidate not found")

