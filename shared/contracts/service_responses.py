from __future__ import annotations

import uuid
from datetime import datetime

from contracts.enums import JobStatus, ResumeParsingStatus
from pydantic import BaseModel, ConfigDict, Field


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


class ResumeStructuredDataContract(BaseModel):
    model_config = ConfigDict(extra="ignore")

    skills: list[str] = Field(default_factory=list)


class ResumeResponseContract(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: uuid.UUID
    parsing_status: ResumeParsingStatus
    structured_data: ResumeStructuredDataContract | None = None
