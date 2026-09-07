from __future__ import annotations

from typing import Any


class ServiceError(Exception):
    def __init__(self, message: str, *, detail: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.detail: dict[str, Any] = detail or {}


class BadRequestError(ServiceError):
    pass


class ForbiddenError(ServiceError):
    pass


class NotFoundError(ServiceError):
    pass


class ConflictError(ServiceError):
    pass


class PayloadTooLargeError(ServiceError):
    pass


class InvalidStateTransitionError(ServiceError):
    pass


InvalidStateTransition = InvalidStateTransitionError


class ServiceUnavailableError(ServiceError):
    pass
