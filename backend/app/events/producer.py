from __future__ import annotations

import asyncio
import json
import logging
from typing import Any
from urllib import error, request

from aiokafka import AIOKafkaProducer
from aiokafka.admin import AIOKafkaAdminClient, NewTopic
from aiokafka.errors import TopicAlreadyExistsError

from app.core.config import Settings, get_settings
from app.core.tracing import inject_trace_headers, start_trace_span
from app.events.schemas import EVENT_CONTRACTS, get_event_contract


logger = logging.getLogger(__name__)


class SchemaRegistryClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    async def register_json_schema(self, *, subject: str, schema: dict[str, Any]) -> None:
        payload = json.dumps(
            {
                "schemaType": "JSON",
                "schema": json.dumps(schema, sort_keys=True, separators=(",", ":")),
            }
        ).encode("utf-8")
        await asyncio.to_thread(self._post_schema, subject, payload)

    def _post_schema(self, subject: str, payload: bytes) -> None:
        schema_request = request.Request(
            url=f"{self.base_url}/subjects/{subject}/versions",
            data=payload,
            method="POST",
            headers={"Content-Type": "application/vnd.schemaregistry.v1+json"},
        )
        try:
            with request.urlopen(schema_request, timeout=10) as response:
                response.read()
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")
            if exc.code == 409:
                logger.warning(
                    "Schema registry kept existing schema for subject %s after incompatibility response: %s",
                    subject,
                    body,
                )
                return
            raise RuntimeError(
                f"Schema registry request failed for subject '{subject}': {exc.code} {body}"
            ) from exc
        except error.URLError as exc:
            raise RuntimeError(
                f"Schema registry is unavailable: {exc.reason}") from exc


class KafkaEventPublisher:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._producer: AIOKafkaProducer | None = None
        self._registry = SchemaRegistryClient(settings.schema_registry_url)
        self._registered_subjects: set[str] = set()
        self._startup_lock = asyncio.Lock()

    async def start(self) -> None:
        async with self._startup_lock:
            if self._producer is not None:
                return

            await self.ensure_topics()
            self._producer = AIOKafkaProducer(
                bootstrap_servers=self.settings.kafka_bootstrap_servers,
                value_serializer=lambda value: json.dumps(
                    value,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8"),
                key_serializer=lambda key: key.encode(
                    "utf-8") if key is not None else None,
            )
            await self._producer.start()
            await self.ensure_registered_contracts()

    async def ensure_topics(self) -> None:
        admin_client = AIOKafkaAdminClient(
            bootstrap_servers=self.settings.kafka_bootstrap_servers,
        )
        await admin_client.start()
        try:
            topics = [
                NewTopic(
                    name=contract.topic_name(),
                    num_partitions=1,
                    replication_factor=1,
                )
                for contract in EVENT_CONTRACTS
            ]
            try:
                await admin_client.create_topics(topics)
            except TopicAlreadyExistsError:
                pass
        finally:
            await admin_client.close()

    async def close(self) -> None:
        if self._producer is None:
            return
        await self._producer.stop()
        self._producer = None

    async def ensure_registered_contracts(self) -> None:
        for contract in EVENT_CONTRACTS:
            await self.ensure_event_schema(contract.event_type())

    async def ensure_event_schema(self, event_type: str) -> None:
        contract = get_event_contract(event_type)
        subject = contract.schema_subject()
        if subject in self._registered_subjects:
            return
        await self._registry.register_json_schema(
            subject=subject,
            schema=contract.json_schema_payload(),
        )
        self._registered_subjects.add(subject)

    async def publish(
        self,
        *,
        topic_name: str,
        payload: dict[str, Any],
        key: str,
        headers: dict[str, str] | None = None,
        event_type: str,
    ) -> None:
        if self._producer is None:
            raise RuntimeError("Kafka producer has not been started")

        await self.ensure_event_schema(event_type)
        with start_trace_span(
            "kafka.publish",
            headers=headers,
            attributes={
                "messaging.system": "kafka",
                "messaging.destination.name": topic_name,
                "messaging.operation": "publish",
                "smarthire.event_type": event_type,
            },
        ):
            propagated_headers = inject_trace_headers(headers)
            kafka_headers = [
                (header_key, header_value.encode("utf-8"))
                for header_key, header_value in propagated_headers.items()
            ]
            await self._producer.send_and_wait(
                topic_name,
                payload,
                key=key,
                headers=kafka_headers,
            )


_event_publisher: KafkaEventPublisher | None = None


async def start_event_publisher(settings: Settings | None = None) -> KafkaEventPublisher:
    global _event_publisher

    if _event_publisher is None:
        _event_publisher = KafkaEventPublisher(settings or get_settings())
    await _event_publisher.start()
    return _event_publisher


def get_event_publisher() -> KafkaEventPublisher:
    if _event_publisher is None:
        raise RuntimeError("Kafka event publisher has not been started")
    return _event_publisher


async def stop_event_publisher() -> None:
    global _event_publisher

    if _event_publisher is None:
        return
    await _event_publisher.close()
    _event_publisher = None
