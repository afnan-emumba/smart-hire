from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ResumeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    candidate_id: uuid.UUID
    source_application_id: uuid.UUID | None = None
    file_name: str | None = None
    content_type: str | None = None
    uploaded_at: datetime | None = None
    parsing_status: str
    parsing_error: str | None = None
    parsed_at: datetime | None = None
    parser_version: str | None = None
    schema_version: str
    structured_data: dict[str, Any] | None = None
    extraction_metadata: dict[str, Any] = Field(default_factory=dict)