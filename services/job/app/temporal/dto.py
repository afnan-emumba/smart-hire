from __future__ import annotations

from dataclasses import dataclass


@dataclass
class JobDeletionInput:
    """Payload for the job deletion cascade.

    Field names are part of a cross-service contract: user-service's
    ``RecruiterDeletionWorkflow`` starts this workflow as a child and serializes
    its own identically-shaped dataclass into it.
    """

    job_id: str
    actor_user_id: str
    actor_role: str
