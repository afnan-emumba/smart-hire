from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.app_factory import make_app
from app.api.router import api_router
from app.clients.application_client import ApplicationClient
from app.clients.resume_client import ResumeClient
from app.core.config import get_settings

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.resume_client = ResumeClient(settings)
    app.state.application_client = ApplicationClient(settings)
    yield
    await app.state.resume_client.aclose()
    await app.state.application_client.aclose()


app = make_app(app_name=settings.app_name, lifespan=lifespan)

app.include_router(api_router)
