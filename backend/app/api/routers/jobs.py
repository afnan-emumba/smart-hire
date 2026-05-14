from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.dependencies import get_job_service
from app.core.auth import CurrentUser, get_current_user, require_role
from app.schemas.job import JobCreate, JobResponse, JobStatus, JobUpdate
from app.services.job_service import JobService


router = APIRouter()


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


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job(
    job_id: uuid.UUID,
    current_user: CurrentUser = Depends(require_role("RECRUITER")),
    service: JobService = Depends(get_job_service),
) -> Response:
    await service.delete_job(job_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)