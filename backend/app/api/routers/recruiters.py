from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status

from app.api.dependencies import get_recruiter_service
from app.core.auth import CurrentUser, get_current_user, require_role
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


@router.get("/{recruiter_id}", response_model=RecruiterResponse)
async def get_recruiter(
    recruiter_id: uuid.UUID,
    current_user: CurrentUser = Depends(require_role("RECRUITER")),
    service: RecruiterService = Depends(get_recruiter_service),
) -> RecruiterResponse:
    return await service.get_recruiter(recruiter_id)


@router.get("", response_model=list[RecruiterResponse])
async def list_recruiters(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: CurrentUser = Depends(require_role("RECRUITER")),
    service: RecruiterService = Depends(get_recruiter_service),
) -> list[RecruiterResponse]:
    return await service.list_recruiters(limit=limit, offset=offset)