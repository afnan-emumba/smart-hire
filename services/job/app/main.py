from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.app_factory import make_app
from app.api.router import api_router
from app.clients.application_client import ApplicationClient
from app.clients.recruiter_client import RecruiterClient
from app.core.config import get_settings
from app.temporal.client import TemporalClient

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.recruiter_client = RecruiterClient(settings)
    app.state.application_client = ApplicationClient(settings)
    yield
    await app.state.recruiter_client.aclose()
    await app.state.application_client.aclose()
    await TemporalClient.close()


app = make_app(app_name=settings.app_name, lifespan=lifespan)

app.include_router(api_router)
