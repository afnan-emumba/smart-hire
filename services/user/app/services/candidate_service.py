from __future__ import annotations

import logging
import uuid

from sqlalchemy.exc import IntegrityError

from app.clients.resume_client import ResumeClient
from app.repositories.candidate_repo import CandidateRepository
from app.schemas.candidate import (
    CandidateCreate,
    CandidateResponse,
    CandidateUpdate,
    MasterProfileData,
)
from app.services.user_lifecycle import UserLifecycleCoordinator
from auth.actors import require_candidate_user_id
from auth.header_auth import CurrentUser
from contracts.enums import UserRole
from contracts.service_responses import ResumeStructuredDataContract
from db.base import is_unique_violation
from exceptions.http_exceptions import ConflictError, ForbiddenError, NotFoundError

logger = logging.getLogger(__name__)

_SUMMARY_MAX_LENGTH = 2000
_SKILL_MAX_LENGTH = 100
_PHONE_MAX_LENGTH = 32
_LOCATION_MAX_LENGTH = 255
_PROFILE_LINK_FIELDS = ("linkedin", "github", "portfolio", "website")


class CandidateService:
    def __init__(
        self,
        candidate_repo: CandidateRepository,
        lifecycle: UserLifecycleCoordinator,
        resume_client: ResumeClient,
    ) -> None:
        self.candidate_repo = candidate_repo
        self.lifecycle = lifecycle
        self.resume_client = resume_client

    async def create_candidate(
        self, candidate_create: CandidateCreate, current_user: CurrentUser
    ) -> CandidateResponse:
        candidate_id = require_candidate_user_id(current_user)

        existing_candidate = await self.candidate_repo.get_by_email(
            candidate_create.email
        )
        if existing_candidate is not None:
            raise ConflictError("Candidate with this email already exists")

        try:
            candidate = await self.candidate_repo.create(candidate_create, candidate_id)
        except IntegrityError as exc:
            if is_unique_violation(exc):
                logger.info(
                    "Candidate creation conflicted with a concurrent request",
                    extra={"email": candidate_create.email},
                )
                raise ConflictError("Candidate with this email already exists") from exc
            logger.exception(
                "Failed to create candidate",
                extra={"email": candidate_create.email},
            )
            raise

        return CandidateResponse.model_validate(candidate)

    async def get_candidate(
        self,
        candidate_id: uuid.UUID,
        current_user: CurrentUser,
    ) -> CandidateResponse:
        if current_user.role == UserRole.CANDIDATE and current_user.id != str(
            candidate_id
        ):
            raise ForbiddenError("Candidates can only view their own profile")

        candidate = await self.candidate_repo.get_by_id(candidate_id)
        if candidate is None:
            raise NotFoundError("Candidate not found")

        return CandidateResponse.model_validate(candidate)

    async def list_candidates(
        self, *, limit: int, offset: int
    ) -> list[CandidateResponse]:
        candidates = await self.candidate_repo.list_all(limit=limit, offset=offset)
        return [CandidateResponse.model_validate(candidate) for candidate in candidates]

    async def update_candidate(
        self,
        candidate_id: uuid.UUID,
        candidate_update: CandidateUpdate,
        current_user: CurrentUser,
    ) -> CandidateResponse:
        owner_id = require_candidate_user_id(current_user)
        if owner_id != candidate_id:
            raise ForbiddenError("Not authorized to update this candidate")

        candidate = await self.candidate_repo.get_by_id(candidate_id)
        if candidate is None:
            raise NotFoundError("Candidate not found")

        if candidate_update.email is not None:
            existing_candidate = await self.candidate_repo.get_by_email(
                candidate_update.email
            )
            if existing_candidate is not None and existing_candidate.id != candidate_id:
                raise ConflictError("Candidate with this email already exists")

        try:
            updated_candidate = await self.candidate_repo.update(
                candidate_id,
                candidate_update.model_dump(mode="json", exclude_unset=True),
            )
        except IntegrityError as exc:
            if is_unique_violation(exc):
                logger.info(
                    "Candidate update conflicted with a concurrent request",
                    extra={
                        "candidate_id": str(candidate_id),
                        "email": candidate_update.email,
                    },
                )
                raise ConflictError("Candidate with this email already exists") from exc
            logger.exception(
                "Failed to update candidate",
                extra={"candidate_id": str(candidate_id)},
            )
            raise

        if updated_candidate is None:
            raise NotFoundError("Candidate not found")

        return CandidateResponse.model_validate(updated_candidate)

    async def sync_profile_from_resume(
        self,
        candidate_id: uuid.UUID,
        current_user: CurrentUser,
    ) -> CandidateResponse:
        owner_id = require_candidate_user_id(current_user)
        if owner_id != candidate_id:
            raise ForbiddenError("Not authorized to update this candidate")

        candidate = await self.candidate_repo.get_by_id(candidate_id)
        if candidate is None:
            raise NotFoundError("Candidate not found")

        latest_resume = await self.resume_client.get_latest_parsed_resume(
            candidate_id, current_user
        )
        if latest_resume is None or latest_resume.structured_data is None:
            raise NotFoundError("No parsed resume available to sync from")

        existing_profile = MasterProfileData.model_validate(
            candidate.master_profile_data
        )
        merged_profile = self._fill_empty_profile_fields(
            existing_profile, latest_resume.structured_data
        )

        updated_candidate = await self.candidate_repo.update(
            candidate_id,
            {"master_profile_data": merged_profile.model_dump(mode="json")},
        )
        if updated_candidate is None:
            raise NotFoundError("Candidate not found")

        return CandidateResponse.model_validate(updated_candidate)

    def _fill_empty_profile_fields(
        self,
        existing: MasterProfileData,
        resume_data: ResumeStructuredDataContract,
    ) -> MasterProfileData:
        merged = existing.model_copy(deep=True)

        if merged.summary is None:
            cleaned_summary = self._clean_bounded_text(
                resume_data.summary, max_length=_SUMMARY_MAX_LENGTH
            )
            if cleaned_summary is not None:
                merged.summary = cleaned_summary

        if not merged.skills and resume_data.skills:
            merged.skills = self._clean_skills(resume_data.skills)

        if merged.contact.phone is None:
            cleaned_phone = self._clean_bounded_text(
                resume_data.contact.phone, max_length=_PHONE_MAX_LENGTH
            )
            if cleaned_phone is not None:
                merged.contact.phone = cleaned_phone

        if merged.contact.location is None:
            cleaned_location = self._clean_bounded_text(
                resume_data.contact.location, max_length=_LOCATION_MAX_LENGTH
            )
            if cleaned_location is not None:
                merged.contact.location = cleaned_location

        for field_name in _PROFILE_LINK_FIELDS:
            if getattr(merged.links, field_name) is None:
                resume_value = getattr(resume_data.links, field_name)
                if resume_value is not None:
                    setattr(merged.links, field_name, resume_value)

        return merged

    @staticmethod
    def _clean_skills(skills: list[str]) -> list[str]:
        seen: set[str] = set()
        cleaned_skills: list[str] = []
        for skill in skills:
            cleaned = CandidateService._clean_bounded_text(
                skill, max_length=_SKILL_MAX_LENGTH
            )
            if cleaned is None:
                continue
            dedupe_key = cleaned.lower()
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            cleaned_skills.append(cleaned)
        return cleaned_skills

    @staticmethod
    def _clean_bounded_text(value: str | None, *, max_length: int) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned or len(cleaned) > max_length:
            return None
        return cleaned

    async def delete_candidate(
        self, candidate_id: uuid.UUID, current_user: CurrentUser
    ) -> None:
        owner_id = require_candidate_user_id(current_user)
        if owner_id != candidate_id:
            raise ForbiddenError("Not authorized to delete this candidate")

        candidate = await self.candidate_repo.get_by_id(candidate_id)
        if candidate is None:
            raise NotFoundError("Candidate not found")

        await self.lifecycle.on_candidate_deleted(candidate_id, current_user)

        was_deleted = await self.candidate_repo.delete(candidate_id)
        if not was_deleted:
            raise NotFoundError("Candidate not found")
