from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


ApplicationStatus = Literal["submitted", "reviewed", "rejected", "accepted"]


class ApplicationCreate(BaseModel):
    job_id: uuid.UUID
    candidate_id: uuid.UUID


class ApplicationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_id: uuid.UUID
    candidate_id: uuid.UUID
    recruiter_id: uuid.UUID | None
    status: ApplicationStatus
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        validation_alias=AliasChoices("application_metadata", "metadata"),
    )
    created_at: datetime
    updated_at: datetime