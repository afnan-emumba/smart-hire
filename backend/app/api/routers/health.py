from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.health import collect_dependency_results
from app.db.session import get_db_session


router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/health", status_code=status.HTTP_200_OK)
async def health_check(session: AsyncSession = Depends(get_db_session)) -> dict[str, object]:
    dependency_results = await collect_dependency_results(session)
    is_ok = all(result["status"] ==
                "up" for result in dependency_results.values())
    return {
        "status": "ok" if is_ok else "degraded",
        "dependencies": dependency_results,
    }
