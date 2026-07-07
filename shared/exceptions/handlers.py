from __future__ import annotations

import logging

from exceptions.http_exceptions import (BadRequestError, ConflictError,
                                        ForbiddenError,
                                        InvalidStateTransitionError,
                                        NotFoundError, PayloadTooLargeError,
                                        ServiceUnavailableError)
from fastapi import FastAPI
from fastapi.responses import JSONResponse


def _json_error(status_code: int, detail: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"detail": detail})


def register_exception_handlers(app: FastAPI) -> None:
    logger = logging.getLogger(app.title)

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
