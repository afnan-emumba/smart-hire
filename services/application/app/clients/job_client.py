from __future__ import annotations

import uuid

from app.core.config import Settings
from auth.header_auth import CurrentUser
from http_client.base_client import BaseServiceClient


_JOB_PAGE_SIZE = 100


class JobClient(BaseServiceClient):
    def __init__(self, settings: Settings) -> None:
        super().__init__(
            base_url=settings.job_service_url,
            timeout=settings.http_client_timeout_seconds,
            service_label="Job service",
        )

    async def get_job(self, job_id: uuid.UUID, current_user: CurrentUser) -> dict | None:
        response = await self._get(f"/jobs/{job_id}", headers=self._headers(current_user))
        if response.status_code == 404:
            return None
        self._raise_for_status(response)
        return response.json()

    async def list_by_recruiter(self, recruiter_id: uuid.UUID, current_user: CurrentUser) -> list[dict]:
        jobs: list[dict] = []
        offset = 0
        while True:
            response = await self._get(
                "/jobs",
                params={
                    "recruiter_id": str(recruiter_id),
                    "limit": _JOB_PAGE_SIZE,
                    "offset": offset,
                },
                headers=self._headers(current_user),
            )
            self._raise_for_status(response)

            page = response.json()
            jobs.extend(page)
            if len(page) < _JOB_PAGE_SIZE:
                break
            offset += _JOB_PAGE_SIZE

        return jobs
