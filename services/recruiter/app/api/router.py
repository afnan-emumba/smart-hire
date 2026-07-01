from __future__ import annotations

from fastapi import APIRouter

from app.api.routers.health import router as health_router
from app.api.routers.recruiters import router as recruiters_router


api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(recruiters_router, prefix="/recruiters", tags=["recruiters"])
