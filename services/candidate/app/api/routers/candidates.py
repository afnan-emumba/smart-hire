from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.dependencies import get_candidate_service
from app.schemas.candidate import CandidateCreate, CandidateResponse, CandidateUpdate
from app.services.candidate_service import CandidateService
from auth.header_auth import CurrentUser, get_current_user, require_role
from exceptions.http_exceptions import ForbiddenError


router = APIRouter()


@router.post("", response_model=CandidateResponse, status_code=status.HTTP_201_CREATED)
async def create_candidate(
    candidate_create: CandidateCreate,
    current_user: CurrentUser = Depends(require_role("CANDIDATE")),
    service: CandidateService = Depends(get_candidate_service),
) -> CandidateResponse:
    return await service.create_candidate(candidate_create)


@router.get("/{candidate_id}", response_model=CandidateResponse)
async def get_candidate(
    candidate_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    service: CandidateService = Depends(get_candidate_service),
) -> CandidateResponse:
    if current_user.role == "CANDIDATE" and current_user.id != str(candidate_id):
        raise ForbiddenError("Candidates can only view their own profile")
    return await service.get_candidate(candidate_id)


@router.get("", response_model=list[CandidateResponse])
async def list_candidates(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: CurrentUser = Depends(require_role("RECRUITER")),
    service: CandidateService = Depends(get_candidate_service),
) -> list[CandidateResponse]:
    return await service.list_candidates(limit=limit, offset=offset)


@router.patch("/{candidate_id}", response_model=CandidateResponse)
async def update_candidate(
    candidate_id: uuid.UUID,
    candidate_update: CandidateUpdate,
    current_user: CurrentUser = Depends(require_role("CANDIDATE")),
    service: CandidateService = Depends(get_candidate_service),
) -> CandidateResponse:
    return await service.update_candidate(candidate_id, candidate_update, current_user)


@router.delete("/{candidate_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_candidate(
    candidate_id: uuid.UUID,
    current_user: CurrentUser = Depends(require_role("CANDIDATE")),
    service: CandidateService = Depends(get_candidate_service),
) -> Response:
    await service.delete_candidate(candidate_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
