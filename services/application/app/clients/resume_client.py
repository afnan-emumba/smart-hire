from __future__ import annotations

import logging
import uuid

from pydantic import ValidationError

from app.core.config import Settings
from auth.header_auth import CurrentUser
from contracts.enums import ResumeParsingStatus
from contracts.service_responses import ResumeResponseContract
from http_client.base_client import BaseServiceClient
from http_client.constants import (
    QUERY_PARAM_CANDIDATE_ID,
    QUERY_PARAM_LIMIT,
    QUERY_PARAM_PARSING_STATUS,
)

logger = logging.getLogger(__name__)


class ResumeClient(BaseServiceClient):
    def __init__(self, settings: Settings) -> None:
        super().__init__(
            base_url=settings.resume_service_url,
            timeout=settings.http_client_timeout_seconds,
            service_label="Resume service",
        )

    async def get_latest_parsed_resume(
        self,
        candidate_id: uuid.UUID,
        current_user: CurrentUser,
    ) -> ResumeResponseContract | None:
        response = await self._get(
            "/resumes",
            params={
                QUERY_PARAM_CANDIDATE_ID: str(candidate_id),
                QUERY_PARAM_PARSING_STATUS: ResumeParsingStatus.PARSED.value,
                QUERY_PARAM_LIMIT: 1,
            },
            headers=self._headers(current_user),
        )
        if response.status_code == 404:
            return None
        self._raise_for_status(response)

        resumes = response.json()
        if not resumes:
            return None
        try:
            return ResumeResponseContract.model_validate(resumes[0])
        except ValidationError:
            logger.warning(
                "Resume service returned a resume payload that does not match "
                "ResumeResponseContract; treating as no usable resume",
                exc_info=True,
            )
            return None
