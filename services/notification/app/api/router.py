from __future__ import annotations

from fastapi import APIRouter

from app.api.routers.health import router as health_router
from app.api.routers.notifications import router as notifications_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(
    notifications_router, prefix="/notifications", tags=["notifications"]
)
