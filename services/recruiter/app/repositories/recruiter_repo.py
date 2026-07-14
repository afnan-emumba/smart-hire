from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Recruiter
from app.schemas.recruiter import RecruiterCreate


class RecruiterRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, recruiter_create: RecruiterCreate) -> Recruiter:
        recruiter = Recruiter(**recruiter_create.model_dump())
        self.session.add(recruiter)
        await self.session.flush()
        await self.session.refresh(recruiter)
        return recruiter

    async def get_by_id(self, recruiter_id: uuid.UUID) -> Recruiter | None:
        result = await self.session.execute(
            select(Recruiter).where(Recruiter.id == recruiter_id)
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> Recruiter | None:
        result = await self.session.execute(
            select(Recruiter).where(func.lower(Recruiter.email) == email.lower())
        )
        return result.scalar_one_or_none()

    async def list_all(self, *, limit: int, offset: int) -> list[Recruiter]:
        result = await self.session.execute(
            select(Recruiter)
            .order_by(Recruiter.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())
