from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status

from app.api.dependencies import get_application_service
from app.core.auth import CurrentUser, get_current_user, require_role
from app.core.config import get_settings
from app.schemas.application import ApplicationCreate, ApplicationResponse
from app.services.application_service import ApplicationService


router = APIRouter()


async def read_limited_upload(upload: UploadFile, max_bytes: int) -> bytes:
    chunks: list[bytes] = []
    total_size = 0

    while True:
        chunk = await upload.read(1024 * 1024)
        if not chunk:
            break
        total_size += len(chunk)
        if total_size > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Resume file exceeds the configured size limit",
            )
        chunks.append(chunk)

    return b"".join(chunks)


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
    candidate_id: uuid.UUID | None = None,
    job_id: uuid.UUID | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: CurrentUser = Depends(get_current_user),
    service: ApplicationService = Depends(get_application_service),
) -> list[ApplicationResponse]:
    return await service.list_applications(
        candidate_id=candidate_id,
        job_id=job_id,
        current_user=current_user,
        limit=limit,
        offset=offset,
    )


@router.post("/{application_id}/resume", response_model=ApplicationResponse)
async def upload_application_resume(
    application_id: uuid.UUID,
    resume: UploadFile = File(...),
    current_user: CurrentUser = Depends(require_role("CANDIDATE")),
    service: ApplicationService = Depends(get_application_service),
) -> ApplicationResponse:
    settings = get_settings()
    file_bytes = await read_limited_upload(resume, settings.max_resume_size_bytes)
    return await service.upload_resume(
        application_id,
        file_name=resume.filename or "resume",
        content_type=resume.content_type or "application/octet-stream",
        file_bytes=file_bytes,
        current_user=current_user,
    )