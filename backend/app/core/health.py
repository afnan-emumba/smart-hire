from __future__ import annotations

import asyncio
import logging
from urllib import error, request
from urllib.parse import urlparse

from redis import asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import ping_database


logger = logging.getLogger(__name__)
settings = get_settings()


async def check_database(session: AsyncSession) -> dict[str, str]:
    try:
        database_ok = await ping_database(session)
    except Exception:
        logger.exception("Database health check failed")
        database_ok = False

    return {"status": "up" if database_ok else "down"}


async def check_tcp_dependency(host: str, port: int, *, dependency_name: str) -> dict[str, str]:
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=settings.healthcheck_timeout_seconds,
        )
        writer.close()
        await writer.wait_closed()
        return {"status": "up"}
    except Exception as exc:
        logger.warning("%s health check failed",
                       dependency_name, extra={"error": str(exc)})
        return {"status": "down", "error": str(exc)}


def perform_http_healthcheck(schema_request: request.Request) -> None:
    try:
        with request.urlopen(schema_request, timeout=settings.healthcheck_timeout_seconds) as response:
            response.read()
    except error.URLError as exc:
        raise RuntimeError(str(exc.reason)) from exc


async def check_schema_registry() -> dict[str, str]:
    schema_request = request.Request(
        url=f"{settings.schema_registry_url.rstrip('/')}/subjects",
        method="GET",
    )
    try:
        await asyncio.to_thread(perform_http_healthcheck, schema_request)
        return {"status": "up"}
    except Exception as exc:
        logger.warning("Schema registry health check failed",
                       extra={"error": str(exc)})
        return {"status": "down", "error": str(exc)}


async def check_redis() -> dict[str, str]:
    client = redis.from_url(settings.redis_url)
    try:
        is_ok = await asyncio.wait_for(client.ping(), timeout=settings.healthcheck_timeout_seconds)
        return {"status": "up" if is_ok else "down"}
    except Exception as exc:
        logger.warning("Redis health check failed", extra={"error": str(exc)})
        return {"status": "down", "error": str(exc)}
    finally:
        await client.aclose()


def parse_host_port(value: str, *, default_port: int) -> tuple[str, int]:
    if "://" in value:
        parsed = urlparse(value)
        if parsed.hostname is None:
            raise RuntimeError(f"Invalid endpoint: {value}")
        return parsed.hostname, parsed.port or default_port

    host, raw_port = value.rsplit(":", 1)
    return host, int(raw_port)


async def collect_dependency_results(session: AsyncSession) -> dict[str, dict[str, str]]:
    kafka_host, kafka_port = parse_host_port(
        settings.kafka_bootstrap_servers.split(",", maxsplit=1)[0],
        default_port=9092,
    )
    rabbitmq_host, rabbitmq_port = parse_host_port(
        settings.rabbitmq_url, default_port=5672)
    temporal_host, temporal_port = parse_host_port(
        settings.temporal_address, default_port=7233)

    return {
        "database": await check_database(session),
        "temporal": await check_tcp_dependency(temporal_host, temporal_port, dependency_name="Temporal"),
        "kafka": await check_tcp_dependency(kafka_host, kafka_port, dependency_name="Kafka"),
        "schema_registry": await check_schema_registry(),
        "rabbitmq": await check_tcp_dependency(rabbitmq_host, rabbitmq_port, dependency_name="RabbitMQ"),
        "redis": await check_redis(),
    }
