from __future__ import annotations

import logging
import uuid

from app.core.config import Settings
from auth.header_auth import CurrentUser
from contracts.service_responses import JobResponseContract
from http_client.base_client import BaseServiceClient
from http_client.constants import (
    DEFAULT_JOB_PAGE_SIZE,
    MAX_JOBS_PER_RECRUITER,
    QUERY_PARAM_LIMIT,
    QUERY_PARAM_OFFSET,
    QUERY_PARAM_RECRUITER_ID,
)

logger = logging.getLogger(__name__)


class JobClient(BaseServiceClient):
    def __init__(self, settings: Settings) -> None:
        super().__init__(
            base_url=settings.job_service_url,
            timeout=settings.http_client_timeout_seconds,
            service_label="Job service",
        )

    async def list_job_ids_for_recruiter(
        self,
        recruiter_id: uuid.UUID,
        current_user: CurrentUser,
    ) -> list[uuid.UUID]:
        job_ids: list[uuid.UUID] = []
        offset = 0
        while True:
            response = await self._get(
                "/jobs",
                params={
                    QUERY_PARAM_RECRUITER_ID: str(recruiter_id),
                    QUERY_PARAM_LIMIT: DEFAULT_JOB_PAGE_SIZE,
                    QUERY_PARAM_OFFSET: offset,
                },
                headers=self._headers(current_user),
            )
            self._raise_for_status(response)

            page = [
                JobResponseContract.model_validate(item) for item in response.json()
            ]
            job_ids.extend(job.id for job in page)
            if len(page) < DEFAULT_JOB_PAGE_SIZE:
                break
            if len(job_ids) >= MAX_JOBS_PER_RECRUITER:
                logger.warning(
                    "Recruiter %s has more than %d jobs; the deletion cascade will "
                    "only cover the first %d",
                    recruiter_id,
                    MAX_JOBS_PER_RECRUITER,
                    MAX_JOBS_PER_RECRUITER,
                )
                break
            offset += DEFAULT_JOB_PAGE_SIZE

        return job_ids
