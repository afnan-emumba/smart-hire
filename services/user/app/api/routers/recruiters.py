from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status

from api.pagination import PaginationParams
from app.api.dependencies import get_recruiter_service
from app.schemas.recruiter import RecruiterCreate, RecruiterResponse
from app.services.recruiter_service import RecruiterService
from auth.header_auth import CurrentUser, require_role
from contracts.enums import UserRole

router = APIRouter()


@router.post("", response_model=RecruiterResponse, status_code=status.HTTP_201_CREATED)
async def create_recruiter(
    recruiter_create: RecruiterCreate,
    current_user: CurrentUser = Depends(require_role(UserRole.RECRUITER)),
    service: RecruiterService = Depends(get_recruiter_service),
) -> RecruiterResponse:
    return await service.create_recruiter(recruiter_create, current_user)


@router.get("/{recruiter_id}", response_model=RecruiterResponse)
async def get_recruiter(
    recruiter_id: uuid.UUID,
    current_user: CurrentUser = Depends(require_role(UserRole.RECRUITER)),
    service: RecruiterService = Depends(get_recruiter_service),
) -> RecruiterResponse:
    return await service.get_recruiter(recruiter_id)


@router.get("", response_model=list[RecruiterResponse])
async def list_recruiters(
    pagination: PaginationParams = Depends(PaginationParams),
    current_user: CurrentUser = Depends(require_role(UserRole.RECRUITER)),
    service: RecruiterService = Depends(get_recruiter_service),
) -> list[RecruiterResponse]:
    return await service.list_recruiters(
        limit=pagination.limit, offset=pagination.offset
    )
