from __future__ import annotations

import asyncio
import uuid

from app.clients.candidate_client import CandidateClient
from app.clients.job_client import JobClient
from app.clients.resume_client import ResumeClient
from app.core.config import Settings
from app.repositories.application_repo import ApplicationRepository
from app.schemas.application import EligibilityReasonCode, EligibilityResult
from auth.header_auth import CurrentUser
from contracts.enums import JobStatus
from contracts.service_responses import CandidateMasterProfileContract
from db.deletion import ensure_not_deleting
from exceptions.http_exceptions import NotFoundError


class EligibilityService:
    def __init__(
        self,
        job_client: JobClient,
        candidate_client: CandidateClient,
        resume_client: ResumeClient,
        application_repo: ApplicationRepository,
        settings: Settings,
    ) -> None:
        self.job_client = job_client
        self.candidate_client = candidate_client
        self.resume_client = resume_client
        self.application_repo = application_repo
        self.settings = settings

    async def check_eligibility(
        self,
        candidate_id: uuid.UUID,
        job_id: uuid.UUID,
        current_user: CurrentUser,
    ) -> EligibilityResult:
        existing_application = await self.application_repo.get_by_job_and_candidate(
            job_id,
            candidate_id,
        )
        if existing_application is not None:
            return EligibilityResult(
                is_eligible=False,
                reason_code=EligibilityReasonCode.DUPLICATE_APPLICATION,
                reason="You have already applied to this job",
                match_score=0.0,
            )

        active_application_count = (
            await self.application_repo.count_active_by_candidate(candidate_id)
        )
        if active_application_count >= self.settings.max_applications_per_candidate:
            return EligibilityResult(
                is_eligible=False,
                reason_code=EligibilityReasonCode.MAX_ACTIVE_APPLICATIONS,
                reason=(
                    "You have reached the maximum of "
                    f"{self.settings.max_applications_per_candidate} active applications"
                ),
                match_score=0.0,
            )

        job, candidate = await asyncio.gather(
            self.job_client.get_job(job_id, current_user),
            self.candidate_client.get_candidate(candidate_id, current_user),
        )
        if job is None:
            raise NotFoundError("Job not found")
        if candidate is None:
            raise NotFoundError("Candidate not found")
        ensure_not_deleting(job, "Job is being deleted")
        ensure_not_deleting(candidate, "Candidate is being deleted")

        if job.status != JobStatus.READY:
            return EligibilityResult(
                is_eligible=False,
                reason_code=EligibilityReasonCode.JOB_NOT_READY,
                reason="Job is not yet published",
                match_score=0.0,
            )

        candidate_skills, resume_id = await self._resolve_candidate_skills(
            candidate_id,
            candidate.master_profile_data,
            current_user,
        )
        required_skills = self._normalize_skills(job.required_skills)

        if not required_skills:
            return EligibilityResult(
                is_eligible=True,
                reason_code=EligibilityReasonCode.NO_REQUIRED_SKILLS,
                reason="Job has no required skills configured",
                match_score=1.0,
                resume_id=resume_id,
            )

        matched_skills = candidate_skills & required_skills
        match_score = len(matched_skills) / len(required_skills)
        missing_skills = sorted(required_skills - candidate_skills)

        if match_score < 0.5:
            return EligibilityResult(
                is_eligible=False,
                reason_code=EligibilityReasonCode.INSUFFICIENT_SKILLS,
                reason="You don't have enough required skills",
                missing_skills=missing_skills,
                match_score=match_score,
                resume_id=resume_id,
            )

        return EligibilityResult(
            is_eligible=True,
            reason_code=EligibilityReasonCode.ELIGIBLE,
            reason="You meet the job requirements",
            missing_skills=missing_skills,
            match_score=match_score,
            resume_id=resume_id,
        )

    @staticmethod
    def _normalize_skills(skills: list[object]) -> set[str]:
        normalized: set[str] = set()
        for skill in skills:
            if isinstance(skill, str):
                cleaned = skill.strip().lower()
                if cleaned:
                    normalized.add(cleaned)
        return normalized

    async def _resolve_candidate_skills(
        self,
        candidate_id: uuid.UUID,
        master_profile_data: CandidateMasterProfileContract,
        current_user: CurrentUser,
    ) -> tuple[set[str], uuid.UUID | None]:
        canonical_skills = self._normalize_skills(master_profile_data.skills)
        if canonical_skills:
            return canonical_skills, None

        latest_resume = await self.resume_client.get_latest_parsed_resume(
            candidate_id, current_user
        )
        if latest_resume is None:
            return canonical_skills, None

        structured_data = latest_resume.structured_data
        if structured_data is None:
            return canonical_skills, None

        resume_skills = self._normalize_skills(structured_data.skills)
        return resume_skills, latest_resume.id
