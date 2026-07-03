from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status

from app.api.dependencies import get_resume_service
from app.core.config import get_settings
from app.schemas.resume import ResumeResponse
from app.services.resume_service import ResumeService
from auth.header_auth import CurrentUser, get_current_user, require_role


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


@router.post("", response_model=ResumeResponse, status_code=status.HTTP_201_CREATED)
async def upload_resume(
    resume: UploadFile = File(...),
    current_user: CurrentUser = Depends(require_role("CANDIDATE")),
    service: ResumeService = Depends(get_resume_service),
) -> ResumeResponse:
    settings = get_settings()
    file_bytes = await read_limited_upload(resume, settings.max_resume_size_bytes)
    return await service.upload_resume(
        file_name=resume.filename or "resume",
        content_type=resume.content_type or "application/octet-stream",
        file_bytes=file_bytes,
        current_user=current_user,
    )


@router.get("/{resume_id}", response_model=ResumeResponse)
async def get_resume(
    resume_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    service: ResumeService = Depends(get_resume_service),
) -> ResumeResponse:
    return await service.get_resume(resume_id, current_user)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_resumes(
    candidate_id: uuid.UUID,
    current_user: CurrentUser = Depends(require_role("CANDIDATE")),
    service: ResumeService = Depends(get_resume_service),
) -> Response:
    await service.delete_resumes_for_candidate(candidate_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("", response_model=list[ResumeResponse])
async def list_resumes(
    candidate_id: uuid.UUID | None = None,
    parsing_status: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: CurrentUser = Depends(get_current_user),
    service: ResumeService = Depends(get_resume_service),
) -> list[ResumeResponse]:
    return await service.list_resumes(
        candidate_id=candidate_id,
        current_user=current_user,
        parsing_status=parsing_status,
        limit=limit,
        offset=offset,
    )
