from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from datetime import timedelta
from typing import Any

from temporalio.client import Client
from temporalio.exceptions import WorkflowAlreadyStartedError

from exceptions.http_exceptions import ServiceUnavailableError


async def start_workflow_with_retryable_error_mapping(
    *,
    client_factory: Callable[[], Awaitable[Client]],
    workflow: Any,
    workflow_input: Any,
    workflow_id: str,
    task_queue: str,
    execution_timeout: timedelta,
    logger: logging.Logger,
    context: dict[str, str],
    conflict_log_message: str,
    failure_log_message: str,
    unavailable_message: str,
) -> None:
    try:
        client = await client_factory()
        await client.start_workflow(
            workflow,
            workflow_input,
            id=workflow_id,
            task_queue=task_queue,
            execution_timeout=execution_timeout,
        )
    except WorkflowAlreadyStartedError:
        logger.info(conflict_log_message, extra=context)
    except Exception as exc:
        logger.exception(failure_log_message, extra=context)
        raise ServiceUnavailableError(unavailable_message) from exc


async def start_workflow_best_effort(
    *,
    client_factory: Callable[[], Awaitable[Client]],
    workflow: Any,
    workflow_input: Any,
    workflow_id: str,
    task_queue: str,
    execution_timeout: timedelta,
    logger: logging.Logger,
    context: dict[str, str],
    conflict_log_message: str,
    failure_log_message: str,
) -> str | None:
    """Start a workflow without letting a Temporal outage fail the caller.

    Used for non-critical side effects (notification delivery) where the
    triggering write has already been committed and must not be rolled back
    just because the workflow could not be scheduled.
    """
    try:
        client = await client_factory()
        await client.start_workflow(
            workflow,
            workflow_input,
            id=workflow_id,
            task_queue=task_queue,
            execution_timeout=execution_timeout,
        )
        return workflow_id
    except WorkflowAlreadyStartedError:
        logger.info(conflict_log_message, extra=context)
        return workflow_id
    except Exception:
        logger.exception(failure_log_message, extra=context)
        return None
