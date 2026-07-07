from __future__ import annotations

from app.clients.candidate_client import CandidateClient
from app.clients.job_client import JobClient
from app.clients.resume_client import ResumeClient
from app.core.config import get_settings
from app.db.session import get_db_session
from app.repositories.application_repo import ApplicationRepository
from app.services.application_service import ApplicationService
from app.services.eligibility_service import EligibilityService
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession


async def get_application_service(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> ApplicationService:
    settings = get_settings()
    application_repo = ApplicationRepository(session)
    job_client: JobClient = request.app.state.job_client
    candidate_client: CandidateClient = request.app.state.candidate_client
    resume_client: ResumeClient = request.app.state.resume_client
    return ApplicationService(
        application_repo=application_repo,
        job_client=job_client,
        eligibility_service=EligibilityService(
            job_client=job_client,
            candidate_client=candidate_client,
            resume_client=resume_client,
            application_repo=application_repo,
            settings=settings,
        ),
        settings=settings,
    )
