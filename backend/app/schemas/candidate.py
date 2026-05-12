from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class CandidateCreate(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=255)
    resume_data: dict[str, Any] | None = None


class CandidateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    name: str
    resume_data: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime