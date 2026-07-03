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

    async def get_latest_parsed_resume(
        self,
        candidate_id: uuid.UUID,
        current_user: CurrentUser,
    ) -> dict | None:
        response = await self._get(
            "/resumes",
            params={
                "candidate_id": str(candidate_id),
                "parsing_status": "parsed",
                "limit": 1,
            },
            headers=self._headers(current_user),
        )
        if response.status_code == 404:
            return None
        self._raise_for_status(response)

        resumes = response.json()
        return resumes[0] if resumes else None
