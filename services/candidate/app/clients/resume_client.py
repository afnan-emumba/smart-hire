from __future__ import annotations

import uuid

from app.core.config import Settings
from auth.header_auth import CurrentUser
from http_client.base_client import BaseServiceClient


class ResumeClient(BaseServiceClient):
    def __init__(self, settings: Settings) -> None:
        super().__init__(
            base_url=settings.resume_service_url,
            timeout=settings.http_client_timeout_seconds,
            service_label="Resume service",
        )

    async def delete_resumes_for_candidate(self, candidate_id: uuid.UUID, current_user: CurrentUser) -> None:
        response = await self._delete(
            "/resumes",
            params={"candidate_id": str(candidate_id)},
            headers=self._headers(current_user),
        )
        self._raise_for_status(response)
