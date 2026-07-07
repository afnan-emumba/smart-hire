from __future__ import annotations

from app.core.config import get_settings
from app.db.session import get_db_session
from app.repositories.job_repo import JobRepository
from app.services.job_service import JobService
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession


async def get_job_service(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> JobService:
    return JobService(
        job_repo=JobRepository(session),
        settings=get_settings(),
        recruiter_client=request.app.state.recruiter_client,
        application_client=request.app.state.application_client,
    )
