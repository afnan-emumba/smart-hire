from __future__ import annotations

from enum import Enum


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
