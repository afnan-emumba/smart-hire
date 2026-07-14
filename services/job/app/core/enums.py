from __future__ import annotations

from enum import Enum

from contracts.enums import JobStatus

__all__ = [
    "JobStatus",
    "JobDescriptionSourceType",
    "JobDescriptionParsingStatus",
    "is_valid_transition",
]


class JobDescriptionSourceType(str, Enum):
    MANUAL_TEXT = "manual_text"
    PDF_UPLOAD = "pdf_upload"


class JobDescriptionParsingStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    PARSED = "parsed"
    FAILED = "failed"


_VALID_JOB_TRANSITIONS: dict[JobStatus, set[JobStatus]] = {
    JobStatus.DRAFT: {JobStatus.PROCESSING},
    JobStatus.PROCESSING: {JobStatus.READY, JobStatus.DRAFT},
    JobStatus.READY: {JobStatus.ARCHIVED},
    JobStatus.ARCHIVED: set(),
}


def is_valid_transition(from_state: JobStatus, to_state: JobStatus) -> bool:
    return to_state in _VALID_JOB_TRANSITIONS.get(from_state, set())
