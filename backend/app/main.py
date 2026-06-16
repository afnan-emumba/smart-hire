from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core.config import get_settings
from app.services.exceptions import (
    BadRequestError,
    ConflictError,
    ForbiddenError,
    InvalidStateTransitionError,
    NotFoundError,
    PayloadTooLargeError,
    ServiceUnavailableError,
)
from app.temporal.client import TemporalClient


settings = get_settings()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle startup and shutdown events."""
    # Startup
    yield
    # Shutdown
    await TemporalClient.close()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
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


def _json_error(status_code: int, detail: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"detail": detail})


@app.exception_handler(BadRequestError)
async def handle_bad_request(_: object, exc: BadRequestError) -> JSONResponse:
    return _json_error(400, str(exc))


@app.exception_handler(ForbiddenError)
async def handle_forbidden(_: object, exc: ForbiddenError) -> JSONResponse:
    return _json_error(403, str(exc))


@app.exception_handler(NotFoundError)
async def handle_not_found(_: object, exc: NotFoundError) -> JSONResponse:
    return _json_error(404, str(exc))


@app.exception_handler(ConflictError)
async def handle_conflict(_: object, exc: ConflictError) -> JSONResponse:
    return _json_error(409, str(exc))


@app.exception_handler(PayloadTooLargeError)
async def handle_payload_too_large(_: object, exc: PayloadTooLargeError) -> JSONResponse:
    return _json_error(413, str(exc))


@app.exception_handler(InvalidStateTransitionError)
async def handle_invalid_state_transition(
    _: object,
    exc: InvalidStateTransitionError,
) -> JSONResponse:
    return _json_error(400, str(exc))


@app.exception_handler(ServiceUnavailableError)
async def handle_service_unavailable(_: object, exc: ServiceUnavailableError) -> JSONResponse:
    logger.error(
        "Service unavailable",
        exc_info=(type(exc), exc, exc.__traceback__),
    )
    return _json_error(503, str(exc))


@app.exception_handler(Exception)
async def handle_unexpected_error(_: object, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled application error", exc_info=exc)
    return _json_error(500, "Internal server error")


app.include_router(api_router)
