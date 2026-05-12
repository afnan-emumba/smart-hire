from __future__ import annotations

from collections.abc import Callable
from typing import Literal

from fastapi import Depends, Header, HTTPException, status
from pydantic import BaseModel


UserRole = Literal["RECRUITER", "CANDIDATE"]
ALLOWED_ROLES = {"RECRUITER", "CANDIDATE"}


class CurrentUser(BaseModel):
    id: str
    role: UserRole


async def get_current_user(
    x_user_id: str = Header(..., alias="X-User-ID", min_length=1),
    x_user_role: str = Header(..., alias="X-User-Role", min_length=1),
) -> CurrentUser:
    normalized_role = x_user_role.strip().upper()
    if normalized_role not in ALLOWED_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid user role",
        )

    return CurrentUser(id=x_user_id.strip(), role=normalized_role)


def require_role(*roles: UserRole) -> Callable[..., CurrentUser]:
    async def dependency(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized for this action",
            )
        return current_user

    return dependency