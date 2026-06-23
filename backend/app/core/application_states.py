from __future__ import annotations

from enum import Enum


class ApplicationStatus(str, Enum):
    PENDING = "pending"
    SCREENING = "screening"
    INTERVIEW = "interview"
    OFFER = "offer"
    REJECTED = "rejected"
    ACCEPTED = "accepted"


_VALID_APPLICATION_TRANSITIONS: dict[ApplicationStatus, set[ApplicationStatus]] = {
    ApplicationStatus.PENDING: {
        ApplicationStatus.SCREENING,
        ApplicationStatus.REJECTED,
    },
    ApplicationStatus.SCREENING: {
        ApplicationStatus.INTERVIEW,
        ApplicationStatus.REJECTED,
    },
    ApplicationStatus.INTERVIEW: {
        ApplicationStatus.OFFER,
        ApplicationStatus.REJECTED,
    },
    ApplicationStatus.OFFER: {
        ApplicationStatus.ACCEPTED,
        ApplicationStatus.REJECTED,
    },
    ApplicationStatus.REJECTED: set(),
    ApplicationStatus.ACCEPTED: set(),
}


def is_valid_app_transition(
    from_state: ApplicationStatus,
    to_state: ApplicationStatus,
) -> bool:
    return to_state in _VALID_APPLICATION_TRANSITIONS.get(from_state, set())