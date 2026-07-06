from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.constants import STRUCTURED_JOB_METADATA_FIELDS
from app.core.enums import JobStatus
from app.repositories.job_repo import JobRepository
from app.schemas.job import JobBreakdownFields
from app.services.job_breakdown_service import JobBreakdownService
from app.utils.job_description_pdf import JobDescriptionPdfConverter


logger = logging.getLogger(__name__)


class JobBreakdownOrchestrator:
    def __init__(self, job_repo: JobRepository) -> None:
        self.job_repo = job_repo

    async def finalize_for_publish(self, job: Any) -> Any:
        if job.jd_source_type == "pdf_upload":
            return await self._finalize_pdf_breakdown(job)

        if job.description_breakdown is not None:
            return job

        if not job.description:
            return job

        extracted_profile = await JobBreakdownService.extract_job_profile(
            title=job.title,
            description=job.description,
        )
        breakdown = extracted_profile["breakdown"]
        return await self.job_repo.set_job_description_parsing_result(
            job,
            description=job.description,
            description_breakdown=breakdown.model_dump(mode="json"),
            required_skills=self.merge_required_skills(
                job.required_skills,
                [skill.name for skill in breakdown.skills],
            ),
            parsing_status="parsed",
            parsing_error=None,
            structured_updates=self.build_structured_updates(extracted_profile),
        )

    async def build_breakdown_fields(
        self,
        *,
        title: str,
        description: str | None,
        required_skills: list[str],
        overrides: dict[str, Any] | None = None,
    ) -> JobBreakdownFields:
        override_values = dict(overrides or {})
        normalized_required_skills = self.merge_required_skills(required_skills, [])
        if not description:
            return self._empty_breakdown_fields(
                override_values=override_values,
                normalized_required_skills=normalized_required_skills,
                jd_parsing_status="pending",
                jd_parsing_error=None,
            )

        try:
            extracted_profile = await JobBreakdownService.extract_job_profile(
                title=title,
                description=description,
            )
            breakdown = extracted_profile["breakdown"]
        except Exception as exc:
            return self._empty_breakdown_fields(
                override_values=override_values,
                normalized_required_skills=normalized_required_skills,
                jd_parsing_status="failed",
                jd_parsing_error=str(exc),
            )

        extracted_skills = [skill.name for skill in breakdown.skills]
        return JobBreakdownFields.model_validate(
            {
                **self.build_structured_updates(extracted_profile),
                **override_values,
                "description_breakdown": breakdown.model_dump(mode="json"),
                "required_skills": self.merge_required_skills(required_skills, extracted_skills),
                "jd_parsing_status": "parsed",
                "jd_parsing_error": None,
                "status": JobStatus.DRAFT.value,
            }
        )

    def _empty_breakdown_fields(
        self,
        *,
        override_values: dict[str, Any],
        normalized_required_skills: list[str],
        jd_parsing_status: str,
        jd_parsing_error: str | None,
    ) -> JobBreakdownFields:
        return JobBreakdownFields.model_validate(
            {
                **self.empty_structured_updates(),
                **override_values,
                "description_breakdown": None,
                "required_skills": normalized_required_skills,
                "jd_parsing_status": jd_parsing_status,
                "jd_parsing_error": jd_parsing_error,
                "status": JobStatus.DRAFT.value,
            }
        )

    @staticmethod
    def is_breakdown_complete(description_breakdown: dict[str, Any]) -> bool:
        skills = description_breakdown.get("skills") or []
        technologies = description_breakdown.get("technologies") or []
        responsibilities = description_breakdown.get("responsibilities") or []
        requirements = description_breakdown.get("requirements") or {}
        must_haves = requirements.get("must_haves") or []
        nice_to_haves = requirements.get("nice_to_haves") or []
        overview = description_breakdown.get("overview")
        return bool(skills or technologies or responsibilities or must_haves or nice_to_haves or overview)

    @staticmethod
    def merge_required_skills(base_skills: list[str], extracted_skills: list[str]) -> list[str]:
        normalized_skills = [
            skill.strip() for skill in [*base_skills, *extracted_skills] if skill.strip()
        ]
        return JobBreakdownService._deduplicate(normalized_skills)

    @staticmethod
    def empty_structured_updates() -> dict[str, Any]:
        return {field_name: None for field_name in STRUCTURED_JOB_METADATA_FIELDS}

    @classmethod
    def build_structured_updates(cls, extracted_profile: dict[str, Any]) -> dict[str, Any]:
        return {
            "employment_type": extracted_profile.get("employment_type"),
            "seniority_level": extracted_profile.get("seniority_level"),
            "department": extracted_profile.get("department"),
            "job_category": extracted_profile.get("job_category"),
            "location": cls._dump_model(extracted_profile.get("location")),
            "compensation": cls._dump_model(extracted_profile.get("compensation")),
            "years_of_experience_required": extracted_profile.get("years_of_experience_required"),
            "application_deadline": extracted_profile.get("application_deadline"),
        }

    @staticmethod
    def _dump_model(value: Any) -> Any:
        if value is None:
            return None
        if hasattr(value, "model_dump"):
            return value.model_dump(mode="json")
        return value

    async def _finalize_pdf_breakdown(self, job: Any) -> Any:
        try:
            file_bytes = await asyncio.to_thread(Path(job.jd_storage_path).read_bytes)
            description = await asyncio.to_thread(
                JobDescriptionPdfConverter.convert_pdf_to_markdown,
                file_bytes,
            )
            extracted_profile = await JobBreakdownService.extract_job_profile(
                title=job.title,
                description=description,
            )
            breakdown = extracted_profile["breakdown"]
        except Exception as exc:
            logger.exception(
                "Failed to finalize job description breakdown",
                extra={"job_id": str(job.id)},
            )
            failed_job = await self.job_repo.set_job_description_parsing_result(
                job,
                description=None,
                description_breakdown=None,
                required_skills=job.required_skills,
                parsing_status="failed",
                parsing_error=str(exc),
                structured_updates=self.empty_structured_updates(),
            )
            await self.job_repo.update(
                job.id,
                {
                    "publishing_failed_at": datetime.now(timezone.utc),
                    "publishing_error": str(exc),
                },
            )
            return failed_job

        return await self.job_repo.set_job_description_parsing_result(
            job,
            description=description,
            description_breakdown=breakdown.model_dump(mode="json"),
            required_skills=self.merge_required_skills(
                job.required_skills,
                [skill.name for skill in breakdown.skills],
            ),
            parsing_status="parsed",
            parsing_error=None,
            structured_updates=self.build_structured_updates(extracted_profile),
        )
