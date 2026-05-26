from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Mapping

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import OutboxEvent


class OutboxRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _pending_query() -> Select[tuple[OutboxEvent]]:
        return (
            select(OutboxEvent)
            .where(OutboxEvent.publish_status == "pending")
            .order_by(OutboxEvent.created_at.asc())
        )

    async def create_event(
        self,
        *,
        aggregate_type: str,
        aggregate_id: uuid.UUID,
        topic_name: str,
        event_type: str,
        payload: Mapping[str, Any],
        schema_version: str = "v1",
        headers: Mapping[str, Any] | None = None,
        trace_context: Mapping[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> OutboxEvent:
        event = OutboxEvent(
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            topic_name=topic_name,
            event_type=event_type,
            schema_version=schema_version,
            idempotency_key=idempotency_key,
            payload=dict(payload),
            headers=dict(headers or {}),
            trace_context=dict(trace_context or {}),
        )
        self.session.add(event)
        await self.session.flush()
        await self.session.refresh(event)
        return event

    async def list_pending(self, *, limit: int = 100) -> list[OutboxEvent]:
        result = await self.session.execute(self._pending_query().limit(limit))
        return list(result.scalars().all())

    async def claim_pending(self, *, limit: int = 100) -> list[OutboxEvent]:
        result = await self.session.execute(
            self._pending_query().limit(limit).with_for_update(skip_locked=True)
        )
        events = list(result.scalars().all())
        for event in events:
            event.publish_status = "claimed"
            event.last_error = None
        await self.session.flush()
        return events

    async def mark_published(self, event: OutboxEvent) -> OutboxEvent:
        event.publish_status = "published"
        event.published_at = datetime.now(timezone.utc)
        event.last_error = None
        await self.session.flush()
        await self.session.refresh(event)
        return event

    async def mark_failed(self, event: OutboxEvent, *, error_message: str) -> OutboxEvent:
        event.publish_status = "failed"
        event.retry_count += 1
        event.last_error = error_message
        await self.session.flush()
        await self.session.refresh(event)
        return event

    async def reset_claim(self, event: OutboxEvent, *, error_message: str | None = None) -> OutboxEvent:
        event.publish_status = "pending"
        if error_message is not None:
            event.retry_count += 1
            event.last_error = error_message
        await self.session.flush()
        await self.session.refresh(event)
        return event
