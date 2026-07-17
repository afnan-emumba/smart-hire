from __future__ import annotations

import asyncio
import logging
import uuid

from app.clients.application_client import ApplicationClient
from app.clients.resume_client import ResumeClient
from auth.header_auth import CurrentUser
from exceptions.http_exceptions import ServiceUnavailableError

logger = logging.getLogger(__name__)


class UserLifecycleCoordinator:
    """Coordinates cross-service cleanup triggered by user lifecycle changes.

    Today this is a synchronous, fail-closed fan-out over HTTP. It is isolated
    here as a seam so the transport can later become a Kafka ``CandidateDeleted``
    domain event or a Temporal saga without touching the routers or services.
    """

    def __init__(
        self,
        resume_client: ResumeClient,
        application_client: ApplicationClient,
    ) -> None:
        self.resume_client = resume_client
        self.application_client = application_client

    async def on_candidate_deleted(
        self, candidate_id: uuid.UUID, current_user: CurrentUser
    ) -> None:
        results = await asyncio.gather(
            self.resume_client.delete_resumes_for_candidate(candidate_id, current_user),
            self.application_client.delete_applications_for_candidate(
                candidate_id, current_user
            ),
            return_exceptions=True,
        )
        failures = [result for result in results if isinstance(result, Exception)]
        if failures:
            logger.error(
                "Failed to cascade-delete one or more of the candidate's dependents; "
                "candidate was not deleted, safe to retry",
                extra={"candidate_id": str(candidate_id)},
                exc_info=failures[0],
            )
            raise ServiceUnavailableError(
                "Failed to delete the candidate's resumes or applications; "
                "the candidate was not deleted, please retry"
            ) from failures[0]
