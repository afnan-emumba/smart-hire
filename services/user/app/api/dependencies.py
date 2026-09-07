from __future__ import annotations

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db_session
from app.repositories.candidate_repo import CandidateRepository
from app.repositories.recruiter_repo import RecruiterRepository
from app.services.candidate_service import CandidateService
from app.services.recruiter_service import RecruiterService


async def get_recruiter_service(
    session: AsyncSession = Depends(get_db_session),
) -> RecruiterService:
    return RecruiterService(RecruiterRepository(session), settings=get_settings())


async def get_candidate_service(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> CandidateService:
    return CandidateService(
        CandidateRepository(session),
        resume_client=request.app.state.resume_client,
        settings=get_settings(),
    )
