from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.api.dependencies import get_recruiter_service
from app.core.auth import CurrentUser, require_role
from app.schemas.recruiter import RecruiterCreate, RecruiterResponse
from app.services.recruiter_service import RecruiterService


router = APIRouter()


@router.post("", response_model=RecruiterResponse, status_code=status.HTTP_201_CREATED)
async def create_recruiter(
    recruiter_create: RecruiterCreate,
    current_user: CurrentUser = Depends(require_role("RECRUITER")),
    service: RecruiterService = Depends(get_recruiter_service),
) -> RecruiterResponse:
    return await service.create_recruiter(recruiter_create)