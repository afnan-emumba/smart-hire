from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.application_states import ApplicationStatus
from app.db.models import Application, ApplicationStatusHistory, CandidateResume, Job
from app.schemas.application import ApplicationCreate


class ApplicationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _base_query():
        return select(Application).options(selectinload(Application.resume))

    async def create(
        self,
        application_create: ApplicationCreate,
        *,
        candidate_id: uuid.UUID,
        status: ApplicationStatus,
        eligibility_result: dict[str, Any] | None = None,
    ) -> Application:
        application = Application(
            **application_create.model_dump(),
            candidate_id=candidate_id,
            status=status.value,
            eligibility_result=eligibility_result,
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

    async def list_all(
        self,
        *,
        status_filter: str | None,
        limit: int,
        offset: int,
    ) -> list[Application]:
        stmt = self._base_query()
        if status_filter is not None:
            stmt = stmt.where(Application.status == status_filter)
        result = await self.session.execute(
            stmt.order_by(Application.created_at.desc()).limit(limit).offset(offset)
        )
        return list(result.scalars().all())

    async def list_by_recruiter(
        self,
        recruiter_id: uuid.UUID,
        *,
        status_filter: str | None,
        limit: int,
        offset: int,
    ) -> list[Application]:
        stmt = (
            self._base_query()
            .join(Job, Job.id == Application.job_id)
            .where(Job.recruiter_id == recruiter_id)
        )
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

    async def set_workflow_tracking(
        self,
        application: Application,
        *,
        workflow_id: str | None = None,
        workflow_initialized_at: datetime | None = None,
        workflow_failed_at: datetime | None = None,
        workflow_error: str | None = None,
    ) -> Application:
        if workflow_id is not None:
            application.workflow_id = workflow_id
        if workflow_initialized_at is not None:
            application.workflow_initialized_at = workflow_initialized_at
        if workflow_failed_at is not None:
            application.workflow_failed_at = workflow_failed_at
        if workflow_error is not None or workflow_failed_at is not None:
            application.workflow_error = workflow_error

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

    async def update_metadata_section(
        self,
        application: Application,
        *,
        section_name: str,
        section_value: dict[str, Any],
    ) -> Application:
        result = await self.session.execute(
            select(Application)
            .where(Application.id == application.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        locked_application = result.scalar_one()
        await self.session.refresh(locked_application, attribute_names=["application_metadata"])
        metadata = dict(locked_application.application_metadata)
        metadata[section_name] = section_value
        locked_application.application_metadata = metadata
        await self.session.flush()
        return await self.get_by_id(application.id)

    async def update_resume_parsing(
        self,
        application: Application,
        *,
        metadata: dict,
    ) -> Application:
        application.application_metadata = metadata
        await self.session.flush()
        return await self.get_by_id(application.id)

    async def attach_resume(
        self,
        application: Application,
        *,
        resume: CandidateResume,
    ) -> Application:
        application.resume_id = resume.id
        application.resume = resume

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