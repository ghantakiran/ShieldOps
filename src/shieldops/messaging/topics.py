"""Kafka topic constants and event envelope schema."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

from pydantic import BaseModel, Field

# ── Topic constants ──────────────────────────────────────────────────────────

EVENTS_TOPIC = "shieldops.events"
AGENT_RESULTS_TOPIC = "shieldops.agent.results"
AUDIT_TOPIC = "shieldops.audit"

ALL_TOPICS: list[str] = [EVENTS_TOPIC, AGENT_RESULTS_TOPIC, AUDIT_TOPIC]


# ── Event envelope ───────────────────────────────────────────────────────────


class EventEnvelope(BaseModel):
    """Canonical wrapper for every message on the ShieldOps event bus.

    All Kafka messages are serialized as ``EventEnvelope`` so that consumers
    always receive a consistent schema regardless of the underlying payload.
    """

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str
    source: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    payload: dict = Field(default_factory=dict)  # type: ignore[type-arg]
    correlation_id: str | None = None


# ── Serialization helpers ────────────────────────────────────────────────────


def serialize_event(envelope: EventEnvelope) -> bytes:
    """Serialize an ``EventEnvelope`` to UTF-8 JSON bytes for Kafka."""
    return envelope.model_dump_json().encode("utf-8")


def deserialize_event(data: bytes) -> EventEnvelope:
    """Deserialize UTF-8 JSON bytes back into an ``EventEnvelope``."""
    return EventEnvelope.model_validate(json.loads(data))
