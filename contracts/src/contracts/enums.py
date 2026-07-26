from __future__ import annotations

from enum import Enum


class UserRole(str, Enum):
    RECRUITER = "RECRUITER"
    CANDIDATE = "CANDIDATE"


class JobStatus(str, Enum):
    DRAFT = "draft"
    PROCESSING = "processing"
    READY = "ready"
    ARCHIVED = "archived"


class ResumeParsingStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    PARSED = "parsed"
    FAILED = "failed"
    UNSUPPORTED = "unsupported"


class DeletionState(str, Enum):
    """Lifecycle flag for records whose cross-service delete cascade is in flight.

    Enforced at the write boundary only: ``DELETING`` rows stay readable so that
    downstream ownership checks keep working while their cascade runs.
    """

    ACTIVE = "active"
    DELETING = "deleting"


class NotificationType(str, Enum):
    APPLICATION_STATUS_CHANGED = "application_status_changed"


class NotificationChannel(str, Enum):
    IN_APP = "in_app"


class NotificationStatus(str, Enum):
    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"
