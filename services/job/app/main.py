from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.clients.application_client import ApplicationClient
from app.clients.recruiter_client import RecruiterClient
from app.core.config import get_settings
from app.temporal.client import TemporalClient
from exceptions.handlers import register_exception_handlers


settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.recruiter_client = RecruiterClient(settings)
    app.state.application_client = ApplicationClient(settings)
    yield
    await app.state.recruiter_client.aclose()
    await app.state.application_client.aclose()
    await TemporalClient.close()


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
