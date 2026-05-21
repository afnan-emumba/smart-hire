from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.application_states import ApplicationStatus
from app.db.models import Application, Job
from app.schemas.application import ApplicationCreate


class ApplicationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        application_create: ApplicationCreate,
        *,
        candidate_id: uuid.UUID,
        status: ApplicationStatus,
    ) -> Application:
        application = Application(
            **application_create.model_dump(),
            candidate_id=candidate_id,
            status=status.value,
        )
        self.session.add(application)
        await self.session.flush()
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

    async def list_by_candidate(
        self,
        candidate_id: uuid.UUID,
        *,
        status_filter: str | None,
        limit: int,
        offset: int,
    ) -> list[Application]:
        stmt = select(Application).where(Application.candidate_id == candidate_id)
        if status_filter is not None:
            stmt = stmt.where(Application.status == status_filter)
        result = await self.session.execute(
            stmt.order_by(Application.created_at.desc()).limit(limit).offset(offset)
        )
        return list(result.scalars().all())

    async def list_by_job(
        self,
        job_id: uuid.UUID,
        *,
        status_filter: str | None,
        limit: int,
        offset: int,
    ) -> list[Application]:
        stmt = select(Application).where(Application.job_id == job_id)
        if status_filter is not None:
            stmt = stmt.where(Application.status == status_filter)
        result = await self.session.execute(
            stmt.order_by(Application.created_at.desc()).limit(limit).offset(offset)
        )
        return list(result.scalars().all())

    async def list_all(
        self,
        *,
        status_filter: str | None,
        limit: int,
        offset: int,
    ) -> list[Application]:
        stmt = select(Application)
        if status_filter is not None:
            stmt = stmt.where(Application.status == status_filter)
        result = await self.session.execute(
            stmt.order_by(Application.created_at.desc()).limit(limit).offset(offset)
        )
        return list(result.scalars().all())

    async def list_by_recruiter(
        self,
        recruiter_id: uuid.UUID,
        *,
        status_filter: str | None,
        limit: int,
        offset: int,
    ) -> list[Application]:
        stmt = (
            select(Application)
            .join(Job, Job.id == Application.job_id)
            .where(Job.recruiter_id == recruiter_id)
        )
        if status_filter is not None:
            stmt = stmt.where(Application.status == status_filter)
        result = await self.session.execute(
            stmt.order_by(Application.created_at.desc()).limit(limit).offset(offset)
        )
        return list(result.scalars().all())

    async def update_status(
        self,
        application: Application,
        *,
        status: ApplicationStatus,
    ) -> Application:
        application.status = status.value
        await self.session.flush()
        await self.session.refresh(application)
        return application

    async def update_metadata(
        self,
        application: Application,
        *,
        metadata: dict,
    ) -> Application:
        application.application_metadata = metadata
        await self.session.flush()
        await self.session.refresh(application)
        return application

    async def update_resume_parsing(
        self,
        application: Application,
        *,
        resume_data: dict | None,
        metadata: dict,
    ) -> Application:
        application.resume_data = resume_data
        application.application_metadata = metadata
        await self.session.flush()
        await self.session.refresh(application)
        return application

    async def attach_resume(
        self,
        application: Application,
        *,
        file_name: str,
        content_type: str,
        storage_path: str,
        uploaded_at: datetime,
    ) -> Application:
        application.resume_file_name = file_name
        application.resume_content_type = content_type
        application.resume_storage_path = storage_path
        application.resume_uploaded_at = uploaded_at
        application.resume_data = None

        await self.session.flush()
        await self.session.refresh(application)
        return application