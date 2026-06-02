from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.events.topics import (
    APPLICATION_RECEIVED_EVENT_TYPE,
    APPLICATION_RECEIVED_TOPIC,
    JOB_PUBLISHED_EVENT_TYPE,
    JOB_PUBLISHED_TOPIC,
    schema_subject_for_topic,
)


class EventContext(BaseModel):
    model_config = ConfigDict(extra="ignore")

    trace_id: str | None = None
    span_id: str | None = None
    traceparent: str | None = None
    tracestate: str | None = None
    correlation_id: str | None = None
    user_id: str | None = None


class BaseEvent(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    event_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    schema_version: str = "v1"
    aggregate_id: uuid.UUID
    workflow_id: str | None = None
    context: EventContext = Field(default_factory=EventContext)

    @classmethod
    def event_type(cls) -> str:
        raise NotImplementedError

    @classmethod
    def topic_name(cls) -> str:
        raise NotImplementedError

    @classmethod
    def schema_subject(cls) -> str:
        return schema_subject_for_topic(cls.topic_name())

    def payload(self) -> dict[str, Any]:
        return self.model_dump(mode="json", by_alias=True)

    def headers(self) -> dict[str, str]:
        headers: dict[str, str] = {
            "event_type": self.event_type(),
            "schema_version": self.schema_version,
            "event_id": str(self.event_id),
        }
        if self.context.trace_id:
            headers["trace_id"] = self.context.trace_id
        if self.context.span_id:
            headers["span_id"] = self.context.span_id
        if self.context.traceparent:
            headers["traceparent"] = self.context.traceparent
        if self.context.tracestate:
            headers["tracestate"] = self.context.tracestate
        if self.context.correlation_id:
            headers["correlation_id"] = self.context.correlation_id
        if self.workflow_id:
            headers["workflow_id"] = self.workflow_id
        return headers

    def trace_context(self) -> dict[str, str]:
        trace_context: dict[str, str] = {}
        if self.context.trace_id:
            trace_context["trace_id"] = self.context.trace_id
        if self.context.span_id:
            trace_context["span_id"] = self.context.span_id
        if self.context.traceparent:
            trace_context["traceparent"] = self.context.traceparent
        if self.context.tracestate:
            trace_context["tracestate"] = self.context.tracestate
        if self.context.correlation_id:
            trace_context["correlation_id"] = self.context.correlation_id
        if self.context.user_id:
            trace_context["user_id"] = self.context.user_id
        return trace_context

    @classmethod
    def json_schema_payload(cls) -> dict[str, Any]:
        return cls.model_json_schema()


class JobPublishedEvent(BaseEvent):
    job_id: uuid.UUID
    recruiter_id: uuid.UUID
    status: str

    @classmethod
    def event_type(cls) -> str:
        return JOB_PUBLISHED_EVENT_TYPE

    @classmethod
    def topic_name(cls) -> str:
        return JOB_PUBLISHED_TOPIC


class ApplicationReceivedEvent(BaseEvent):
    application_id: uuid.UUID
    job_id: uuid.UUID
    candidate_id: uuid.UUID
    status: str

    @classmethod
    def event_type(cls) -> str:
        return APPLICATION_RECEIVED_EVENT_TYPE

    @classmethod
    def topic_name(cls) -> str:
        return APPLICATION_RECEIVED_TOPIC


EVENT_CONTRACTS: tuple[type[BaseEvent], ...] = (
    JobPublishedEvent,
    ApplicationReceivedEvent,
)

EVENT_CONTRACTS_BY_TYPE: dict[str, type[BaseEvent]] = {
    contract.event_type(): contract for contract in EVENT_CONTRACTS
}


def get_event_contract(event_type: str) -> type[BaseEvent]:
    try:
        return EVENT_CONTRACTS_BY_TYPE[event_type]
    except KeyError as exc:
        raise ValueError(f"Unsupported event type: {event_type}") from exc