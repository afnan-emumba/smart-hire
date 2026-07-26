from __future__ import annotations

import asyncio

import httpx
from temporalio import activity

from auth.header_auth import CurrentUser
from exceptions.http_exceptions import BadRequestError, ServiceUnavailableError

_MAX_ATTEMPTS = 3
_BASE_RETRY_DELAY_SECONDS = 0.2


class BaseServiceClient:
    """Pooled HTTP client for calling another service. One instance should be
    created per target service and reused for the lifetime of the app so the
    underlying connection pool is actually shared across requests.

    Retries transport errors and 5xx responses with exponential backoff.
    Inside a Temporal activity, retry is skipped (a single attempt) since the
    activity's own RetryPolicy already owns retry/backoff for that call —
    retrying at both layers would only compound delay without adding safety.
    """

    def __init__(self, *, base_url: str, timeout: float, service_label: str) -> None:
        self._client = httpx.AsyncClient(base_url=base_url, timeout=timeout)
        self._service_label = service_label

    async def aclose(self) -> None:
        await self._client.aclose()

    @staticmethod
    def _headers(current_user: CurrentUser) -> dict[str, str]:
        return {"X-User-ID": current_user.id, "X-User-Role": current_user.role}

    async def _request_with_retry(
        self, method: str, path: str, *, headers, params=None
    ) -> httpx.Response:
        max_attempts = 1 if activity.in_activity() else _MAX_ATTEMPTS
        last_error: httpx.HTTPError | None = None
        response: httpx.Response | None = None
        for attempt in range(1, max_attempts + 1):
            try:
                response = await self._client.request(
                    method, path, headers=headers, params=params
                )
            except httpx.HTTPError as exc:
                last_error = exc
                response = None
            else:
                if response.status_code < 500:
                    return response
            if attempt < max_attempts:
                delay = _BASE_RETRY_DELAY_SECONDS * (2 ** (attempt - 1))
                await asyncio.sleep(delay)
        if response is not None:
            return response
        raise ServiceUnavailableError(
            f"{self._service_label} is unavailable"
        ) from last_error

    async def _get(
        self,
        path: str,
        *,
        headers: dict[str, str],
        params: dict[str, object] | None = None,
    ) -> httpx.Response:
        return await self._request_with_retry(
            "GET", path, headers=headers, params=params
        )

    async def _delete(
        self,
        path: str,
        *,
        headers: dict[str, str],
        params: dict[str, object] | None = None,
    ) -> httpx.Response:
        return await self._request_with_retry(
            "DELETE", path, headers=headers, params=params
        )

    def _raise_for_status(self, response: httpx.Response) -> None:
        if response.status_code < 400:
            return
        if response.status_code >= 500:
            raise ServiceUnavailableError(f"{self._service_label} is unavailable")
        raise BadRequestError(
            f"{self._service_label} rejected the request (HTTP {response.status_code})"
        )
