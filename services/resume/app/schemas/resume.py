from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ResumeParsingStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    PARSED = "parsed"
    FAILED = "failed"
    UNSUPPORTED = "unsupported"


class ResumeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    candidate_id: uuid.UUID
    file_name: str | None = None
    content_type: str | None = None
    uploaded_at: datetime | None = None
    parsing_status: ResumeParsingStatus
    parsing_error: str | None = None
    parsed_at: datetime | None = None
    parser_version: str | None = None
    schema_version: str
    structured_data: dict[str, Any] | None = None
    extraction_metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
