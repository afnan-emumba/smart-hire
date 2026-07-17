from __future__ import annotations

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.repositories.candidate_repo import CandidateRepository
from app.repositories.recruiter_repo import RecruiterRepository
from app.services.candidate_service import CandidateService
from app.services.recruiter_service import RecruiterService
from app.services.user_lifecycle import UserLifecycleCoordinator


async def get_recruiter_service(
    session: AsyncSession = Depends(get_db_session),
) -> RecruiterService:
    return RecruiterService(RecruiterRepository(session))


async def get_candidate_service(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> CandidateService:
    lifecycle = UserLifecycleCoordinator(
        resume_client=request.app.state.resume_client,
        application_client=request.app.state.application_client,
    )
    return CandidateService(
        CandidateRepository(session),
        lifecycle=lifecycle,
        resume_client=request.app.state.resume_client,
    )
