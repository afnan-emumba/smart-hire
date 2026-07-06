from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from app.clients.candidate_client import CandidateClient
from app.core.config import Settings
from app.repositories.resume_repo import ResumeRepository
from app.schemas.resume import ResumeResponse
from app.services.resume_parsing_service import ResumeParsingService
from app.temporal.client import TemporalClient
from app.utils.resume_pdf import ResumePdfConverter
from auth.actors import require_candidate_user_id
from auth.header_auth import CurrentUser
from exceptions.http_exceptions import (
    BadRequestError,
    ForbiddenError,
    NotFoundError,
    PayloadTooLargeError,
)
from temporal.workflow_launcher import start_workflow_with_retryable_error_mapping


logger = logging.getLogger(__name__)

# Keep in sync with process_resume_parsing, which only implements PDF extraction.
_SUPPORTED_CONTENT_TYPES = {
    "application/pdf",
}


class ResumeService:
    _RESUME_PARSER_VERSION = "resume_pdf.v1"
    _RESUME_SCHEMA_VERSION = "resume_profile.v1"

    def __init__(
        self,
        resume_repo: ResumeRepository,
        settings: Settings,
        candidate_client: CandidateClient,
    ) -> None:
        self.resume_repo = resume_repo
        self.settings = settings
        self.candidate_client = candidate_client

    async def upload_resume(
        self,
        *,
        file_name: str,
        content_type: str,
        file_bytes: bytes,
        current_user: CurrentUser,
    ) -> ResumeResponse:
        candidate_id = require_candidate_user_id(current_user)

        candidate = await self.candidate_client.get_candidate(candidate_id, current_user)
        if candidate is None:
            raise NotFoundError("Candidate not found")

        if len(file_bytes) > self.settings.max_resume_size_bytes:
            raise PayloadTooLargeError("Resume file exceeds the configured size limit")

        if not file_bytes:
            raise BadRequestError("Resume file is empty")

        if content_type not in _SUPPORTED_CONTENT_TYPES:
            raise BadRequestError("Unsupported resume file type")

        upload_dir = Path(self.settings.resume_upload_dir)
        await asyncio.to_thread(upload_dir.mkdir, parents=True, exist_ok=True)

        sanitized_name = Path(file_name).name
        suffix = Path(sanitized_name).suffix.lower()
        if not suffix:
            raise BadRequestError("Resume file must include an extension")

        resume_id = uuid.uuid4()
        stored_file_name = f"{resume_id}{suffix}"
        file_path = upload_dir / stored_file_name

        await asyncio.to_thread(file_path.write_bytes, file_bytes)

        uploaded_at = datetime.now(timezone.utc)
        resume = await self.resume_repo.create(
            resume_id=resume_id,
            candidate_id=candidate_id,
            file_name=sanitized_name,
            content_type=content_type,
            storage_path=file_path.as_posix(),
            uploaded_at=uploaded_at,
            parsing_status="pending",
            parser_version=self._RESUME_PARSER_VERSION,
            schema_version=self._RESUME_SCHEMA_VERSION,
            extraction_metadata={"source": "resume_upload"},
        )

        await self._start_resume_parsing_workflow(resume.id, uploaded_at)

        return ResumeResponse.model_validate(resume)

    async def get_resume(self, resume_id: uuid.UUID, current_user: CurrentUser) -> ResumeResponse:
        resume = await self.resume_repo.get_by_id(resume_id)
        if resume is None:
            raise NotFoundError("Resume not found")

        if current_user.role == "CANDIDATE":
            candidate_id = require_candidate_user_id(current_user)
            if resume.candidate_id != candidate_id:
                raise ForbiddenError("Not authorized to view this resume")

        return ResumeResponse.model_validate(resume)

    async def list_resumes(
        self,
        *,
        candidate_id: uuid.UUID | None,
        current_user: CurrentUser,
        parsing_status: str | None = None,
        limit: int,
        offset: int,
    ) -> list[ResumeResponse]:
        if current_user.role == "CANDIDATE":
            own_candidate_id = require_candidate_user_id(current_user)
            if candidate_id is not None and candidate_id != own_candidate_id:
                raise ForbiddenError("Not authorized to view another candidate's resumes")
            candidate_id = own_candidate_id
        elif candidate_id is None:
            raise BadRequestError("candidate_id is required")

        resumes = await self.resume_repo.list_by_candidate(
            candidate_id,
            parsing_status=parsing_status,
            limit=limit,
            offset=offset,
        )
        return [ResumeResponse.model_validate(resume) for resume in resumes]

    async def process_resume_parsing(self, resume_id: uuid.UUID) -> dict[str, Any]:
        resume = await self.resume_repo.get_by_id(resume_id)
        if resume is None:
            raise NotFoundError("Resume not found")

        if resume.content_type != "application/pdf":
            updated = await self._update_resume_record(
                resume,
                parsing_status="unsupported",
                parsing_error="Resume parsing currently supports PDF uploads only",
                parsed_at=None,
                raw_markdown=None,
                structured_data=None,
            )
            return self._parsing_result(updated)

        if resume.storage_path is None:
            updated = await self._update_resume_record(
                resume,
                parsing_status="failed",
                parsing_error="Resume storage path is missing",
                parsed_at=None,
                raw_markdown=None,
                structured_data=None,
            )
            return self._parsing_result(updated)

        resume_path = Path(resume.storage_path)
        if not resume_path.exists():
            updated = await self._update_resume_record(
                resume,
                parsing_status="failed",
                parsing_error="Uploaded resume file is no longer available",
                parsed_at=None,
                raw_markdown=None,
                structured_data=None,
            )
            return self._parsing_result(updated)

        await self.resume_repo.update_parsing_status(resume, parsing_status="processing")

        try:
            file_bytes = await asyncio.to_thread(resume_path.read_bytes)
            markdown = await asyncio.to_thread(ResumePdfConverter.convert_pdf_to_markdown, file_bytes)
            parsed_resume = await ResumeParsingService.extract_resume_profile(markdown)
        except ValueError as exc:
            updated = await self._update_resume_record(
                resume,
                parsing_status="failed",
                parsing_error=str(exc),
                parsed_at=None,
                raw_markdown=None,
                structured_data=None,
            )
            return self._parsing_result(updated)

        parsed_at = datetime.now(timezone.utc)
        updated = await self._update_resume_record(
            resume,
            parsing_status="parsed",
            parsing_error=None,
            parsed_at=parsed_at,
            raw_markdown=markdown,
            structured_data=parsed_resume,
        )
        return self._parsing_result(updated)

    async def delete_resumes_for_candidate(
        self,
        candidate_id: uuid.UUID,
        current_user: CurrentUser,
    ) -> None:
        owner_id = require_candidate_user_id(current_user)
        if owner_id != candidate_id:
            raise ForbiddenError("Not authorized to delete another candidate's resumes")

        await self.resume_repo.delete_by_candidate(candidate_id)

    async def _update_resume_record(
        self,
        resume: Any,
        *,
        parsing_status: str,
        parsing_error: str | None,
        parsed_at: datetime | None,
        raw_markdown: str | None,
        structured_data: dict[str, Any] | None,
    ) -> Any:
        extraction_metadata = dict(resume.extraction_metadata)
        extraction_metadata["last_processed_at"] = datetime.now(timezone.utc).isoformat()
        extraction_metadata["parser_version"] = self._RESUME_PARSER_VERSION
        extraction_metadata["schema_version"] = self._RESUME_SCHEMA_VERSION
        return await self.resume_repo.update_parsing_result(
            resume,
            parsing_status=parsing_status,
            parsing_error=parsing_error,
            parsed_at=parsed_at,
            raw_markdown=raw_markdown,
            structured_data=structured_data,
            extraction_metadata=extraction_metadata,
        )

    @staticmethod
    def _parsing_result(resume: Any) -> dict[str, Any]:
        return {
            "resume_id": str(resume.id),
            "parsing_status": resume.parsing_status,
        }

    async def _start_resume_parsing_workflow(self, resume_id: uuid.UUID, uploaded_at: datetime) -> None:
        workflow_id = self._build_resume_workflow_id(resume_id, uploaded_at)
        client = await TemporalClient.get_client()
        from app.temporal.workflows import ResumeParsingWorkflow, ResumeParsingWorkflowInput

        await start_workflow_with_retryable_error_mapping(
            client=client,
            workflow=ResumeParsingWorkflow.run,
            workflow_input=ResumeParsingWorkflowInput(resume_id=str(resume_id)),
            workflow_id=workflow_id,
            task_queue=self.settings.temporal_resume_task_queue,
            execution_timeout=timedelta(minutes=5),
            logger=logger,
            context={"resume_id": str(resume_id), "workflow_id": workflow_id},
            conflict_log_message="Resume parsing workflow already started",
            failure_log_message="Failed to start resume parsing workflow",
            unavailable_message="Temporal workflow service is unavailable",
        )

    @staticmethod
    def _build_resume_workflow_id(resume_id: uuid.UUID, uploaded_at: datetime) -> str:
        return f"resume-parsing-{resume_id}-{int(uploaded_at.timestamp())}"

