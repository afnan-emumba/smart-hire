from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status

from app.api.dependencies import get_job_service
from app.core.auth import CurrentUser, get_current_user, require_role
from app.core.config import get_settings
from app.schemas.job import JobCreate, JobResponse, JobStatus, JobUpdate, PublishJobResponse
from app.services.job_service import JobService


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
                detail="Job description file exceeds the configured size limit",
            )
        chunks.append(chunk)

    return b"".join(chunks)


@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def create_job(
    job_create: JobCreate,
    current_user: CurrentUser = Depends(require_role("RECRUITER")),
    service: JobService = Depends(get_job_service),
) -> JobResponse:
    return await service.create_job(job_create, current_user)


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    service: JobService = Depends(get_job_service),
) -> JobResponse:
    return await service.get_job(job_id)


@router.get("", response_model=list[JobResponse])
async def list_jobs(
    recruiter_id: uuid.UUID | None = None,
    status_filter: JobStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: CurrentUser = Depends(get_current_user),
    service: JobService = Depends(get_job_service),
) -> list[JobResponse]:
    return await service.list_jobs(
        recruiter_id=recruiter_id,
        status_filter=status_filter,
        limit=limit,
        offset=offset,
    )


@router.patch("/{job_id}", response_model=JobResponse)
async def update_job(
    job_id: uuid.UUID,
    job_update: JobUpdate,
    current_user: CurrentUser = Depends(require_role("RECRUITER")),
    service: JobService = Depends(get_job_service),
) -> JobResponse:
    return await service.update_job(job_id, job_update, current_user)


@router.post(
    "/{job_id}/description-file",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_job_description_file(
    job_id: uuid.UUID,
    description_file: UploadFile = File(...),
    current_user: CurrentUser = Depends(require_role("RECRUITER")),
    service: JobService = Depends(get_job_service),
) -> JobResponse:
    settings = get_settings()
    file_bytes = await read_limited_upload(description_file, settings.max_jd_size_bytes)
    return await service.upload_job_description(
        job_id,
        file_name=description_file.filename or "job-description.pdf",
        content_type=description_file.content_type or "application/octet-stream",
        file_bytes=file_bytes,
        current_user=current_user,
    )


@router.post("/{job_id}/publish", response_model=PublishJobResponse, status_code=status.HTTP_202_ACCEPTED)
async def publish_job(
    job_id: uuid.UUID,
    current_user: CurrentUser = Depends(require_role("RECRUITER")),
    service: JobService = Depends(get_job_service),
) -> PublishJobResponse:
    return await service.publish_job(job_id, current_user)


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job(
    job_id: uuid.UUID,
    current_user: CurrentUser = Depends(require_role("RECRUITER")),
    service: JobService = Depends(get_job_service),
) -> Response:
    await service.delete_job(job_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)