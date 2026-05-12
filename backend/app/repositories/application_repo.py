from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Application
from app.schemas.application import ApplicationCreate


class ApplicationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, application_create: ApplicationCreate) -> Application:
        application = Application(**application_create.model_dump())
        self.session.add(application)
        await self.session.commit()
        await self.session.refresh(application)
        return application

    async def get_by_id(self, application_id: uuid.UUID) -> Application | None:
        result = await self.session.execute(
            select(Application).where(Application.id == application_id)
        )
        return result.scalar_one_or_none()

    async def get_by_job_and_candidate(
        self,
        job_id: uuid.UUID,
        candidate_id: uuid.UUID,
    ) -> Application | None:
        result = await self.session.execute(
            select(Application).where(
                Application.job_id == job_id,
                Application.candidate_id == candidate_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_by_candidate(self, candidate_id: uuid.UUID) -> list[Application]:
        result = await self.session.execute(
            select(Application)
            .where(Application.candidate_id == candidate_id)
            .order_by(Application.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_by_job(self, job_id: uuid.UUID) -> list[Application]:
        result = await self.session.execute(
            select(Application)
            .where(Application.job_id == job_id)
            .order_by(Application.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_all(self) -> list[Application]:
        result = await self.session.execute(
            select(Application).order_by(Application.created_at.desc())
        )
        return list(result.scalars().all())