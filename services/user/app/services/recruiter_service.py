from __future__ import annotations

import logging
import uuid
from datetime import timedelta

from sqlalchemy.exc import IntegrityError

from api.deletion import DeletionAcceptedResponse
from app.core.config import Settings
from app.repositories.recruiter_repo import RecruiterRepository
from app.schemas.recruiter import RecruiterCreate, RecruiterResponse
from app.temporal.client import TemporalClient
from app.temporal.constants import RECRUITER_DELETION_WORKFLOW_ID_PREFIX
from app.temporal.dto import RecruiterDeletionInput
from app.temporal.workflows import RecruiterDeletionWorkflow
from auth.actors import require_recruiter_user_id
from auth.header_auth import CurrentUser
from db.base import is_unique_violation
from db.deletion import is_deleting
from exceptions.http_exceptions import ConflictError, ForbiddenError, NotFoundError
from temporal.workflow_launcher import start_workflow_with_retryable_error_mapping

logger = logging.getLogger(__name__)


class RecruiterService:
    def __init__(self, recruiter_repo: RecruiterRepository, settings: Settings) -> None:
        self.recruiter_repo = recruiter_repo
        self.settings = settings

    async def create_recruiter(
        self, recruiter_create: RecruiterCreate, current_user: CurrentUser
    ) -> RecruiterResponse:
        recruiter_id = require_recruiter_user_id(current_user)

        existing_recruiter = await self.recruiter_repo.get_by_email(
            recruiter_create.email
        )
        if existing_recruiter is not None:
            raise ConflictError("Recruiter with this email already exists")

        try:
            recruiter = await self.recruiter_repo.create(recruiter_create, recruiter_id)
        except IntegrityError as exc:
            if is_unique_violation(exc):
                logger.info(
                    "Recruiter creation conflicted with a concurrent request",
                    extra={"email": recruiter_create.email},
                )
                raise ConflictError("Recruiter with this email already exists") from exc
            logger.exception(
                "Failed to create recruiter",
                extra={"email": recruiter_create.email},
            )
            raise

        return RecruiterResponse.model_validate(recruiter)

    async def get_recruiter(self, recruiter_id: uuid.UUID) -> RecruiterResponse:
        recruiter = await self.recruiter_repo.get_by_id(recruiter_id)
        if recruiter is None:
            raise NotFoundError("Recruiter not found")

        return RecruiterResponse.model_validate(recruiter)

    async def list_recruiters(
        self, *, limit: int, offset: int
    ) -> list[RecruiterResponse]:
        recruiters = await self.recruiter_repo.list_all(limit=limit, offset=offset)
        return [RecruiterResponse.model_validate(recruiter) for recruiter in recruiters]

    async def delete_recruiter(
        self, recruiter_id: uuid.UUID, current_user: CurrentUser
    ) -> DeletionAcceptedResponse:
        owner_id = require_recruiter_user_id(current_user)
        if owner_id != recruiter_id:
            raise ForbiddenError("Not authorized to delete this recruiter")

        recruiter = await self.recruiter_repo.get_by_id(recruiter_id)
        if recruiter is None:
            raise NotFoundError("Recruiter not found")

        workflow_id = f"{RECRUITER_DELETION_WORKFLOW_ID_PREFIX}-{recruiter_id}"
        if not is_deleting(recruiter):
            await self.recruiter_repo.mark_deleting(recruiter_id)
            await self.recruiter_repo.session.commit()

        await start_workflow_with_retryable_error_mapping(
            client_factory=TemporalClient.get_client,
            workflow=RecruiterDeletionWorkflow.run,
            workflow_input=RecruiterDeletionInput(
                recruiter_id=str(recruiter_id),
                actor_user_id=current_user.id,
                actor_role=current_user.role.value,
            ),
            workflow_id=workflow_id,
            task_queue=self.settings.temporal_user_deletion_task_queue,
            execution_timeout=timedelta(hours=1),
            logger=logger,
            context={"recruiter_id": str(recruiter_id)},
            conflict_log_message="Recruiter deletion workflow already running",
            failure_log_message="Failed to start recruiter deletion workflow",
            unavailable_message="Unable to start recruiter deletion right now",
        )

        return DeletionAcceptedResponse(
            resource_id=recruiter_id, workflow_id=workflow_id
        )
