from __future__ import annotations

import uuid

from fastapi import HTTPException, status

from app.repositories.recruiter_repo import RecruiterRepository
from app.schemas.recruiter import RecruiterCreate, RecruiterResponse


class RecruiterService:
    def __init__(self, recruiter_repo: RecruiterRepository) -> None:
        self.recruiter_repo = recruiter_repo

    async def create_recruiter(self, recruiter_create: RecruiterCreate) -> RecruiterResponse:
        existing_recruiter = await self.recruiter_repo.get_by_email(recruiter_create.email)
        if existing_recruiter is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Recruiter with this email already exists",
            )

        recruiter = await self.recruiter_repo.create(recruiter_create)
        return RecruiterResponse.model_validate(recruiter)

    async def get_recruiter(self, recruiter_id: uuid.UUID) -> RecruiterResponse:
        recruiter = await self.recruiter_repo.get_by_id(recruiter_id)
        if recruiter is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Recruiter not found",
            )

        return RecruiterResponse.model_validate(recruiter)

    async def list_recruiters(self) -> list[RecruiterResponse]:
        recruiters = await self.recruiter_repo.list_all()
        return [RecruiterResponse.model_validate(recruiter) for recruiter in recruiters]