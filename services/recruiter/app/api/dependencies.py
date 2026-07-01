from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.repositories.recruiter_repo import RecruiterRepository
from app.services.recruiter_service import RecruiterService


async def get_recruiter_service(
    session: AsyncSession = Depends(get_db_session),
) -> RecruiterService:
    return RecruiterService(RecruiterRepository(session))
