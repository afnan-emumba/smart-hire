from __future__ import annotations

import uuid

from app.core.auth import CurrentUser
from app.repositories.candidate_repo import CandidateRepository
from app.schemas.candidate import CandidateCreate, CandidateResponse, CandidateUpdate
from app.services.exceptions import BadRequestError, ConflictError, ForbiddenError, NotFoundError


class CandidateService:
    def __init__(self, candidate_repo: CandidateRepository) -> None:
        self.candidate_repo = candidate_repo

    async def create_candidate(self, candidate_create: CandidateCreate) -> CandidateResponse:
        existing_candidate = await self.candidate_repo.get_by_email(candidate_create.email)
        if existing_candidate is not None:
            raise ConflictError("Candidate with this email already exists")

        candidate = await self.candidate_repo.create(candidate_create)
        return CandidateResponse.model_validate(candidate)

    async def get_candidate(self, candidate_id: uuid.UUID) -> CandidateResponse:
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
        owner_id = self._require_candidate_user_id(current_user)
        if owner_id != candidate_id:
            raise ForbiddenError("Not authorized to update this candidate")

        candidate = await self.candidate_repo.get_by_id(candidate_id)
        if candidate is None:
            raise NotFoundError("Candidate not found")

        if candidate_update.email is not None:
            existing_candidate = await self.candidate_repo.get_by_email(candidate_update.email)
            if existing_candidate is not None and existing_candidate.id != candidate_id:
                raise ConflictError("Candidate with this email already exists")

        updated_candidate = await self.candidate_repo.update(
            candidate_id,
            candidate_update.model_dump(mode="json", exclude_unset=True),
        )
        if updated_candidate is None:
            raise NotFoundError("Candidate not found")

        return CandidateResponse.model_validate(updated_candidate)

    async def delete_candidate(self, candidate_id: uuid.UUID, current_user: CurrentUser) -> None:
        owner_id = self._require_candidate_user_id(current_user)
        if owner_id != candidate_id:
            raise ForbiddenError("Not authorized to delete this candidate")

        candidate = await self.candidate_repo.get_by_id(candidate_id)
        if candidate is None:
            raise NotFoundError("Candidate not found")

        was_deleted = await self.candidate_repo.delete(candidate_id)
        if not was_deleted:
            raise NotFoundError("Candidate not found")

    @staticmethod
    def _require_candidate_user_id(current_user: CurrentUser) -> uuid.UUID:
        if current_user.role != "CANDIDATE":
            raise ForbiddenError("Only candidates can perform this action")

        try:
            return uuid.UUID(current_user.id)
        except ValueError as exc:
            raise BadRequestError(
                "X-User-ID must be a valid candidate UUID") from exc
