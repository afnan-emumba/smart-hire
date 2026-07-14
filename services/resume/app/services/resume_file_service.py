from __future__ import annotations

import uuid
from pathlib import Path

from app.core.config import Settings
from exceptions.http_exceptions import BadRequestError, PayloadTooLargeError
from storage.constants import MIME_TYPE_APPLICATION_PDF
from storage.local_file_store import has_pdf_signature, remove_if_exists, write_file

_SUPPORTED_CONTENT_TYPES = {
    MIME_TYPE_APPLICATION_PDF,
}


class ResumeFileService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def validate_resume_upload(
        self, *, file_name: str, content_type: str, file_bytes: bytes
    ) -> tuple[str, str]:
        if len(file_bytes) > self.settings.max_resume_size_bytes:
            raise PayloadTooLargeError("Resume file exceeds the configured size limit")

        if not file_bytes:
            raise BadRequestError("Resume file is empty")

        if content_type not in _SUPPORTED_CONTENT_TYPES:
            raise BadRequestError("Unsupported resume file type")

        if not has_pdf_signature(file_bytes):
            raise BadRequestError("Resume file does not appear to be a valid PDF")

        sanitized_name = Path(file_name).name
        suffix = Path(sanitized_name).suffix.lower()
        if not suffix:
            raise BadRequestError("Resume file must include an extension")

        return sanitized_name, suffix

    async def write_resume_file(
        self,
        *,
        resume_id: uuid.UUID,
        suffix: str,
        file_bytes: bytes,
    ) -> str:
        return await write_file(
            directory=self.settings.resume_upload_dir,
            file_name=f"{resume_id}{suffix}",
            file_bytes=file_bytes,
        )

    async def remove_if_exists(self, storage_path: str | None) -> None:
        await remove_if_exists(storage_path)
