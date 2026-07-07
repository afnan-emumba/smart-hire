from __future__ import annotations

from functools import lru_cache

from pydantic import Field

from config.base import ServiceSettings


class Settings(ServiceSettings):
    app_name: str = "Recruiter Service"
    app_port: int = Field(default=8001, alias="APP_PORT")


@lru_cache
def get_settings() -> Settings:
    return Settings()
