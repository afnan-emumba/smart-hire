from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any

from aiokafka import AIOKafkaConsumer

from app.celery_app import celery_app
from app.core.config import get_settings
from app.core.logging import bind_log_context, configure_logging, reset_log_context
from app.core.tracing import configure_tracing, start_trace_span
from app.db.session import SessionLocal, engine
from app.events.schemas import get_event_contract
from app.events.topics import APPLICATION_RECEIVED_EVENT_TYPE, JOB_PUBLISHED_EVENT_TYPE
from app.repositories.event_processing_repo import EventProcessingRepository
from app.tasks import (
    APPLICATION_ANALYTICS_TASK,
    APPLICATION_RECEIVED_NOTIFICATION_TASK,
    APPLICATION_SCORING_TASK,
    JOB_ANALYTICS_TASK,
)


settings = get_settings()
configure_logging(settings)
configure_tracing(settings, sqlalchemy_engine=engine)
logger = logging.getLogger(__name__)


EVENT_TASK_MAP: dict[str, tuple[str, ...]] = {
    APPLICATION_RECEIVED_EVENT_TYPE: (
        APPLICATION_SCORING_TASK,
        APPLICATION_RECEIVED_NOTIFICATION_TASK,
        APPLICATION_ANALYTICS_TASK,
    ),
    JOB_PUBLISHED_EVENT_TYPE: (
        JOB_ANALYTICS_TASK,
    ),
}


class EventConsumer:
    def __init__(self) -> None:
        self.settings = settings
        self.consumer = AIOKafkaConsumer(
            self.settings.kafka_job_published_topic,
            self.settings.kafka_application_received_topic,
            bootstrap_servers=self.settings.kafka_bootstrap_servers,
            group_id=self.settings.kafka_consumer_group_id,
            enable_auto_commit=False,
            auto_offset_reset="earliest",
            value_deserializer=lambda value: json.loads(value.decode("utf-8")),
        )

    async def run_forever(self) -> None:
        await self.consumer.start()
        try:
            while True:
                records = await self.consumer.getmany(timeout_ms=self.settings.kafka_consumer_poll_timeout_ms)
                if not records:
                    await asyncio.sleep(0.1)
                    continue

                for topic_partition, messages in records.items():
                    for message in messages:
                        await self.process_message(message.topic, message.value, message.headers)
                    await self.consumer.commit({topic_partition: messages[-1].offset + 1})
        finally:
            await self.consumer.stop()

    async def process_message(
        self,
        topic_name: str,
        payload: dict[str, Any],
        raw_headers: list[tuple[str, bytes]] | None,
    ) -> None:
        headers = self._decode_headers(raw_headers)
        event_type = headers.get("event_type")
        if event_type is None:
            raise RuntimeError(f"Kafka message on topic '{topic_name}' is missing event_type header")

        tokens = bind_log_context(
            user_id=headers.get("user_id"),
            workflow_id=headers.get("workflow_id"),
            correlation_id=headers.get("correlation_id"),
        )
        try:
            with start_trace_span(
                "kafka.consume",
                headers=headers,
                attributes={
                    "messaging.system": "kafka",
                    "messaging.destination.name": topic_name,
                    "messaging.operation": "process",
                    "smarthire.event_type": event_type,
                },
            ):
                contract = get_event_contract(event_type)
                event = contract.model_validate(payload)
                header_schema_version = headers.get("schema_version")
                if header_schema_version is not None and header_schema_version != event.schema_version:
                    raise RuntimeError(
                        "Kafka message schema version header does not match the validated payload"
                    )
                handler_names = EVENT_TASK_MAP.get(event_type, ())
                if not handler_names:
                    logger.info("No task handlers registered for event type", extra={"event_type": event_type})
                    return

                async with SessionLocal() as session:
                    processing_repo = EventProcessingRepository(session)
                    for handler_name in handler_names:
                        record, _ = await processing_repo.get_or_create(
                            event_id=event.event_id,
                            handler_name=handler_name,
                            event_type=event_type,
                            topic_name=topic_name,
                            aggregate_id=event.aggregate_id,
                            schema_version=event.schema_version,
                            metadata={
                                "consumer_group_id": self.settings.kafka_consumer_group_id,
                            },
                        )
                        if self._should_skip_dispatch(record):
                            continue

                        try:
                            async_result = celery_app.send_task(
                                handler_name,
                                kwargs={
                                    "payload": event.payload(),
                                    "headers": headers,
                                },
                            )
                        except Exception as exc:
                            await processing_repo.mark_failed(
                                record,
                                error_message=str(exc),
                                metadata={
                                    "dispatch_failed_at": datetime.now(timezone.utc).isoformat(),
                                },
                            )
                            await session.commit()
                            raise

                        await processing_repo.mark_queued(
                            record,
                            metadata={
                                "celery_task_id": async_result.id,
                                "enqueued_at": datetime.now(timezone.utc).isoformat(),
                            },
                        )

                    await session.commit()
        finally:
            reset_log_context(tokens)

    @staticmethod
    def _decode_headers(raw_headers: list[tuple[str, bytes]] | None) -> dict[str, str]:
        decoded_headers: dict[str, str] = {}
        for key, value in raw_headers or []:
            decoded_headers[key] = value.decode("utf-8")
        return decoded_headers

    @staticmethod
    def _should_skip_dispatch(record) -> bool:
        if record.status in {"queued", "processing", "completed"}:
            return True
        if record.status == "failed" and record.processing_metadata.get("celery_task_id"):
            return True
        return False


async def _main() -> None:
    consumer = EventConsumer()
    await consumer.run_forever()


if __name__ == "__main__":
    asyncio.run(_main())