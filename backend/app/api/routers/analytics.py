from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.dependencies import get_analytics_service
from app.core.auth import require_role
from app.schemas.analytics import AnalyticsSummaryResponse
from app.services.analytics_service import AnalyticsService


router = APIRouter()


@router.get("/summary", response_model=AnalyticsSummaryResponse)
async def get_analytics_summary(
    _: object = Depends(require_role("RECRUITER")),
    service: AnalyticsService = Depends(get_analytics_service),
) -> AnalyticsSummaryResponse:
    return await service.get_summary()
