from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from contracts.enums import JobStatus, ResumeParsingStatus
from contracts.profile import ProfileLinks


class CandidateMasterProfileContract(BaseModel):
    model_config = ConfigDict(extra="ignore")

    skills: list[str] = Field(default_factory=list)


class CandidateResponseContract(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: uuid.UUID
    master_profile_data: CandidateMasterProfileContract = Field(
        default_factory=CandidateMasterProfileContract,
    )


class JobResponseContract(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: uuid.UUID
    recruiter_id: uuid.UUID
    status: JobStatus
    required_skills: list[str] = Field(default_factory=list)


class RecruiterResponseContract(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: uuid.UUID
    email: str
    name: str
    created_at: datetime
    updated_at: datetime


class ResumeContactContract(BaseModel):
    model_config = ConfigDict(extra="ignore")

    phone: str | None = None
    location: str | None = None


class ResumeStructuredDataContract(BaseModel):
    model_config = ConfigDict(extra="ignore")

    summary: str | None = None
    skills: list[str] = Field(default_factory=list)
    contact: ResumeContactContract = Field(default_factory=ResumeContactContract)
    links: ProfileLinks = Field(default_factory=ProfileLinks)


class ResumeResponseContract(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: uuid.UUID
    parsing_status: ResumeParsingStatus
    structured_data: ResumeStructuredDataContract | None = None
