from __future__ import annotations

import uuid

import httpx

from app.core.config import Settings
from auth.header_auth import CurrentUser
from exceptions.http_exceptions import ServiceUnavailableError

_JOB_PAGE_SIZE = 100


class JobClient:
    def __init__(self, settings: Settings) -> None:
        self._base_url = settings.job_service_url
        self._timeout = settings.http_client_timeout_seconds

    @staticmethod
    def _headers(current_user: CurrentUser) -> dict[str, str]:
        return {"X-User-ID": current_user.id, "X-User-Role": current_user.role}

    async def get_job(self, job_id: uuid.UUID, current_user: CurrentUser) -> dict | None:
        async with httpx.AsyncClient(base_url=self._base_url, timeout=self._timeout) as client:
            try:
                response = await client.get(f"/jobs/{job_id}", headers=self._headers(current_user))
            except httpx.HTTPError as exc:
                raise ServiceUnavailableError("Job service is unavailable") from exc

        if response.status_code == 404:
            return None
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ServiceUnavailableError("Job service is unavailable") from exc
        return response.json()

    async def list_by_recruiter(self, recruiter_id: uuid.UUID, current_user: CurrentUser) -> list[dict]:
        jobs: list[dict] = []
        offset = 0
        async with httpx.AsyncClient(base_url=self._base_url, timeout=self._timeout) as client:
            while True:
                try:
                    response = await client.get(
                        "/jobs",
                        params={
                            "recruiter_id": str(recruiter_id),
                            "limit": _JOB_PAGE_SIZE,
                            "offset": offset,
                        },
                        headers=self._headers(current_user),
                    )
                except httpx.HTTPError as exc:
                    raise ServiceUnavailableError("Job service is unavailable") from exc

                try:
                    response.raise_for_status()
                except httpx.HTTPStatusError as exc:
                    raise ServiceUnavailableError("Job service is unavailable") from exc

                page = response.json()
                jobs.extend(page)
                if len(page) < _JOB_PAGE_SIZE:
                    break
                offset += _JOB_PAGE_SIZE

        return jobs
