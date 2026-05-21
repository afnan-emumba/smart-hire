from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.core.config import get_settings
from app.repositories.application_repo import ApplicationRepository
from app.repositories.candidate_repo import CandidateRepository
from app.repositories.job_repo import JobRepository
from app.repositories.recruiter_repo import RecruiterRepository
from app.services.application_service import ApplicationService
from app.services.candidate_service import CandidateService
from app.services.eligibility_service import EligibilityService
from app.services.job_service import JobService
from app.services.recruiter_service import RecruiterService


async def get_recruiter_service(
    session: AsyncSession = Depends(get_db_session),
) -> RecruiterService:
    return RecruiterService(RecruiterRepository(session))


async def get_candidate_service(
    session: AsyncSession = Depends(get_db_session),
) -> CandidateService:
    return CandidateService(CandidateRepository(session))


async def get_job_service(session: AsyncSession = Depends(get_db_session)) -> JobService:
    return JobService(
        job_repo=JobRepository(session),
        recruiter_repo=RecruiterRepository(session),
        settings=get_settings(),
    )


async def get_application_service(
    session: AsyncSession = Depends(get_db_session),
) -> ApplicationService:
    application_repo = ApplicationRepository(session)
    job_repo = JobRepository(session)
    candidate_repo = CandidateRepository(session)
    return ApplicationService(
        application_repo=application_repo,
        job_repo=job_repo,
        candidate_repo=candidate_repo,
        eligibility_service=EligibilityService(
            job_repo=job_repo,
            candidate_repo=candidate_repo,
            application_repo=application_repo,
        ),
        settings=get_settings(),
    )