from __future__ import annotations

import uuid
from typing import Any, Mapping

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Job
from app.schemas.job import JobCreate


class JobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, job_create: JobCreate) -> Job:
        job = Job(**job_create.model_dump())
        self.session.add(job)
        await self.session.commit()
        await self.session.refresh(job)
        return job

    async def get_by_id(self, job_id: uuid.UUID) -> Job | None:
        result = await self.session.execute(select(Job).where(Job.id == job_id))
        return result.scalar_one_or_none()

    async def list_by_recruiter(self, recruiter_id: uuid.UUID) -> list[Job]:
        result = await self.session.execute(
            select(Job)
            .where(Job.recruiter_id == recruiter_id)
            .order_by(Job.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_all(self) -> list[Job]:
        result = await self.session.execute(select(Job).order_by(Job.created_at.desc()))
        return list(result.scalars().all())

    async def update(self, job_id: uuid.UUID, updates: Mapping[str, Any]) -> Job | None:
        update_values = dict(updates)
        if not update_values:
            return await self.get_by_id(job_id)

        result = await self.session.execute(
            update(Job)
            .where(Job.id == job_id)
            .values(**update_values)
            .returning(Job.id)
        )
        updated_job_id = result.scalar_one_or_none()
        if updated_job_id is None:
            await self.session.rollback()
            return None

        await self.session.commit()
        return await self.get_by_id(updated_job_id)

    async def delete(self, job_id: uuid.UUID) -> bool:
        result = await self.session.execute(delete(Job).where(Job.id == job_id))
        await self.session.commit()
        return bool(result.rowcount)