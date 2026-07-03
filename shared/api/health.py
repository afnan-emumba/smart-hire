from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession


def make_health_router(
    get_db_session: Callable[..., AsyncSession],
    ping_database: Callable[[AsyncSession], Awaitable[bool]],
) -> APIRouter:
    router = APIRouter()
    logger = logging.getLogger(__name__)

    @router.get("/health", status_code=status.HTTP_200_OK)
    async def health_check(session: AsyncSession = Depends(get_db_session)) -> dict[str, str]:
        try:
            database_ok = await ping_database(session)
        except Exception:
            logger.exception("Database health check failed")
            database_ok = False

        return {
            "status": "ok" if database_ok else "degraded",
            "database": "up" if database_ok else "down",
        }

    return router
