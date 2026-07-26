from __future__ import annotations

from temporalio.client import Client

from app.core.config import get_settings
from temporal.client import TemporalClient as SharedTemporalClient


class TemporalClient:
    """Client-only Temporal access.

    Application-service hosts no workers: it starts notification delivery by
    name on notification-service's task queue.
    """

    @classmethod
    async def get_client(cls) -> Client:
        settings = get_settings()
        return await SharedTemporalClient.get_client(
            settings.temporal_address, settings.temporal_namespace
        )

    @classmethod
    async def close(cls) -> None:
        await SharedTemporalClient.close()
