from __future__ import annotations

import logging
from contextvars import ContextVar, Token

from opentelemetry import trace
from pythonjsonlogger.json import JsonFormatter

from app.core.config import Settings


_logging_configured = False
_user_id_var: ContextVar[str | None] = ContextVar("user_id", default=None)
_workflow_id_var: ContextVar[str | None] = ContextVar("workflow_id", default=None)
_correlation_id_var: ContextVar[str | None] = ContextVar("correlation_id", default=None)


class _StructuredContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        span_context = trace.get_current_span().get_span_context()
        record.trace_id = format(span_context.trace_id, "032x") if span_context.is_valid else None
        record.span_id = format(span_context.span_id, "016x") if span_context.is_valid else None
        record.user_id = getattr(record, "user_id", _user_id_var.get())
        record.workflow_id = getattr(record, "workflow_id", _workflow_id_var.get())
        record.correlation_id = getattr(record, "correlation_id", _correlation_id_var.get())
        record.component = getattr(record, "component", record.name)
        return True


def configure_logging(settings: Settings) -> None:
    global _logging_configured

    if _logging_configured:
        logging.getLogger().setLevel(settings.log_level.upper())
        return

    handler = logging.StreamHandler()
    handler.addFilter(_StructuredContextFilter())
    if settings.log_json:
        formatter = JsonFormatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s %(trace_id)s %(span_id)s %(user_id)s %(workflow_id)s %(correlation_id)s %(component)s"
        )
    else:
        formatter = logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s"
        )
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(settings.log_level.upper())
    _logging_configured = True


def bind_log_context(
    *,
    user_id: str | None = None,
    workflow_id: str | None = None,
    correlation_id: str | None = None,
) -> dict[str, Token[str | None]]:
    return {
        "user_id": _user_id_var.set(user_id),
        "workflow_id": _workflow_id_var.set(workflow_id),
        "correlation_id": _correlation_id_var.set(correlation_id),
    }


def reset_log_context(tokens: dict[str, Token[str | None]]) -> None:
    _user_id_var.reset(tokens["user_id"])
    _workflow_id_var.reset(tokens["workflow_id"])
    _correlation_id_var.reset(tokens["correlation_id"])