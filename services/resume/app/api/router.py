from __future__ import annotations

from fastapi import APIRouter

from app.api.routers.health import router as health_router
from app.api.routers.resumes import router as resumes_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(resumes_router, prefix="/resumes", tags=["resumes"])
