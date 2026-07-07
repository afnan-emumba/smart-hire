from __future__ import annotations

import json
import uuid
from typing import Any

from db.base import Base, TimestampMixin
from sqlalchemy import String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

DEFAULT_MASTER_PROFILE_DATA: dict[str, Any] = {
    "summary": None,
    "skills": [],
    "contact": {
        "phone": None,
        "location": None,
    },
    "education": [],
    "work_experience": [],
    "links": {
        "linkedin": None,
        "github": None,
        "portfolio": None,
        "website": None,
    },
}
DEFAULT_MASTER_PROFILE_DATA_JSON = json.dumps(DEFAULT_MASTER_PROFILE_DATA)


def default_master_profile_data() -> dict[str, Any]:
    return json.loads(DEFAULT_MASTER_PROFILE_DATA_JSON)


class Candidate(TimestampMixin, Base):
    __tablename__ = "candidates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    master_profile_data: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=default_master_profile_data,
        server_default=text(f"'{DEFAULT_MASTER_PROFILE_DATA_JSON}'::jsonb"),
    )
