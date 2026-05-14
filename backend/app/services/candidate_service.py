from __future__ import annotations

import uuid

from app.repositories.candidate_repo import CandidateRepository
from app.services.exceptions import ConflictError, NotFoundError
from app.schemas.candidate import CandidateCreate, CandidateResponse


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