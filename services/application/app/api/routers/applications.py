from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.dependencies import get_application_service
from app.core.application_states import ApplicationStatus
from app.schemas.application import ApplicationCreate, ApplicationResponse, ApplicationStatusUpdate
from app.services.application_service import ApplicationService
from auth.header_auth import CurrentUser, get_current_user, require_role


router = APIRouter()


@router.post("", response_model=ApplicationResponse, status_code=status.HTTP_201_CREATED)
async def create_application(
    application_create: ApplicationCreate,
    current_user: CurrentUser = Depends(require_role("CANDIDATE")),
    service: ApplicationService = Depends(get_application_service),
) -> ApplicationResponse:
    return await service.apply_to_job(application_create, current_user)


@router.get("/{application_id}", response_model=ApplicationResponse)
async def get_application(
    application_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    service: ApplicationService = Depends(get_application_service),
) -> ApplicationResponse:
    return await service.get_application(application_id, current_user)


@router.get("", response_model=list[ApplicationResponse])
async def list_applications(
    status_filter: ApplicationStatus | None = Query(default=None, alias="status"),
    candidate_id: uuid.UUID | None = None,
    job_id: uuid.UUID | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: CurrentUser = Depends(get_current_user),
    service: ApplicationService = Depends(get_application_service),
) -> list[ApplicationResponse]:
    return await service.list_applications(
        status=status_filter,
        candidate_id=candidate_id,
        job_id=job_id,
        current_user=current_user,
        limit=limit,
        offset=offset,
    )


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_applications(
    job_id: uuid.UUID | None = None,
    candidate_id: uuid.UUID | None = None,
    current_user: CurrentUser = Depends(get_current_user),
    service: ApplicationService = Depends(get_application_service),
) -> Response:
    await service.delete_applications(job_id=job_id, candidate_id=candidate_id, current_user=current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/{application_id}/status", response_model=ApplicationResponse)
async def update_application_status(
    application_id: uuid.UUID,
    status_update: ApplicationStatusUpdate,
    current_user: CurrentUser = Depends(require_role("RECRUITER")),
    service: ApplicationService = Depends(get_application_service),
) -> ApplicationResponse:
    return await service.update_application_status(
        application_id,
        status_update.status,
        current_user,
    )
