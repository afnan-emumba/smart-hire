from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, UploadFile, status

from app.api.dependencies import get_application_service
from app.core.auth import CurrentUser, get_current_user, require_role
from app.schemas.application import ApplicationCreate, ApplicationResponse
from app.services.application_service import ApplicationService


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
    return await service.get_application(application_id)


@router.get("", response_model=list[ApplicationResponse])
async def list_applications(
    candidate_id: uuid.UUID | None = None,
    job_id: uuid.UUID | None = None,
    current_user: CurrentUser = Depends(get_current_user),
    service: ApplicationService = Depends(get_application_service),
) -> list[ApplicationResponse]:
    return await service.list_applications(candidate_id=candidate_id, job_id=job_id)


@router.post("/{application_id}/resume", response_model=ApplicationResponse)
async def upload_application_resume(
    application_id: uuid.UUID,
    resume: UploadFile = File(...),
    current_user: CurrentUser = Depends(require_role("CANDIDATE")),
    service: ApplicationService = Depends(get_application_service),
) -> ApplicationResponse:
    file_bytes = await resume.read()
    return await service.upload_resume(
        application_id,
        file_name=resume.filename or "resume",
        content_type=resume.content_type or "application/octet-stream",
        file_bytes=file_bytes,
        current_user=current_user,
    )