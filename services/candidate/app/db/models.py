from __future__ import annotations

import json
import uuid

from sqlalchemy import String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.schemas.candidate import MasterProfileData
from db.base import Base, TimestampMixin

DEFAULT_MASTER_PROFILE_DATA = MasterProfileData().model_dump(mode="json")
DEFAULT_MASTER_PROFILE_DATA_JSON = json.dumps(DEFAULT_MASTER_PROFILE_DATA)


def default_master_profile_data() -> dict[str, object]:
    return json.loads(DEFAULT_MASTER_PROFILE_DATA_JSON)


class Candidate(TimestampMixin, Base):
    __tablename__ = "candidates"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(
        String(320), unique=True, nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    master_profile_data: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
        default=default_master_profile_data,
        server_default=text(f"'{DEFAULT_MASTER_PROFILE_DATA_JSON}'::jsonb"),
    )
