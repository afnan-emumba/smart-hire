from __future__ import annotations

import httpx

from auth.header_auth import CurrentUser
from exceptions.http_exceptions import ServiceUnavailableError


class BaseServiceClient:
    """Pooled HTTP client for calling another service. One instance should be
    created per target service and reused for the lifetime of the app so the
    underlying connection pool is actually shared across requests."""

    def __init__(self, *, base_url: str, timeout: float, service_label: str) -> None:
        self._client = httpx.AsyncClient(base_url=base_url, timeout=timeout)
        self._service_label = service_label

    async def aclose(self) -> None:
        await self._client.aclose()

    @staticmethod
    def _headers(current_user: CurrentUser) -> dict[str, str]:
        return {"X-User-ID": current_user.id, "X-User-Role": current_user.role}

    async def _get(
        self,
        path: str,
        *,
        headers: dict[str, str],
        params: dict[str, object] | None = None,
    ) -> httpx.Response:
        try:
            return await self._client.get(path, headers=headers, params=params)
        except httpx.HTTPError as exc:
            raise ServiceUnavailableError(f"{self._service_label} is unavailable") from exc

    async def _delete(
        self,
        path: str,
        *,
        headers: dict[str, str],
        params: dict[str, object] | None = None,
    ) -> httpx.Response:
        try:
            return await self._client.delete(path, headers=headers, params=params)
        except httpx.HTTPError as exc:
            raise ServiceUnavailableError(f"{self._service_label} is unavailable") from exc

    def _raise_for_status(self, response: httpx.Response) -> None:
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ServiceUnavailableError(f"{self._service_label} is unavailable") from exc
