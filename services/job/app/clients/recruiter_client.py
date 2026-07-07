from __future__ import annotations

import uuid

from app.core.config import Settings
from auth.header_auth import CurrentUser
from contracts.service_responses import RecruiterResponseContract
from http_client.base_client import BaseServiceClient


class RecruiterClient(BaseServiceClient):
    def __init__(self, settings: Settings) -> None:
        super().__init__(
            base_url=settings.recruiter_service_url,
            timeout=settings.http_client_timeout_seconds,
            service_label="Recruiter service",
        )

    async def get_recruiter(
        self,
        recruiter_id: uuid.UUID,
        current_user: CurrentUser,
    ) -> RecruiterResponseContract | None:
        response = await self._get(
            f"/recruiters/{recruiter_id}",
            headers=self._headers(current_user),
        )
        if response.status_code == 404:
            return None
        self._raise_for_status(response)
        return RecruiterResponseContract.model_validate(response.json())
