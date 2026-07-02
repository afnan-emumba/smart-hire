from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db_session
from app.repositories.resume_repo import ResumeRepository
from app.services.resume_service import ResumeService


async def get_resume_service(
    session: AsyncSession = Depends(get_db_session),
) -> ResumeService:
    return ResumeService(resume_repo=ResumeRepository(session), settings=get_settings())
