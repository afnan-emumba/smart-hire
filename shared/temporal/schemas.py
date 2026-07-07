from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel


class JobBreakdownActivityResult(BaseModel):
    job_id: uuid.UUID
    breakdown_validated: bool
    jd_parsing_status: str


class JobStatusActivityResult(BaseModel):
    job_id: uuid.UUID
    status: str


class JobPublishingWorkflowResult(BaseModel):
    status: Literal["success"]
    job_id: uuid.UUID
    job_status: str


class ResumeParsingActivityResult(BaseModel):
    resume_id: uuid.UUID
    parsing_status: str


class ResumeParsingWorkflowResult(BaseModel):
    status: Literal["success"]
    resume_id: uuid.UUID
    parsing_status: str
