from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


JobStatus = Literal["draft", "publishing", "published", "closed"]


class JobCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1)
    required_skills: list[str] = Field(default_factory=list)


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    recruiter_id: uuid.UUID
    title: str
    description: str
    description_breakdown: dict[str, Any] | None = None
    required_skills: list[str]
    status: JobStatus
    created_at: datetime
    updated_at: datetime


class JobUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, min_length=1)
    description_breakdown: dict[str, Any] | None = None
    required_skills: list[str] | None = None
    status: JobStatus | None = None