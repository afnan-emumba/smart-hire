from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import JobStatus
from app.schemas.job_breakdown import Compensation, JobBreakdown, JobLocation

EmploymentType = Literal[
    "full_time", "part_time", "contract", "temporary", "internship", "freelance"
]
SeniorityLevel = Literal[
    "intern",
    "junior",
    "mid",
    "senior",
    "lead",
    "staff",
    "principal",
    "manager",
    "director",
]
JobDescriptionSourceType = Literal["manual_text", "pdf_upload"]
JobDescriptionParsingStatus = Literal[
    "pending",
    "processing",
    "parsed",
    "failed",
]


class JobCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, min_length=1)
    employment_type: EmploymentType | None = None
    seniority_level: SeniorityLevel | None = None
    department: str | None = Field(default=None, min_length=1, max_length=100)
    job_category: str | None = Field(default=None, min_length=1, max_length=100)
    location: JobLocation | None = None
    compensation: Compensation | None = None
    years_of_experience_required: int | None = Field(default=None, ge=0)
    application_deadline: datetime | None = None
    required_skills: list[str] = Field(default_factory=list)


class JobBreakdownFields(BaseModel):
    model_config = ConfigDict(extra="forbid")

    employment_type: EmploymentType | None = None
    seniority_level: SeniorityLevel | None = None
    department: str | None = None
    job_category: str | None = None
    location: JobLocation | None = None
    compensation: Compensation | None = None
    years_of_experience_required: int | None = None
    application_deadline: datetime | None = None
    description_breakdown: JobBreakdown | None = None
    required_skills: list[str] = Field(default_factory=list)
    jd_parsing_status: JobDescriptionParsingStatus = "pending"
    jd_parsing_error: str | None = None
    status: JobStatus = JobStatus.DRAFT


class JobCreatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    description: str | None = None
    employment_type: EmploymentType | None = None
    seniority_level: SeniorityLevel | None = None
    department: str | None = None
    job_category: str | None = None
    location: JobLocation | None = None
    compensation: Compensation | None = None
    years_of_experience_required: int | None = None
    application_deadline: datetime | None = None
    required_skills: list[str] = Field(default_factory=list)
    jd_source_type: JobDescriptionSourceType | None = None
    jd_parsing_status: JobDescriptionParsingStatus = "pending"
    jd_parsing_error: str | None = None
    description_breakdown: JobBreakdown | None = None
    status: JobStatus = JobStatus.DRAFT


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    recruiter_id: uuid.UUID
    title: str
    description: str | None
    employment_type: EmploymentType | None = None
    seniority_level: SeniorityLevel | None = None
    department: str | None = None
    job_category: str | None = None
    location: JobLocation | None = None
    compensation: Compensation | None = None
    years_of_experience_required: int | None = None
    application_deadline: datetime | None = None
    description_breakdown: JobBreakdown | None = None
    required_skills: list[str]
    jd_source_type: JobDescriptionSourceType | None = None
    jd_parsing_status: JobDescriptionParsingStatus
    jd_parsing_error: str | None = None
    jd_file_name: str | None = None
    jd_content_type: str | None = None
    jd_uploaded_at: datetime | None = None
    status: JobStatus
    created_at: datetime
    updated_at: datetime


class PublishJobResponse(BaseModel):
    job_id: uuid.UUID
    workflow_id: str
    status: JobStatus


class JobBreakdownValidationResponse(BaseModel):
    job_id: uuid.UUID
    breakdown_validated: bool
    jd_parsing_status: JobDescriptionParsingStatus


class JobUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, min_length=1)
    employment_type: EmploymentType | None = None
    seniority_level: SeniorityLevel | None = None
    department: str | None = Field(default=None, min_length=1, max_length=100)
    job_category: str | None = Field(default=None, min_length=1, max_length=100)
    location: JobLocation | None = None
    compensation: Compensation | None = None
    years_of_experience_required: int | None = Field(default=None, ge=0)
    application_deadline: datetime | None = None
    required_skills: list[str] | None = None
