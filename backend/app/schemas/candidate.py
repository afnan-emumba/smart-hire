from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, StringConstraints


ProfileText = Annotated[str, StringConstraints(
    strip_whitespace=True, min_length=1, max_length=255)]


class CandidateCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    name: ProfileText


class CandidateUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr | None = None
    name: ProfileText | None = None


class CandidateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: uuid.UUID
    email: EmailStr
    name: str
    created_at: datetime
    updated_at: datetime
