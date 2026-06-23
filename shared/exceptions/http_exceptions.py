from __future__ import annotations


class ServiceError(Exception):
    pass


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


# Alias kept for backward compatibility within migrated services
InvalidStateTransition = InvalidStateTransitionError


class ServiceUnavailableError(ServiceError):
    pass
