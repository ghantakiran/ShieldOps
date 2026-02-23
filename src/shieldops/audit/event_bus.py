"""Structured audit event bus — centralized publish/subscribe for audit events.

Replaces scattered audit logging with a unified event-driven architecture.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable
from uuid import uuid4

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


class AuditCategory(StrEnum):
    AGENT_ACTION = "agent_action"
    REMEDIATION = "remediation"
    POLICY_DECISION = "policy_decision"
    AUTH = "auth"
    CONFIG_CHANGE = "config_change"
    DATA_ACCESS = "data_access"
    SECURITY = "security"


class AuditOutcome(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"
    DENIED = "denied"
    ERROR = "error"


class AuditEvent(BaseModel):
    """A structured audit event."""

    id: str = Field(default_factory=lambda: f"evt-{uuid4().hex[:12]}")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    actor: str = "system"
    action: str
    resource: str = ""
    category: AuditCategory = AuditCategory.AGENT_ACTION
    outcome: AuditOutcome = AuditOutcome.SUCCESS
    metadata: dict[str, Any] = Field(default_factory=dict)
    environment: str = ""
    correlation_id: str = ""


class AuditSummary(BaseModel):
    """Summary of audit events by category and actor."""

    total_events: int = 0
    by_category: dict[str, int] = Field(default_factory=dict)
    by_actor: dict[str, int] = Field(default_factory=dict)
    by_outcome: dict[str, int] = Field(default_factory=dict)


@runtime_checkable
class AuditSubscriber(Protocol):
    """Protocol for audit event handlers."""

    async def handle(self, event: AuditEvent) -> None: ...


class LogSubscriber:
    """Writes audit events to structlog."""

    async def handle(self, event: AuditEvent) -> None:
        logger.info(
            "audit_event",
            event_id=event.id,
            actor=event.actor,
            action=event.action,
            resource=event.resource,
            category=event.category,
            outcome=event.outcome,
        )


class StoreSubscriber:
    """Stores audit events in-memory for querying."""

    def __init__(self, max_events: int = 50_000) -> None:
        self._events: list[AuditEvent] = []
        self._max_events = max_events

    async def handle(self, event: AuditEvent) -> None:
        self._events.append(event)
        if len(self._events) > self._max_events:
            self._events[:] = self._events[-self._max_events :]

    @property
    def events(self) -> list[AuditEvent]:
        return list(self._events)

    def get_event(self, event_id: str) -> AuditEvent | None:
        for e in self._events:
            if e.id == event_id:
                return e
        return None

    def query(
        self,
        category: str | None = None,
        actor: str | None = None,
        action: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AuditEvent]:
        results = self._events
        if category:
            results = [e for e in results if e.category == category]
        if actor:
            results = [e for e in results if e.actor == actor]
        if action:
            results = [e for e in results if e.action == action]
        # Reverse to get most recent first
        results = list(reversed(results))
        return results[offset : offset + limit]

    def summary(self) -> AuditSummary:
        by_cat: dict[str, int] = {}
        by_actor: dict[str, int] = {}
        by_outcome: dict[str, int] = {}
        for e in self._events:
            by_cat[e.category] = by_cat.get(e.category, 0) + 1
            by_actor[e.actor] = by_actor.get(e.actor, 0) + 1
            by_outcome[e.outcome] = by_outcome.get(e.outcome, 0) + 1
        return AuditSummary(
            total_events=len(self._events),
            by_category=by_cat,
            by_actor=by_actor,
            by_outcome=by_outcome,
        )


class AuditEventBus:
    """Centralized publish/subscribe for audit events.

    Usage::

        bus = AuditEventBus()
        bus.subscribe(LogSubscriber())
        bus.subscribe(StoreSubscriber())
        await bus.publish(AuditEvent(action="restart_service", ...))
    """

    def __init__(self) -> None:
        self._subscribers: list[AuditSubscriber] = []
        self._store = StoreSubscriber()
        # Always include internal store
        self._subscribers.append(self._store)
        self._subscribers.append(LogSubscriber())

    def subscribe(self, subscriber: AuditSubscriber) -> None:
        self._subscribers.append(subscriber)

    async def publish(self, event: AuditEvent) -> None:
        """Publish an event to all subscribers."""
        for sub in self._subscribers:
            try:
                await sub.handle(event)
            except Exception as e:
                logger.warning(
                    "audit_subscriber_error",
                    subscriber=type(sub).__name__,
                    error=str(e),
                )

    def query_events(
        self,
        category: str | None = None,
        actor: str | None = None,
        action: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AuditEvent]:
        return self._store.query(
            category=category,
            actor=actor,
            action=action,
            limit=limit,
            offset=offset,
        )

    def get_event(self, event_id: str) -> AuditEvent | None:
        return self._store.get_event(event_id)

    def summary(self) -> AuditSummary:
        return self._store.summary()

    @property
    def event_count(self) -> int:
        return len(self._store.events)
