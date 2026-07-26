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


class DeleteCascadeActivityResult(BaseModel):
    resource_id: uuid.UUID
    deleted: bool


class ListRecruiterJobsActivityResult(BaseModel):
    recruiter_id: uuid.UUID
    job_ids: list[uuid.UUID]


class CandidateDeletionWorkflowResult(BaseModel):
    status: Literal["success"]
    candidate_id: uuid.UUID


class JobDeletionWorkflowResult(BaseModel):
    status: Literal["success"]
    job_id: uuid.UUID


class RecruiterDeletionWorkflowResult(BaseModel):
    status: Literal["success"]
    recruiter_id: uuid.UUID
    deleted_job_count: int


class NotificationRecordActivityResult(BaseModel):
    notification_id: uuid.UUID
    status: str


class NotificationDeliveryWorkflowResult(BaseModel):
    status: Literal["success"]
    notification_id: uuid.UUID
    notification_status: str
