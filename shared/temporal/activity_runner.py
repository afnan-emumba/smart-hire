from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from typing import Any

from temporalio.exceptions import ApplicationError


async def run_temporal_activity(
    *,
    session_factory: Callable[[], Any],
    build_service: Callable[[Any], Any],
    operation: Callable[[Any], Awaitable[Any]],
    non_retryable_errors: tuple[type[Exception], ...],
    clients: Sequence[Any] = (),
    serialize_result: Callable[[Any], Any] | None = None,
) -> Any:
    try:
        async with session_factory() as session:
            service = build_service(session)
            try:
                result = await operation(service)
                await session.commit()
                return serialize_result(result) if serialize_result is not None else result
            except non_retryable_errors as exc:
                await session.rollback()
                raise ApplicationError(str(exc), type=type(exc).__name__, non_retryable=True) from exc
            except Exception:
                await session.rollback()
                raise
    finally:
        for client in clients:
            await client.aclose()
