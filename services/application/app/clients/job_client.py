from __future__ import annotations

import logging
import uuid

from app.core.config import Settings
from auth.header_auth import CurrentUser
from contracts.service_responses import JobResponseContract
from http_client.base_client import BaseServiceClient
from http_client.constants import (DEFAULT_JOB_PAGE_SIZE,
                                   MAX_JOBS_PER_RECRUITER, QUERY_PARAM_LIMIT,
                                   QUERY_PARAM_OFFSET,
                                   QUERY_PARAM_RECRUITER_ID)

logger = logging.getLogger(__name__)


class JobClient(BaseServiceClient):
    def __init__(self, settings: Settings) -> None:
        super().__init__(
            base_url=settings.job_service_url,
            timeout=settings.http_client_timeout_seconds,
            service_label="Job service",
        )

    async def get_job(self, job_id: uuid.UUID, current_user: CurrentUser) -> JobResponseContract | None:
        response = await self._get(f"/jobs/{job_id}", headers=self._headers(current_user))
        if response.status_code == 404:
            return None
        self._raise_for_status(response)
        return JobResponseContract.model_validate(response.json())

    async def list_by_recruiter(
        self,
        recruiter_id: uuid.UUID,
        current_user: CurrentUser,
    ) -> list[JobResponseContract]:
        jobs: list[JobResponseContract] = []
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

            page = [JobResponseContract.model_validate(
                item) for item in response.json()]
            jobs.extend(page)
            if len(page) < DEFAULT_JOB_PAGE_SIZE:
                break
            if len(jobs) >= MAX_JOBS_PER_RECRUITER:
                logger.warning(
                    "Recruiter %s has more than %d jobs; truncating list_by_recruiter results",
                    recruiter_id,
                    MAX_JOBS_PER_RECRUITER,
                )
                break
            offset += DEFAULT_JOB_PAGE_SIZE

        return jobs
