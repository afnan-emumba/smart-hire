from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


JobStatus = Literal["draft", "publishing", "published", "closed"]


class JobCreate(BaseModel):
    recruiter_id: uuid.UUID
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1)
    required_skills: list[str] = Field(default_factory=list)
    status: JobStatus = "draft"


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    recruiter_id: uuid.UUID
    title: str
    description: str
    status: JobStatus
    created_at: datetime
    updated_at: datetime