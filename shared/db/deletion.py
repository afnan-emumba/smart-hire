from __future__ import annotations

from typing import Any, Protocol

from contracts.enums import DeletionState
from exceptions.http_exceptions import ConflictError


class SupportsDeletionState(Protocol):
    deletion_state: str


def is_deleting(record: SupportsDeletionState | Any) -> bool:
    return getattr(record, "deletion_state", None) == DeletionState.DELETING.value


def ensure_not_deleting(record: SupportsDeletionState | Any, message: str) -> None:
    """Reject a write against a record whose delete cascade is already in flight.

    Deleting records stay readable so in-flight cascades can still verify
    ownership across services; only writes are blocked.
    """
    if is_deleting(record):
        raise ConflictError(message)
