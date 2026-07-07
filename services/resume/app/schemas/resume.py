from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from contracts.enums import ResumeParsingStatus
from contracts.profile import ProfileLinks

# These models describe the output of a best-effort heuristic markdown parser
# (ResumeParsingService) whose shape evolves across schema_version bumps, so
# they tolerate unknown keys instead of hard-failing on drift when re-read
# from previously-stored JSONB.


class ResumeContact(BaseModel):
    model_config = ConfigDict(extra="ignore")

    email: str | None = None
    phone: str | None = None
    location: str | None = None


class ResumeLinks(ProfileLinks):
    model_config = ConfigDict(extra="ignore")


class ResumeTextEntry(BaseModel):
    model_config = ConfigDict(extra="ignore")

    raw_text: str


class ResumeStructuredData(BaseModel):
    model_config = ConfigDict(extra="ignore")

    summary: str | None = None
    skills: list[str] = Field(default_factory=list)
    contact: ResumeContact = Field(default_factory=ResumeContact)
    education: list[ResumeTextEntry] = Field(default_factory=list)
    work_experience: list[ResumeTextEntry] = Field(default_factory=list)
    projects: list[ResumeTextEntry] = Field(default_factory=list)
    certifications: list[ResumeTextEntry] = Field(default_factory=list)
    links: ResumeLinks = Field(default_factory=ResumeLinks)
    markdown: str


class ResumeExtractionMetadata(BaseModel):
    model_config = ConfigDict(extra="ignore")

    source: str | None = None
    last_processed_at: datetime | None = None
    parser_version: str | None = None
    schema_version: str | None = None


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
    structured_data: ResumeStructuredData | None = None
    extraction_metadata: ResumeExtractionMetadata = Field(
        default_factory=ResumeExtractionMetadata
    )
    created_at: datetime
    updated_at: datetime
