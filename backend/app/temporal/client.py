from __future__ import annotations

import asyncio
import inspect

from temporalio.client import Client

from app.core.config import get_settings


class TemporalClient:
    _instance: Client | None = None
    _lock = asyncio.Lock()

    @classmethod
    async def get_client(cls) -> Client:
        if cls._instance is not None:
            return cls._instance

        async with cls._lock:
            if cls._instance is None:
                settings = get_settings()
                cls._instance = await Client.connect(
                    settings.temporal_address,
                    namespace=settings.temporal_namespace,
                )

        return cls._instance

    @classmethod
    async def close(cls) -> None:
        if cls._instance is None:
            return

        async with cls._lock:
            if cls._instance is not None:
                close_method = getattr(cls._instance, "close", None) or getattr(
                    cls._instance,
                    "aclose",
                    None,
                )
                if close_method is not None:
                    result = close_method()
                    if inspect.isawaitable(result):
                        await result
                cls._instance = None
