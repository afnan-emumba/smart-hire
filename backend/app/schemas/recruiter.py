from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RecruiterCreate(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=255)


class RecruiterResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    name: str
    created_at: datetime
    updated_at: datetime