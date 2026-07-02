from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db_session
from app.repositories.job_repo import JobRepository
from app.services.job_service import JobService


async def get_job_service(
    session: AsyncSession = Depends(get_db_session),
) -> JobService:
    return JobService(job_repo=JobRepository(session), settings=get_settings())
