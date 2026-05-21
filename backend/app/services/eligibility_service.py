from __future__ import annotations

import uuid

from app.core.enums import JobStatus
from app.repositories.application_repo import ApplicationRepository
from app.repositories.candidate_repo import CandidateRepository
from app.repositories.job_repo import JobRepository
from app.schemas.application import EligibilityResult
from app.services.exceptions import NotFoundError


class EligibilityService:
    def __init__(
        self,
        job_repo: JobRepository,
        candidate_repo: CandidateRepository,
        application_repo: ApplicationRepository,
    ) -> None:
        self.job_repo = job_repo
        self.candidate_repo = candidate_repo
        self.application_repo = application_repo

    async def check_eligibility(
        self,
        candidate_id: uuid.UUID,
        job_id: uuid.UUID,
    ) -> EligibilityResult:
        job = await self.job_repo.get_by_id(job_id)
        if job is None:
            raise NotFoundError("Job not found")

        candidate = await self.candidate_repo.get_by_id(candidate_id)
        if candidate is None:
            raise NotFoundError("Candidate not found")

        if job.status != JobStatus.READY.value:
            return EligibilityResult(
                is_eligible=False,
                reason="Job is not yet published",
                match_score=0.0,
            )

        existing_application = await self.application_repo.get_by_job_and_candidate(
            job_id,
            candidate_id,
        )
        if existing_application is not None:
            return EligibilityResult(
                is_eligible=False,
                reason="You have already applied to this job",
                match_score=0.0,
            )

        candidate_skills = self._normalize_skills(candidate.master_profile_data.get("skills", []))
        required_skills = self._normalize_skills(job.required_skills or [])

        if not required_skills:
            return EligibilityResult(
                is_eligible=True,
                reason="Job has no required skills configured",
                match_score=1.0,
            )

        matched_skills = candidate_skills & required_skills
        match_score = len(matched_skills) / len(required_skills)
        missing_skills = sorted(required_skills - candidate_skills)

        if match_score < 0.5:
            return EligibilityResult(
                is_eligible=False,
                reason="You don't have enough required skills",
                missing_skills=missing_skills,
                match_score=match_score,
            )

        return EligibilityResult(
            is_eligible=True,
            reason="You meet the job requirements",
            missing_skills=missing_skills,
            match_score=match_score,
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