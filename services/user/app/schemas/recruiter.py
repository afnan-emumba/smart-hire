from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, StringConstraints

RecruiterName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
]


class RecruiterCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    name: RecruiterName


class RecruiterResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    name: str
    created_at: datetime
    updated_at: datetime
