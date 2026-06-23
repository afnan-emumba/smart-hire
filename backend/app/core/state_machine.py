from __future__ import annotations

from app.core.enums import JobStatus, is_valid_transition


class StateMachine:
    @staticmethod
    def can_transition(from_state: JobStatus, to_state: JobStatus) -> bool:
        return is_valid_transition(from_state, to_state)
