from __future__ import annotations

import asyncio
import logging

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.events.producer import KafkaEventPublisher
from app.repositories.outbox_repo import OutboxRepository


logger = logging.getLogger(__name__)


class OutboxRelay:
    def __init__(self) -> None:
        self.settings = get_settings()
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
                try:
                    await self.publisher.publish(
                        topic_name=event.topic_name,
                        payload=event.payload,
                        key=str(event.aggregate_id),
                        headers={
                            key: str(value)
                            for key, value in {**event.headers, **event.trace_context}.items()
                            if value is not None
                        },
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
                    continue

                await repository.mark_published(event)
                published_count += 1

            await session.commit()
            return published_count


async def _main() -> None:
    relay = OutboxRelay()
    await relay.run_forever()


if __name__ == "__main__":
    asyncio.run(_main())