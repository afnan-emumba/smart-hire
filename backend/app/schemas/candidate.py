from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class CandidateCreate(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=255)
    master_profile_data: dict[str, Any] = Field(default_factory=dict)


class CandidateUpdate(BaseModel):
    email: EmailStr | None = None
    name: str | None = Field(default=None, min_length=1, max_length=255)
    master_profile_data: dict[str, Any] | None = None


class CandidateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    name: str
    master_profile_data: dict[str, Any]
    created_at: datetime
    updated_at: datetime