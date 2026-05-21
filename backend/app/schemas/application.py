from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from app.core.application_states import ApplicationStatus


class ApplicationCreate(BaseModel):
    job_id: uuid.UUID


class EligibilityResult(BaseModel):
    is_eligible: bool
    reason: str
    missing_skills: list[str] = Field(default_factory=list)
    match_score: float


class ApplicationStatusUpdate(BaseModel):
    status: ApplicationStatus


class ApplicationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_id: uuid.UUID
    candidate_id: uuid.UUID
    status: ApplicationStatus
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        validation_alias=AliasChoices("application_metadata", "metadata"),
    )
    resume_file_name: str | None = None
    resume_content_type: str | None = None
    resume_uploaded_at: datetime | None = None
    resume_data: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime