from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CandidateResume


class ResumeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        resume_id: uuid.UUID,
        candidate_id: uuid.UUID,
        file_name: str,
        content_type: str,
        storage_path: str,
        uploaded_at: datetime,
        parsing_status: str,
        parser_version: str | None,
        schema_version: str,
        extraction_metadata: dict[str, Any],
    ) -> CandidateResume:
        resume = CandidateResume(
            id=resume_id,
            candidate_id=candidate_id,
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

    async def list_by_candidate(
        self,
        candidate_id: uuid.UUID,
        *,
        parsing_status: str | None = None,
        limit: int,
        offset: int,
    ) -> list[CandidateResume]:
        stmt = select(CandidateResume).where(CandidateResume.candidate_id == candidate_id)
        if parsing_status is not None:
            stmt = stmt.where(CandidateResume.parsing_status == parsing_status)
        result = await self.session.execute(
            stmt.order_by(CandidateResume.uploaded_at.desc(), CandidateResume.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def delete_by_candidate(self, candidate_id: uuid.UUID) -> list[str]:
        result = await self.session.execute(
            delete(CandidateResume)
            .where(CandidateResume.candidate_id == candidate_id)
            .returning(CandidateResume.storage_path)
        )
        await self.session.flush()
        return [storage_path for storage_path in result.scalars().all() if storage_path]

    async def update_parsing_status(
        self,
        resume: CandidateResume,
        *,
        parsing_status: str,
    ) -> CandidateResume:
        resume.parsing_status = parsing_status
        await self.session.flush()
        await self.session.refresh(resume)
        return resume

    async def update_parsing_result(
        self,
        resume: CandidateResume,
        *,
        parsing_status: str,
        parsing_error: str | None,
        parsed_at: datetime | None,
        raw_markdown: str | None,
        structured_data: dict[str, Any] | None,
        extraction_metadata: dict[str, Any],
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
