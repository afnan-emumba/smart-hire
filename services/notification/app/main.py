from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.app_factory import make_app
from app.api.router import api_router
from app.core.config import get_settings
from app.temporal.client import TemporalClient

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await TemporalClient.close()


app = make_app(app_name=settings.app_name, lifespan=lifespan)

app.include_router(api_router)
