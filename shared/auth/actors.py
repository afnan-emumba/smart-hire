from __future__ import annotations

import uuid

from auth.header_auth import CurrentUser
from exceptions.http_exceptions import BadRequestError, ForbiddenError


def require_candidate_user_id(current_user: CurrentUser) -> uuid.UUID:
    if current_user.role != "CANDIDATE":
        raise ForbiddenError("Only candidates can perform this action")

    try:
        return uuid.UUID(current_user.id)
    except ValueError as exc:
        raise BadRequestError("X-User-ID must be a valid candidate UUID") from exc


def require_recruiter_user_id(current_user: CurrentUser) -> uuid.UUID:
    if current_user.role != "RECRUITER":
        raise ForbiddenError("Only recruiters can perform this action")

    try:
        return uuid.UUID(current_user.id)
    except ValueError as exc:
        raise BadRequestError("X-User-ID must be a valid recruiter UUID") from exc
