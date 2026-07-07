from __future__ import annotations

from contracts.enums import JobStatus

__all__ = ["JobStatus", "is_valid_transition"]

_VALID_JOB_TRANSITIONS: dict[JobStatus, set[JobStatus]] = {
    JobStatus.DRAFT: {JobStatus.PROCESSING},
    JobStatus.PROCESSING: {JobStatus.READY},
    JobStatus.READY: {JobStatus.ARCHIVED},
    JobStatus.ARCHIVED: set(),
}


def is_valid_transition(from_state: JobStatus, to_state: JobStatus) -> bool:
    return to_state in _VALID_JOB_TRANSITIONS.get(from_state, set())
