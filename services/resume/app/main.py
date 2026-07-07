from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.app_factory import make_app
from app.api.router import api_router
from app.clients.candidate_client import CandidateClient
from app.core.config import get_settings
from app.temporal.client import TemporalClient

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.candidate_client = CandidateClient(settings)
    yield
    await app.state.candidate_client.aclose()
    await TemporalClient.close()


app = make_app(app_name=settings.app_name, lifespan=lifespan)

app.include_router(api_router)
