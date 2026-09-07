from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status

from api.pagination import PaginationParams
from app.api.dependencies import get_notification_service
from app.schemas.notification import NotificationCreate, NotificationResponse
from app.services.notification_service import NotificationService
from auth.header_auth import CurrentUser, get_current_user
from contracts.enums import UserRole
from exceptions.http_exceptions import ForbiddenError

router = APIRouter()


@router.post(
    "", response_model=NotificationResponse, status_code=status.HTTP_201_CREATED
)
async def create_notification(
    notification_create: NotificationCreate,
    current_user: CurrentUser = Depends(get_current_user),
    service: NotificationService = Depends(get_notification_service),
) -> NotificationResponse:
    return await service.create_notification(notification_create)


@router.get("", response_model=list[NotificationResponse])
async def list_notifications(
    recipient_user_id: uuid.UUID,
    pagination: PaginationParams = Depends(PaginationParams),
    current_user: CurrentUser = Depends(get_current_user),
    service: NotificationService = Depends(get_notification_service),
) -> list[NotificationResponse]:
    if current_user.role == UserRole.CANDIDATE and current_user.id != str(
        recipient_user_id
    ):
        raise ForbiddenError("Candidates can only view their own notifications")

    return await service.list_notifications(
        recipient_user_id, limit=pagination.limit, offset=pagination.offset
    )
