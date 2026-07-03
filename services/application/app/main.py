from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.clients.candidate_client import CandidateClient
from app.clients.job_client import JobClient
from app.clients.resume_client import ResumeClient
from app.core.config import get_settings
from exceptions.handlers import register_exception_handlers


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


app = FastAPI(
    title=settings.app_name,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


register_exception_handlers(app)

app.include_router(api_router)
