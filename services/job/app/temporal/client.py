from __future__ import annotations

from app.core.config import get_settings
from temporal.client import TemporalClient as SharedTemporalClient
from temporalio.client import Client


class TemporalClient:
    @classmethod
    async def get_client(cls) -> Client:
        settings = get_settings()
        return await SharedTemporalClient.get_client(settings.temporal_address, settings.temporal_namespace)

    @classmethod
    async def close(cls) -> None:
        await SharedTemporalClient.close()
