from __future__ import annotations

from collections.abc import AsyncGenerator, Callable
from typing import NamedTuple

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (AsyncEngine, AsyncSession,
                                    async_sessionmaker, create_async_engine)


async def ping_database(session: AsyncSession) -> bool:
    result = await session.execute(text("SELECT 1"))
    return result.scalar_one() == 1


def make_get_db_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> Callable[[], AsyncGenerator[AsyncSession, None]]:
    async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    return get_db_session


class ServiceSession(NamedTuple):
    engine: AsyncEngine
    session_local: async_sessionmaker[AsyncSession]
    get_db_session: Callable[[], AsyncGenerator[AsyncSession, None]]


def build_service_session(database_url: str) -> ServiceSession:
    engine = create_async_engine(
        database_url,
        future=True,
        pool_pre_ping=True,
    )

    session_local = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )

    return ServiceSession(engine, session_local, make_get_db_session(session_local))
