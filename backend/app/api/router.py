from __future__ import annotations

from fastapi import APIRouter

from app.api.routers.applications import router as applications_router
from app.api.routers.analytics import router as analytics_router
from app.api.routers.candidates import router as candidates_router
from app.api.routers.health import router as health_router
from app.api.routers.jobs import router as jobs_router
from app.api.routers.recruiters import router as recruiters_router


api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(analytics_router, prefix="/analytics", tags=["analytics"])
api_router.include_router(recruiters_router, prefix="/recruiters", tags=["recruiters"])
api_router.include_router(candidates_router, prefix="/candidates", tags=["candidates"])
api_router.include_router(jobs_router, prefix="/jobs", tags=["jobs"])
api_router.include_router(applications_router, prefix="/applications", tags=["applications"])