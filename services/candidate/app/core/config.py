from __future__ import annotations

from functools import lru_cache

from config.base import ServiceSettings
from pydantic import Field


class Settings(ServiceSettings):
    app_name: str = "Candidate Service"
    app_port: int = Field(default=8002, alias="APP_PORT")


@lru_cache
def get_settings() -> Settings:
    return Settings()
