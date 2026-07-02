from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.application_states import ApplicationStatus
from app.db.models import Application, ApplicationStatusHistory
from app.schemas.application import ApplicationCreate


class ApplicationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _base_query():
        return select(Application)

    async def create(
        self,
        application_create: ApplicationCreate,
        *,
        candidate_id: uuid.UUID,
        status: ApplicationStatus,
        eligibility_result: dict[str, Any] | None = None,
        resume_id: uuid.UUID | None = None,
    ) -> Application:
        application = Application(
            **application_create.model_dump(),
            candidate_id=candidate_id,
            status=status.value,
            eligibility_result=eligibility_result,
            resume_id=resume_id,
        )
        self.session.add(application)
        await self.session.flush()
        self._add_status_history_entry(
            application,
            from_status=None,
            to_status=status.value,
            changed_by_user_id=candidate_id,
            changed_by_role="CANDIDATE",
        )
        await self.session.flush()
        return await self.get_by_id(application.id)

    async def get_by_id(self, application_id: uuid.UUID) -> Application | None:
        result = await self.session.execute(
            self._base_query().where(Application.id == application_id)
        )
        return result.scalar_one_or_none()

    async def get_by_job_and_candidate(
        self,
        job_id: uuid.UUID,
        candidate_id: uuid.UUID,
    ) -> Application | None:
        result = await self.session.execute(
            self._base_query().where(
                Application.job_id == job_id,
                Application.candidate_id == candidate_id,
            )
        )
        return result.scalar_one_or_none()

    async def count_active_by_candidate(self, candidate_id: uuid.UUID) -> int:
        terminal_statuses = {
            ApplicationStatus.REJECTED.value,
            ApplicationStatus.ACCEPTED.value,
        }
        result = await self.session.execute(
            select(func.count())
            .select_from(Application)
            .where(
                Application.candidate_id == candidate_id,
                Application.status.not_in(terminal_statuses),
            )
        )
        return result.scalar_one()

    async def list_by_candidate(
        self,
        candidate_id: uuid.UUID,
        *,
        status_filter: str | None,
        limit: int,
        offset: int,
    ) -> list[Application]:
        stmt = self._base_query().where(Application.candidate_id == candidate_id)
        if status_filter is not None:
            stmt = stmt.where(Application.status == status_filter)
        result = await self.session.execute(
            stmt.order_by(Application.created_at.desc()).limit(limit).offset(offset)
        )
        return list(result.scalars().all())

    async def list_by_job(
        self,
        job_id: uuid.UUID,
        *,
        status_filter: str | None,
        limit: int,
        offset: int,
    ) -> list[Application]:
        stmt = self._base_query().where(Application.job_id == job_id)
        if status_filter is not None:
            stmt = stmt.where(Application.status == status_filter)
        result = await self.session.execute(
            stmt.order_by(Application.created_at.desc()).limit(limit).offset(offset)
        )
        return list(result.scalars().all())

    async def list_by_job_ids(
        self,
        job_ids: list[uuid.UUID],
        *,
        status_filter: str | None,
        limit: int,
        offset: int,
    ) -> list[Application]:
        if not job_ids:
            return []
        stmt = self._base_query().where(Application.job_id.in_(job_ids))
        if status_filter is not None:
            stmt = stmt.where(Application.status == status_filter)
        result = await self.session.execute(
            stmt.order_by(Application.created_at.desc()).limit(limit).offset(offset)
        )
        return list(result.scalars().all())

    async def update_status(
        self,
        application: Application,
        *,
        status: ApplicationStatus,
        changed_by_user_id: uuid.UUID | None = None,
        changed_by_role: str | None = None,
        reason: str | None = None,
        notes: str | None = None,
    ) -> Application:
        previous_status = application.status
        application.status = status.value
        self._apply_status_timestamps(application, status)
        self._add_status_history_entry(
            application,
            from_status=previous_status,
            to_status=status.value,
            changed_by_user_id=changed_by_user_id,
            changed_by_role=changed_by_role,
            reason=reason,
            notes=notes,
        )
        await self.session.flush()
        return await self.get_by_id(application.id)

    async def update_metadata(
        self,
        application: Application,
        *,
        metadata: dict,
    ) -> Application:
        application.application_metadata = metadata
        await self.session.flush()
        return await self.get_by_id(application.id)

    def _apply_status_timestamps(
        self,
        application: Application,
        status: ApplicationStatus,
    ) -> None:
        changed_at = datetime.now(timezone.utc)
        if status == ApplicationStatus.SCREENING and application.screening_started_at is None:
            application.screening_started_at = changed_at
        elif status == ApplicationStatus.INTERVIEW and application.interview_started_at is None:
            application.interview_started_at = changed_at
        elif status == ApplicationStatus.OFFER and application.offered_at is None:
            application.offered_at = changed_at
        elif status == ApplicationStatus.REJECTED and application.rejected_at is None:
            application.rejected_at = changed_at
        elif status == ApplicationStatus.ACCEPTED and application.accepted_at is None:
            application.accepted_at = changed_at

    def _add_status_history_entry(
        self,
        application: Application,
        *,
        from_status: str | None,
        to_status: str,
        changed_by_user_id: uuid.UUID | None,
        changed_by_role: str | None,
        reason: str | None = None,
        notes: str | None = None,
    ) -> None:
        self.session.add(
            ApplicationStatusHistory(
                application_id=application.id,
                from_status=from_status,
                to_status=to_status,
                changed_by_user_id=changed_by_user_id,
                changed_by_role=changed_by_role,
                reason=reason,
                notes=notes,
            )
        )
