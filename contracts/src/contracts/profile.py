from __future__ import annotations

from pydantic import AnyHttpUrl, BaseModel


class ProfileLinks(BaseModel):
    linkedin: AnyHttpUrl | None = None
    github: AnyHttpUrl | None = None
    portfolio: AnyHttpUrl | None = None
    website: AnyHttpUrl | None = None
