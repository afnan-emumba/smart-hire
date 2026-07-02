from __future__ import annotations

import uuid
from typing import Any

from temporalio import activity

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.repositories.resume_repo import ResumeRepository
from app.services.resume_service import ResumeService


@activity.defn
async def parse_resume(resume_id: str) -> dict[str, Any]:
    parsed_resume_id = uuid.UUID(resume_id)
    activity.logger.info("Parsing uploaded resume", extra={"resume_id": resume_id})

    async with SessionLocal() as session:
        service = ResumeService(resume_repo=ResumeRepository(session), settings=get_settings())
        try:
            result = await service.process_resume_parsing(parsed_resume_id)
            await session.commit()
            return result
        except Exception:
            await session.rollback()
            raise
