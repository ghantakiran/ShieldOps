"""Billing source protocol for cloud cost data."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass
class BillingData:
    """Standardized billing query result.

    Attributes:
        total_cost: Aggregate cost for the queried period.
        currency: ISO 4217 currency code.
        period_start: ISO-8601 date string for the start of the period.
        period_end: ISO-8601 date string for the end of the period.
        by_service: Per-service cost breakdown.
        by_environment: Per-environment cost breakdown.
        daily_breakdown: Day-by-day cost breakdown.
        metadata: Provider-specific or diagnostic metadata.
    """

    total_cost: float
    currency: str = "USD"
    period_start: str = ""
    period_end: str = ""
    by_service: list[dict[str, Any]] = field(default_factory=list)
    by_environment: list[dict[str, Any]] = field(default_factory=list)
    daily_breakdown: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class BillingSource(Protocol):
    """Protocol for cloud billing data sources.

    Any class that implements ``query`` with the signature below satisfies
    this protocol -- no inheritance required.
    """

    provider: str

    async def query(
        self,
        environment: str = "production",
        period: str = "30d",
    ) -> BillingData:
        """Query billing data for a time period."""
        ...
