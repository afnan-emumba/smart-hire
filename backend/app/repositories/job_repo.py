from __future__ import annotations

import uuid
from typing import Any, Mapping

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Job
from app.schemas.job import JobCreate


class JobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, job_create: JobCreate, *, recruiter_id: uuid.UUID) -> Job:
        job = Job(**job_create.model_dump(), recruiter_id=recruiter_id)
        self.session.add(job)
        await self.session.flush()
        await self.session.refresh(job)
        return job

    async def get_by_id(self, job_id: uuid.UUID) -> Job | None:
        result = await self.session.execute(select(Job).where(Job.id == job_id))
        return result.scalar_one_or_none()

    async def list_by_recruiter(
        self,
        recruiter_id: uuid.UUID,
        *,
        status_filter: str | None,
        limit: int,
        offset: int,
    ) -> list[Job]:
        stmt = select(Job).where(Job.recruiter_id == recruiter_id)
        if status_filter is not None:
            stmt = stmt.where(Job.status == status_filter)
        result = await self.session.execute(
            stmt
            .order_by(Job.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def list_all(
        self,
        *,
        status_filter: str | None,
        limit: int,
        offset: int,
    ) -> list[Job]:
        stmt = select(Job)
        if status_filter is not None:
            stmt = stmt.where(Job.status == status_filter)
        result = await self.session.execute(
            stmt.order_by(Job.created_at.desc()).limit(limit).offset(offset)
        )
        return list(result.scalars().all())

    async def update(self, job_id: uuid.UUID, updates: Mapping[str, Any]) -> Job | None:
        update_values = dict(updates)
        if not update_values:
            return await self.get_by_id(job_id)

        job = await self.get_by_id(job_id)
        if job is None:
            return None

        for field_name, value in update_values.items():
            setattr(job, field_name, value)

        await self.session.flush()
        await self.session.refresh(job)
        return job

    async def delete(self, job_id: uuid.UUID) -> bool:
        job = await self.get_by_id(job_id)
        if job is None:
            return False

        await self.session.delete(job)
        await self.session.flush()
        return True