from __future__ import annotations

from datetime import datetime, timezone

from app.core.enums import JobStatus, is_valid_transition
from app.db.models import Job
from app.services.exceptions import InvalidStateTransition


class StateMachine:
    @staticmethod
    def can_transition(from_state: JobStatus, to_state: JobStatus) -> bool:
        return is_valid_transition(from_state, to_state)

    @staticmethod
    def transition(job: Job, from_state: JobStatus, to_state: JobStatus) -> bool:
        current_state = JobStatus(job.status)
        if current_state != from_state or not is_valid_transition(from_state, to_state):
            raise InvalidStateTransition(
                f"Invalid job state transition from '{from_state.value}' to '{to_state.value}'"
            )

        job.status = to_state.value
        job.updated_at = datetime.now(timezone.utc)
        return True