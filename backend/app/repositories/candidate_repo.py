from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Candidate
from app.schemas.candidate import CandidateCreate


class CandidateRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, candidate_create: CandidateCreate) -> Candidate:
        candidate = Candidate(**candidate_create.model_dump())
        self.session.add(candidate)
        await self.session.flush()
        await self.session.refresh(candidate)
        return candidate

    async def get_by_id(self, candidate_id: uuid.UUID) -> Candidate | None:
        result = await self.session.execute(
            select(Candidate).where(Candidate.id == candidate_id)
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> Candidate | None:
        result = await self.session.execute(
            select(Candidate).where(Candidate.email == email)
        )
        return result.scalar_one_or_none()

    async def list_all(self, *, limit: int, offset: int) -> list[Candidate]:
        result = await self.session.execute(
            select(Candidate)
            .order_by(Candidate.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())