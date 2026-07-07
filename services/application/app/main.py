from __future__ import annotations

from contextlib import asynccontextmanager

from api.app_factory import make_app
from app.api.router import api_router
from app.clients.candidate_client import CandidateClient
from app.clients.job_client import JobClient
from app.clients.resume_client import ResumeClient
from app.core.config import get_settings
from fastapi import FastAPI

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.job_client = JobClient(settings)
    app.state.candidate_client = CandidateClient(settings)
    app.state.resume_client = ResumeClient(settings)
    yield
    await app.state.job_client.aclose()
    await app.state.candidate_client.aclose()
    await app.state.resume_client.aclose()


app = make_app(app_name=settings.app_name, lifespan=lifespan)

app.include_router(api_router)
