from __future__ import annotations

import uuid

from app.core.config import Settings
from auth.header_auth import CurrentUser
from http_client.base_client import BaseServiceClient
from http_client.constants import QUERY_PARAM_JOB_ID


class ApplicationClient(BaseServiceClient):
    def __init__(self, settings: Settings) -> None:
        super().__init__(
            base_url=settings.application_service_url,
            timeout=settings.http_client_timeout_seconds,
            service_label="Application service",
        )

    async def delete_applications_for_job(self, job_id: uuid.UUID, current_user: CurrentUser) -> None:
        response = await self._delete(
            "/applications",
            params={QUERY_PARAM_JOB_ID: str(job_id)},
            headers=self._headers(current_user),
        )
        self._raise_for_status(response)
