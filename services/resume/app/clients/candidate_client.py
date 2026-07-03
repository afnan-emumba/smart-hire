from __future__ import annotations

import uuid

from app.core.config import Settings
from auth.header_auth import CurrentUser
from http_client.base_client import BaseServiceClient


class CandidateClient(BaseServiceClient):
    def __init__(self, settings: Settings) -> None:
        super().__init__(
            base_url=settings.candidate_service_url,
            timeout=settings.http_client_timeout_seconds,
            service_label="Candidate service",
        )

    async def get_candidate(self, candidate_id: uuid.UUID, current_user: CurrentUser) -> dict | None:
        response = await self._get(
            f"/candidates/{candidate_id}",
            headers=self._headers(current_user),
        )
        if response.status_code == 404:
            return None
        self._raise_for_status(response)
        return response.json()
