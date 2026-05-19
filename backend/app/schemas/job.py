from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


JobStatus = Literal["draft", "processing", "ready", "archived"]
JobDescriptionSourceType = Literal["manual_text", "pdf_upload"]
JobDescriptionParsingStatus = Literal[
    "pending",
    "processing",
    "parsed",
    "failed",
]


class JobCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, min_length=1)
    required_skills: list[str] = Field(default_factory=list)


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    recruiter_id: uuid.UUID
    title: str
    description: str | None
    description_breakdown: dict[str, Any] | None = None
    required_skills: list[str]
    jd_source_type: JobDescriptionSourceType | None = None
    jd_parsing_status: JobDescriptionParsingStatus
    jd_parsing_error: str | None = None
    jd_file_name: str | None = None
    jd_content_type: str | None = None
    jd_uploaded_at: datetime | None = None
    status: JobStatus
    created_at: datetime
    updated_at: datetime


class JobUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, min_length=1)
    required_skills: list[str] | None = None
    status: JobStatus | None = None