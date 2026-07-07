from __future__ import annotations

from app.core.config import get_settings
from db.session import build_service_session, ping_database

settings = get_settings()

engine, SessionLocal, get_db_session = build_service_session(
    settings.database_url)

__all__ = ["SessionLocal", "get_db_session", "ping_database"]
