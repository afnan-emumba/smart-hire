from __future__ import annotations

from db.session import make_get_db_session, ping_database
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings


settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    future=True,
    pool_pre_ping=True,
)

SessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)

get_db_session = make_get_db_session(SessionLocal)

__all__ = ["SessionLocal", "get_db_session", "ping_database"]
