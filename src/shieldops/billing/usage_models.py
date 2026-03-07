"""Pydantic v2 models for usage-based billing.

Defines event types, usage events, summaries, billing tiers,
and usage alert structures for metered billing.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class UsageEventType(StrEnum):
    """Billable event types tracked by the usage metering system."""

    agent_execution = "agent_execution"
    investigation_run = "investigation_run"
    remediation_action = "remediation_action"
    security_scan = "security_scan"
    compliance_assessment = "compliance_assessment"
    war_room_session = "war_room_session"
    api_call = "api_call"


class UsageEvent(BaseModel):
    """A single billable usage event."""

    event_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    org_id: str
    event_type: UsageEventType
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    quantity: int = 1
    unit_label: str = "execution"
    metadata: dict[str, str] = Field(default_factory=dict)
    reported_to_stripe: bool = False


class UsageSummary(BaseModel):
    """Aggregated usage for an organisation over a billing period."""

    org_id: str
    period_start: datetime
    period_end: datetime
    events_by_type: dict[UsageEventType, int] = Field(
        default_factory=dict,
    )
    total_events: int = 0
    estimated_cost: float = 0.0


class BillingTier(BaseModel):
    """Definition of a usage-based billing tier."""

    tier_name: str
    included_executions: int
    overage_price_per_unit: float
    features: list[str] = Field(default_factory=list)


class UsageAlertType(StrEnum):
    """Types of usage alerts."""

    approaching_limit = "approaching_limit"
    exceeded_limit = "exceeded_limit"
    anomalous_usage = "anomalous_usage"


class UsageAlert(BaseModel):
    """Alert raised when usage crosses a threshold."""

    alert_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    org_id: str
    alert_type: UsageAlertType
    threshold_pct: float
    current_usage: int
    limit: int
    message: str
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
    )
    resolved: bool = False
