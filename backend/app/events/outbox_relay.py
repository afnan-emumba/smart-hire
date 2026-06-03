from __future__ import annotations

import asyncio
import logging

from app.core.config import get_settings
from app.core.logging import bind_log_context, configure_logging, reset_log_context
from app.core.tracing import configure_tracing, start_trace_span
from app.db.session import SessionLocal, engine
from app.events.producer import KafkaEventPublisher
from app.repositories.outbox_repo import OutboxRepository


settings = get_settings()
configure_logging(settings)
configure_tracing(settings, sqlalchemy_engine=engine)
logger = logging.getLogger(__name__)


class OutboxRelay:
    def __init__(self) -> None:
        self.settings = settings
        self.publisher = KafkaEventPublisher(self.settings)

    async def run_forever(self) -> None:
        await self.publisher.start()
        try:
            while True:
                published_count = await self.publish_pending_batch()
                if published_count == 0:
                    await asyncio.sleep(self.settings.event_relay_poll_interval_seconds)
        finally:
            await self.publisher.close()

    async def publish_pending_batch(self) -> int:
        async with SessionLocal() as session:
            repository = OutboxRepository(session)
            events = await repository.claim_pending(limit=self.settings.event_relay_batch_size)
            if not events:
                await session.commit()
                return 0

            published_count = 0
            for event in events:
                merged_headers = {
                    key: str(value)
                    for key, value in {**event.headers, **event.trace_context}.items()
                    if value is not None
                }
                tokens = bind_log_context(
                    user_id=merged_headers.get("user_id"),
                    workflow_id=merged_headers.get("workflow_id"),
                    correlation_id=merged_headers.get("correlation_id"),
                )
                try:
                    with start_trace_span(
                        "outbox.publish",
                        headers=merged_headers,
                        attributes={
                            "messaging.system": "kafka",
                            "messaging.destination.name": event.topic_name,
                            "messaging.operation": "publish",
                            "smarthire.event_type": event.event_type,
                            "smarthire.event_id": str(event.id),
                        },
                    ):
                        await self.publisher.publish(
                            topic_name=event.topic_name,
                            payload=event.payload,
                            key=str(event.aggregate_id),
                            headers=merged_headers,
                            event_type=event.event_type,
                        )
                except Exception as exc:
                    if event.retry_count + 1 >= self.settings.event_relay_max_retries:
                        await repository.mark_failed(event, error_message=str(exc))
                        logger.exception(
                            "Outbox publish permanently failed",
                            extra={"event_id": str(event.id), "topic_name": event.topic_name},
                        )
                    else:
                        await repository.reset_claim(event, error_message=str(exc))
                        logger.warning(
                            "Outbox publish failed; event returned to pending",
                            extra={"event_id": str(event.id), "topic_name": event.topic_name},
                        )
                        await session.commit()
                        await asyncio.sleep(self.settings.event_relay_retry_backoff_seconds)
                    reset_log_context(tokens)
                    continue

                await repository.mark_published(event)
                published_count += 1
                reset_log_context(tokens)

            await session.commit()
            return published_count


async def _main() -> None:
    relay = OutboxRelay()
    await relay.run_forever()


if __name__ == "__main__":
    asyncio.run(_main())