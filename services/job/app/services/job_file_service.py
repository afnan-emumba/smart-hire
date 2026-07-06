from __future__ import annotations

import uuid
from pathlib import Path

from app.core.config import Settings
from exceptions.http_exceptions import BadRequestError, PayloadTooLargeError
from storage.local_file_store import remove_if_exists, write_file


class JobFileService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def validate_pdf_upload(self, *, file_name: str, content_type: str, file_bytes: bytes) -> str:
        if len(file_bytes) > self.settings.max_jd_size_bytes:
            raise PayloadTooLargeError("Job description file exceeds the configured size limit")

        if not file_bytes:
            raise BadRequestError("Job description file is empty")

        if content_type != "application/pdf":
            raise BadRequestError("Job description files must be uploaded as PDFs")

        sanitized_name = Path(file_name).name
        suffix = Path(sanitized_name).suffix.lower()
        if suffix != ".pdf":
            raise BadRequestError("Job description file must use a .pdf extension")

        return sanitized_name

    async def write_job_pdf(
        self,
        *,
        job_id: uuid.UUID,
        file_bytes: bytes,
    ) -> str:
        return await write_file(
            directory=self.settings.jd_upload_dir,
            file_name=f"{job_id}.pdf",
            file_bytes=file_bytes,
        )

    async def remove_if_exists(self, storage_path: str | None) -> None:
        await remove_if_exists(storage_path)
