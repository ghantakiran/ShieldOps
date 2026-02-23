"""SLO / Error Budget monitoring.

Tracks Service Level Indicators (SLIs) against targets and calculates
remaining error budget and burn rates.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


class SLOStatus(StrEnum):
    MET = "met"
    AT_RISK = "at_risk"
    BREACHED = "breached"


class SLODefinition(BaseModel):
    """Definition of a Service Level Objective."""

    name: str
    description: str = ""
    target: float = 0.999  # e.g. 99.9%
    window_days: int = 30  # rolling window
    sli_type: str = "availability"  # availability, latency, success_rate
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ErrorBudget(BaseModel):
    """Error budget state for an SLO."""

    slo_name: str
    target: float
    current_sli: float
    budget_total: float  # 1 - target
    budget_consumed: float
    budget_remaining: float
    burn_rate: float  # How fast budget is being consumed (1.0 = normal)
    status: SLOStatus
    window_days: int = 30
    calculated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class BurnRateAlert(BaseModel):
    """Alert when burn rate exceeds a threshold."""

    slo_name: str
    burn_rate: float
    threshold: float
    message: str
    severity: str = "warning"
    fired_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SLOEvent(BaseModel):
    """An SLI measurement event."""

    slo_name: str
    good: bool = True
    timestamp: float = Field(default_factory=time.monotonic)
    value: float = 1.0  # For latency-based SLIs


class SLOMonitor:
    """Tracks SLI metrics against SLO targets.

    Provides error budget calculation, burn rate analysis,
    and alerting when budgets are at risk.
    """

    DEFAULT_SLOS = [
        SLODefinition(
            name="api_availability",
            description="API endpoint availability",
            target=0.999,
            sli_type="availability",
        ),
        SLODefinition(
            name="agent_success_rate",
            description="Agent task completion success rate",
            target=0.95,
            sli_type="success_rate",
        ),
        SLODefinition(
            name="mttr",
            description="Mean Time To Remediation under 30 minutes",
            target=0.90,
            sli_type="latency",
        ),
        SLODefinition(
            name="remediation_success",
            description="Remediation action success rate",
            target=0.95,
            sli_type="success_rate",
        ),
    ]

    def __init__(
        self,
        burn_rate_threshold: float = 2.0,
        max_events: int = 100_000,
    ) -> None:
        self._slos: dict[str, SLODefinition] = {}
        self._events: dict[str, list[SLOEvent]] = {}
        self._alerts: list[BurnRateAlert] = []
        self._burn_rate_threshold = burn_rate_threshold
        self._max_events = max_events

        # Register default SLOs
        for slo in self.DEFAULT_SLOS:
            self.register_slo(slo)

    def register_slo(self, slo: SLODefinition) -> SLODefinition:
        self._slos[slo.name] = slo
        if slo.name not in self._events:
            self._events[slo.name] = []
        return slo

    def get_slo(self, name: str) -> SLODefinition | None:
        return self._slos.get(name)

    def list_slos(self) -> list[SLODefinition]:
        return list(self._slos.values())

    def record_event(self, event: SLOEvent) -> None:
        """Record an SLI measurement event."""
        if event.slo_name not in self._slos:
            return
        events = self._events.setdefault(event.slo_name, [])
        events.append(event)

        # Trim to max events
        if len(events) > self._max_events:
            events[:] = events[-self._max_events :]

    def get_error_budget(self, slo_name: str) -> ErrorBudget | None:
        """Calculate error budget for an SLO."""
        slo = self._slos.get(slo_name)
        if slo is None:
            return None

        events = self._events.get(slo_name, [])
        total = len(events)
        if total == 0:
            return ErrorBudget(
                slo_name=slo_name,
                target=slo.target,
                current_sli=1.0,
                budget_total=1.0 - slo.target,
                budget_consumed=0.0,
                budget_remaining=1.0 - slo.target,
                burn_rate=0.0,
                status=SLOStatus.MET,
                window_days=slo.window_days,
            )

        good_count = sum(1 for e in events if e.good)
        current_sli = good_count / total
        budget_total = 1.0 - slo.target
        budget_consumed = max(0.0, (1.0 - current_sli))
        budget_remaining = max(0.0, budget_total - budget_consumed)

        # Burn rate = (budget consumed / budget total) normalized to window
        burn_rate = budget_consumed / budget_total if budget_total > 0 else 0.0

        # Status
        if budget_remaining <= 0:
            status = SLOStatus.BREACHED
        elif burn_rate >= self._burn_rate_threshold:
            status = SLOStatus.AT_RISK
        else:
            status = SLOStatus.MET

        budget = ErrorBudget(
            slo_name=slo_name,
            target=slo.target,
            current_sli=current_sli,
            budget_total=budget_total,
            budget_consumed=budget_consumed,
            budget_remaining=budget_remaining,
            burn_rate=burn_rate,
            status=status,
            window_days=slo.window_days,
        )

        # Check burn rate alerts
        if burn_rate >= self._burn_rate_threshold:
            alert = BurnRateAlert(
                slo_name=slo_name,
                burn_rate=burn_rate,
                threshold=self._burn_rate_threshold,
                message=(
                    f"SLO '{slo_name}' burn rate {burn_rate:.2f}x"
                    f" exceeds threshold {self._burn_rate_threshold:.1f}x"
                ),
                severity="critical" if status == SLOStatus.BREACHED else "warning",
            )
            self._alerts.append(alert)

        return budget

    def get_all_budgets(self) -> list[ErrorBudget]:
        budgets = []
        for name in self._slos:
            budget = self.get_error_budget(name)
            if budget:
                budgets.append(budget)
        return budgets

    def get_burn_rate_history(self, slo_name: str) -> list[dict[str, Any]]:
        """Get burn rate snapshots over time (simplified)."""
        events = self._events.get(slo_name, [])
        if not events:
            return []

        # Create buckets of 100 events each
        bucket_size = max(1, len(events) // 10)
        history = []
        for i in range(0, len(events), bucket_size):
            bucket = events[i : i + bucket_size]
            good = sum(1 for e in bucket if e.good)
            total = len(bucket)
            sli = good / total if total else 1.0
            slo = self._slos.get(slo_name)
            target = slo.target if slo else 0.999
            budget_total = 1.0 - target
            consumed = max(0.0, 1.0 - sli)
            rate = consumed / budget_total if budget_total > 0 else 0.0
            history.append(
                {
                    "bucket_index": i // bucket_size,
                    "events": total,
                    "sli": round(sli, 6),
                    "burn_rate": round(rate, 4),
                }
            )

        return history

    def get_alerts(self, slo_name: str | None = None) -> list[BurnRateAlert]:
        if slo_name:
            return [a for a in self._alerts if a.slo_name == slo_name]
        return list(self._alerts)
