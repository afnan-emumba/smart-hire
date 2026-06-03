from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any, Mapping

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import EventProcessingRecord


class EventProcessingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_event_and_handler(
        self,
        *,
        event_id: uuid.UUID,
        handler_name: str,
        for_update: bool = False,
    ) -> EventProcessingRecord | None:
        stmt = select(EventProcessingRecord).where(
            EventProcessingRecord.event_id == event_id,
            EventProcessingRecord.handler_name == handler_name,
        )
        if for_update:
            stmt = stmt.with_for_update()

        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_or_create(
        self,
        *,
        event_id: uuid.UUID,
        handler_name: str,
        event_type: str,
        topic_name: str,
        aggregate_id: uuid.UUID,
        schema_version: str = "v1",
        metadata: Mapping[str, Any] | None = None,
    ) -> tuple[EventProcessingRecord, bool]:
        for attempt in range(3):
            stmt = (
                insert(EventProcessingRecord)
                .values(
                    event_id=event_id,
                    handler_name=handler_name,
                    event_type=event_type,
                    topic_name=topic_name,
                    aggregate_id=aggregate_id,
                    schema_version=schema_version,
                    processing_metadata=dict(metadata or {}),
                )
                .on_conflict_do_nothing(
                    index_elements=[
                        EventProcessingRecord.event_id,
                        EventProcessingRecord.handler_name,
                    ]
                )
                .returning(EventProcessingRecord.id)
            )
            inserted = (await self.session.execute(stmt)).scalar_one_or_none()

            record = await self.get_by_event_and_handler(
                event_id=event_id,
                handler_name=handler_name,
                for_update=True,
            )
            if record is not None:
                return record, inserted is not None

            if attempt < 2:
                await asyncio.sleep(0.05 * (attempt + 1))

        raise RuntimeError(
            "Failed to get or create event processing record after concurrent insert attempts"
        )

    async def mark_queued(
        self,
        record: EventProcessingRecord,
        *,
        metadata: Mapping[str, Any] | None = None,
    ) -> EventProcessingRecord:
        record.status = "queued"
        record.claimed_at = datetime.now(timezone.utc)
        record.completed_at = None
        record.last_error = None
        if metadata is not None:
            updated_metadata = dict(record.processing_metadata)
            updated_metadata.update(dict(metadata))
            record.processing_metadata = updated_metadata
        await self.session.flush()
        await self.session.refresh(record)
        return record

    async def claim_for_processing(
        self,
        *,
        event_id: uuid.UUID,
        handler_name: str,
    ) -> tuple[EventProcessingRecord | None, bool]:
        record = await self.get_by_event_and_handler(
            event_id=event_id,
            handler_name=handler_name,
            for_update=True,
        )
        if record is None:
            return None, False
        if record.status in {"processing", "completed"}:
            return record, False

        record.status = "processing"
        record.claimed_at = datetime.now(timezone.utc)
        record.completed_at = None
        record.last_error = None
        await self.session.flush()
        await self.session.refresh(record)
        return record, True

    async def mark_completed(
        self,
        record: EventProcessingRecord,
        *,
        metadata: Mapping[str, Any] | None = None,
    ) -> EventProcessingRecord:
        record.status = "completed"
        record.completed_at = datetime.now(timezone.utc)
        record.last_error = None
        if metadata is not None:
            updated_metadata = dict(record.processing_metadata)
            updated_metadata.update(dict(metadata))
            record.processing_metadata = updated_metadata
        await self.session.flush()
        await self.session.refresh(record)
        return record

    async def mark_failed(
        self,
        record: EventProcessingRecord,
        *,
        error_message: str,
        metadata: Mapping[str, Any] | None = None,
    ) -> EventProcessingRecord:
        record.status = "failed"
        record.retry_count += 1
        record.last_error = error_message
        if metadata is not None:
            updated_metadata = dict(record.processing_metadata)
            updated_metadata.update(dict(metadata))
            record.processing_metadata = updated_metadata
        await self.session.flush()
        await self.session.refresh(record)
        return record