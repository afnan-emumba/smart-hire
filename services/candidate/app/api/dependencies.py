from __future__ import annotations

from app.clients.application_client import ApplicationClient
from app.clients.resume_client import ResumeClient
from app.db.session import get_db_session
from app.repositories.candidate_repo import CandidateRepository
from app.services.candidate_service import CandidateService
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession


async def get_candidate_service(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> CandidateService:
    return CandidateService(
        CandidateRepository(session),
        resume_client=request.app.state.resume_client,
        application_client=request.app.state.application_client,
    )
