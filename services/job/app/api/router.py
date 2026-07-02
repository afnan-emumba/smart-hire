from __future__ import annotations

from fastapi import APIRouter

from app.api.routers.health import router as health_router
from app.api.routers.jobs import router as jobs_router


api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(jobs_router, prefix="/jobs", tags=["jobs"])
