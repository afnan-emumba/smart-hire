from __future__ import annotations

import uuid

import httpx

from app.core.config import Settings
from auth.header_auth import CurrentUser
from exceptions.http_exceptions import ServiceUnavailableError

_LATEST_RESUME_LOOKBACK = 20


class ResumeClient:
    def __init__(self, settings: Settings) -> None:
        self._base_url = settings.resume_service_url
        self._timeout = settings.http_client_timeout_seconds

    @staticmethod
    def _headers(current_user: CurrentUser) -> dict[str, str]:
        return {"X-User-ID": current_user.id, "X-User-Role": current_user.role}

    async def get_latest_parsed_resume(
        self,
        candidate_id: uuid.UUID,
        current_user: CurrentUser,
    ) -> dict | None:
        async with httpx.AsyncClient(base_url=self._base_url, timeout=self._timeout) as client:
            try:
                response = await client.get(
                    "/resumes",
                    params={"candidate_id": str(candidate_id), "limit": _LATEST_RESUME_LOOKBACK},
                    headers=self._headers(current_user),
                )
            except httpx.HTTPError as exc:
                raise ServiceUnavailableError("Resume service is unavailable") from exc

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ServiceUnavailableError("Resume service is unavailable") from exc

        for resume in response.json():
            if resume.get("parsing_status") == "parsed":
                return resume
        return None
