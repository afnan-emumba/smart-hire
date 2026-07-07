from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from app.core.application_states import ApplicationStatus
from pydantic import BaseModel, ConfigDict, Field


class ApplicationCreate(BaseModel):
    job_id: uuid.UUID


class EligibilityReasonCode(str, Enum):
    ELIGIBLE = "eligible"
    JOB_NOT_READY = "job_not_ready"
    DUPLICATE_APPLICATION = "duplicate_application"
    MAX_ACTIVE_APPLICATIONS = "max_active_applications"
    INSUFFICIENT_SKILLS = "insufficient_skills"
    NO_REQUIRED_SKILLS = "no_required_skills"


class EligibilityResult(BaseModel):
    is_eligible: bool
    reason_code: EligibilityReasonCode
    reason: str
    missing_skills: list[str] = Field(default_factory=list)
    match_score: float
    resume_id: uuid.UUID | None = None


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
        validation_alias="application_metadata",
    )
    resume_id: uuid.UUID | None = None
    eligibility_result: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime
