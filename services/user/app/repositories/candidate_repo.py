from __future__ import annotations

import uuid
from typing import Any, Mapping

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Candidate
from app.schemas.candidate import CandidateCreate
from contracts.enums import DeletionState


class CandidateRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self, candidate_create: CandidateCreate, candidate_id: uuid.UUID
    ) -> Candidate:
        candidate = Candidate(
            id=candidate_id, **candidate_create.model_dump(mode="json")
        )
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
            select(Candidate).where(func.lower(Candidate.email) == email.lower())
        )
        return result.scalar_one_or_none()

    async def list_all(self, *, limit: int, offset: int) -> list[Candidate]:
        result = await self.session.execute(
            select(Candidate)
            .where(Candidate.deletion_state == DeletionState.ACTIVE.value)
            .order_by(Candidate.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def mark_deleting(self, candidate_id: uuid.UUID) -> bool:
        candidate = await self.get_by_id(candidate_id)
        if candidate is None:
            return False

        candidate.deletion_state = DeletionState.DELETING.value
        await self.session.flush()
        return True

    async def update(
        self, candidate_id: uuid.UUID, updates: Mapping[str, Any]
    ) -> Candidate | None:
        update_values = dict(updates)
        if not update_values:
            return await self.get_by_id(candidate_id)

        candidate = await self.get_by_id(candidate_id)
        if candidate is None:
            return None

        for field_name, value in update_values.items():
            setattr(candidate, field_name, value)

        await self.session.flush()
        await self.session.refresh(candidate)
        return candidate

    async def delete(self, candidate_id: uuid.UUID) -> bool:
        candidate = await self.get_by_id(candidate_id)
        if candidate is None:
            return False

        await self.session.delete(candidate)
        await self.session.flush()
        return True
