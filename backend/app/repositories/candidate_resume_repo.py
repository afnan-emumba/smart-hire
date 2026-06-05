from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CandidateResume


class CandidateResumeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        resume_id: uuid.UUID,
        candidate_id: uuid.UUID,
        source_application_id: uuid.UUID | None,
        file_name: str,
        content_type: str,
        storage_path: str,
        uploaded_at: datetime,
        parsing_status: str,
        parser_version: str | None,
        schema_version: str,
        extraction_metadata: dict,
    ) -> CandidateResume:
        resume = CandidateResume(
            id=resume_id,
            candidate_id=candidate_id,
            source_application_id=source_application_id,
            file_name=file_name,
            content_type=content_type,
            storage_path=storage_path,
            uploaded_at=uploaded_at,
            parsing_status=parsing_status,
            parser_version=parser_version,
            schema_version=schema_version,
            extraction_metadata=extraction_metadata,
        )
        self.session.add(resume)
        await self.session.flush()
        await self.session.refresh(resume)
        return resume

    async def get_by_id(self, resume_id: uuid.UUID) -> CandidateResume | None:
        result = await self.session.execute(
            select(CandidateResume).where(CandidateResume.id == resume_id)
        )
        return result.scalar_one_or_none()

    async def get_latest_parsed_for_candidate(self, candidate_id: uuid.UUID) -> CandidateResume | None:
        result = await self.session.execute(
            select(CandidateResume)
            .where(
                CandidateResume.candidate_id == candidate_id,
                CandidateResume.parsing_status == "parsed",
            )
            .order_by(CandidateResume.uploaded_at.desc(), CandidateResume.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def update_parsing_result(
        self,
        resume: CandidateResume,
        *,
        parsing_status: str,
        parsing_error: str | None,
        parsed_at: datetime | None,
        raw_markdown: str | None,
        structured_data: dict | None,
        extraction_metadata: dict,
    ) -> CandidateResume:
        resume.parsing_status = parsing_status
        resume.parsing_error = parsing_error
        resume.parsed_at = parsed_at
        resume.raw_markdown = raw_markdown
        resume.structured_data = structured_data
        resume.extraction_metadata = extraction_metadata
        await self.session.flush()
        await self.session.refresh(resume)
        return resume