from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from temporalio.client import Client
from temporalio.exceptions import WorkflowAlreadyStartedError

from exceptions.http_exceptions import ServiceUnavailableError


async def start_workflow_with_retryable_error_mapping(
    *,
    client: Client,
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
