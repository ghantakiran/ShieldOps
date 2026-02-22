"""SLA Management Engine.

Provides SLO definitions, error budget tracking, breach detection,
and auto-escalation when budget burn rates reach critical levels.
Supports 99.9%, 99.95%, and 99.99% availability targets with
configurable rolling windows.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# ── Pydantic Models ──────────────────────────────────────────────


class SLODefinition(BaseModel):
    """Service Level Objective definition."""

    id: str
    name: str
    service: str
    target: float  # e.g., 99.9, 99.95, 99.99
    window_days: int = 30
    metric_type: str = "availability"
    description: str = ""
    created_at: datetime
    updated_at: datetime


class ErrorBudget(BaseModel):
    """Current error budget state for an SLO."""

    slo_id: str
    total_minutes: float
    consumed_minutes: float
    remaining_minutes: float
    remaining_percentage: float
    burn_rate: float
    projected_exhaustion: datetime | None = None
    status: str  # "healthy", "warning", "critical", "exhausted"


class SLABreach(BaseModel):
    """A recorded SLA breach / downtime event."""

    id: str
    slo_id: str
    service: str
    started_at: datetime
    ended_at: datetime | None = None
    duration_minutes: float
    severity: str
    description: str
    auto_escalated: bool = False


class SLADashboard(BaseModel):
    """Aggregate SLA dashboard view."""

    slos: list[dict[str, Any]] = Field(default_factory=list)
    breaches: list[dict[str, Any]] = Field(default_factory=list)
    overall_health: str = "healthy"
    budget_summary: dict[str, Any] = Field(default_factory=dict)


class SLOCreateRequest(BaseModel):
    """Request body for creating a new SLO."""

    name: str
    service: str
    target: float
    window_days: int = 30
    metric_type: str = "availability"
    description: str = ""


class SLOUpdateRequest(BaseModel):
    """Request body for updating an existing SLO (all fields optional)."""

    name: str | None = None
    target: float | None = None
    window_days: int | None = None
    description: str | None = None


# ── SLA Engine ───────────────────────────────────────────────────


class SLAEngine:
    """In-memory SLA management engine.

    Tracks SLO definitions, records downtime events, calculates error
    budgets with rolling windows, detects breaches, and triggers
    auto-escalation when burn rates are critical.
    """

    def __init__(self) -> None:
        self._slos: dict[str, SLODefinition] = {}
        self._breaches: list[SLABreach] = []
        self._downtime_records: list[dict[str, Any]] = []

    # ── CRUD ─────────────────────────────────────────────────────

    def create_slo(self, request: SLOCreateRequest) -> SLODefinition:
        """Create a new SLO definition."""
        now = datetime.now(UTC)
        slo = SLODefinition(
            id=f"slo-{uuid4().hex[:12]}",
            name=request.name,
            service=request.service,
            target=request.target,
            window_days=request.window_days,
            metric_type=request.metric_type,
            description=request.description,
            created_at=now,
            updated_at=now,
        )
        self._slos[slo.id] = slo
        logger.info(
            "slo_created",
            slo_id=slo.id,
            name=slo.name,
            target=slo.target,
        )
        return slo

    def get_slo(self, slo_id: str) -> SLODefinition | None:
        """Get an SLO by ID, or None if not found."""
        return self._slos.get(slo_id)

    def list_slos(self) -> list[SLODefinition]:
        """List all SLO definitions."""
        return list(self._slos.values())

    def update_slo(self, slo_id: str, request: SLOUpdateRequest) -> SLODefinition | None:
        """Update an existing SLO. Returns None if not found."""
        slo = self._slos.get(slo_id)
        if slo is None:
            return None

        if request.name is not None:
            slo.name = request.name
        if request.target is not None:
            slo.target = request.target
        if request.window_days is not None:
            slo.window_days = request.window_days
        if request.description is not None:
            slo.description = request.description

        slo.updated_at = datetime.now(UTC)
        logger.info("slo_updated", slo_id=slo_id)
        return slo

    def delete_slo(self, slo_id: str) -> bool:
        """Delete an SLO. Returns True if found and deleted."""
        if slo_id not in self._slos:
            return False
        del self._slos[slo_id]
        logger.info("slo_deleted", slo_id=slo_id)
        return True

    # ── Downtime Recording ───────────────────────────────────────

    def record_downtime(
        self,
        slo_id: str,
        duration_minutes: float,
        description: str = "",
    ) -> SLABreach:
        """Record a downtime event against an SLO.

        Creates a breach record and checks whether the error budget
        has been exhausted, triggering auto-escalation if needed.
        """
        slo = self._slos.get(slo_id)
        if slo is None:
            raise ValueError(f"SLO not found: {slo_id}")

        now = datetime.now(UTC)

        # Store raw downtime record for budget calculations
        self._downtime_records.append(
            {
                "slo_id": slo_id,
                "duration_minutes": duration_minutes,
                "recorded_at": now,
                "description": description,
            }
        )

        # Determine severity based on duration relative to total budget
        budget = self.calculate_error_budget(slo_id)
        if budget.remaining_percentage <= 0:
            severity = "critical"
        elif budget.remaining_percentage <= 20:
            severity = "high"
        elif budget.remaining_percentage <= 50:
            severity = "medium"
        else:
            severity = "low"

        breach = SLABreach(
            id=f"breach-{uuid4().hex[:12]}",
            slo_id=slo_id,
            service=slo.service,
            started_at=now,
            ended_at=now + timedelta(minutes=duration_minutes),
            duration_minutes=duration_minutes,
            severity=severity,
            description=description,
        )
        self._breaches.append(breach)

        logger.info(
            "downtime_recorded",
            slo_id=slo_id,
            duration_minutes=duration_minutes,
            severity=severity,
            budget_remaining_pct=budget.remaining_percentage,
        )

        # Auto-escalate if budget is critical or exhausted
        if budget.status in ("critical", "exhausted"):
            escalation = self.auto_escalate(slo_id)
            breach.auto_escalated = True
            logger.warning(
                "sla_auto_escalated",
                slo_id=slo_id,
                escalation=escalation,
            )

        return breach

    # ── Error Budget Calculation ─────────────────────────────────

    def calculate_error_budget(self, slo_id: str) -> ErrorBudget:
        """Calculate the current error budget for an SLO.

        Budget formula:
            total_minutes = window_days * 24 * 60 * (1 - target / 100)
            e.g., 30 days at 99.9% = 43.2 minutes

        Burn rate is normalized: consumed / elapsed_fraction / total.
        A burn rate of 1.0 means on-track to exhaust exactly at window end.
        """
        slo = self._slos.get(slo_id)
        if slo is None:
            raise ValueError(f"SLO not found: {slo_id}")

        total_window_minutes = slo.window_days * 24 * 60
        total_budget = total_window_minutes * (1 - slo.target / 100)

        now = datetime.now(UTC)
        window_start = now - timedelta(days=slo.window_days)

        # Sum downtime within the rolling window
        consumed = 0.0
        for record in self._downtime_records:
            if record["slo_id"] == slo_id and record["recorded_at"] >= window_start:
                consumed += record["duration_minutes"]

        remaining = max(0.0, total_budget - consumed)
        remaining_pct = (remaining / total_budget * 100) if total_budget > 0 else 0.0

        # Burn rate: normalized rate of consumption
        # elapsed_fraction = fraction of the window that has passed
        elapsed_seconds = (now - window_start).total_seconds()
        window_seconds = slo.window_days * 24 * 60 * 60
        elapsed_fraction = elapsed_seconds / window_seconds if window_seconds > 0 else 1.0

        if total_budget > 0 and elapsed_fraction > 0:
            burn_rate = (consumed / elapsed_fraction) / total_budget
        else:
            burn_rate = 0.0

        # Project exhaustion time based on burn rate
        projected_exhaustion: datetime | None = None
        if burn_rate > 0 and remaining > 0:
            # At current rate, how many minutes until budget is gone?
            minutes_per_window = consumed / elapsed_fraction if elapsed_fraction > 0 else 0
            if minutes_per_window > 0:
                remaining_fraction = remaining / minutes_per_window
                projected_exhaustion = now + timedelta(days=remaining_fraction * slo.window_days)

        # Status determination
        consumed_pct = 100 - remaining_pct
        if consumed_pct >= 100:
            budget_status = "exhausted"
        elif consumed_pct >= 80:
            budget_status = "critical"
        elif consumed_pct >= 50:
            budget_status = "warning"
        else:
            budget_status = "healthy"

        return ErrorBudget(
            slo_id=slo_id,
            total_minutes=round(total_budget, 4),
            consumed_minutes=round(consumed, 4),
            remaining_minutes=round(remaining, 4),
            remaining_percentage=round(remaining_pct, 2),
            burn_rate=round(burn_rate, 4),
            projected_exhaustion=projected_exhaustion,
            status=budget_status,
        )

    # ── Breach Detection ─────────────────────────────────────────

    def check_breach(self, slo_id: str) -> bool:
        """Check if the error budget for an SLO is exhausted."""
        budget = self.calculate_error_budget(slo_id)
        return budget.status == "exhausted"

    def get_breaches(
        self,
        slo_id: str | None = None,
        limit: int = 50,
    ) -> list[SLABreach]:
        """Get breach history, optionally filtered by SLO ID."""
        breaches = self._breaches
        if slo_id is not None:
            breaches = [b for b in breaches if b.slo_id == slo_id]
        # Return most recent first
        return sorted(breaches, key=lambda b: b.started_at, reverse=True)[:limit]

    # ── Dashboard ────────────────────────────────────────────────

    def get_dashboard(self) -> SLADashboard:
        """Build an aggregate SLA dashboard view."""
        slo_summaries = []
        budgets = []
        statuses: list[str] = []

        for slo in self._slos.values():
            budget = self.calculate_error_budget(slo.id)
            budgets.append(budget)
            statuses.append(budget.status)
            slo_summaries.append(
                {
                    "id": slo.id,
                    "name": slo.name,
                    "service": slo.service,
                    "target": slo.target,
                    "budget_status": budget.status,
                    "remaining_pct": budget.remaining_percentage,
                    "burn_rate": budget.burn_rate,
                }
            )

        recent_breaches = [
            {
                "id": b.id,
                "slo_id": b.slo_id,
                "service": b.service,
                "duration_minutes": b.duration_minutes,
                "severity": b.severity,
                "started_at": b.started_at.isoformat(),
                "auto_escalated": b.auto_escalated,
            }
            for b in self.get_breaches(limit=10)
        ]

        # Overall health: worst status across all SLOs
        if "exhausted" in statuses or "critical" in statuses:
            overall_health = "critical"
        elif "warning" in statuses:
            overall_health = "warning"
        else:
            overall_health = "healthy"

        # Budget summary counts
        budget_summary = {
            "total_slos": len(self._slos),
            "healthy": sum(1 for s in statuses if s == "healthy"),
            "warning": sum(1 for s in statuses if s == "warning"),
            "critical": sum(1 for s in statuses if s == "critical"),
            "exhausted": sum(1 for s in statuses if s == "exhausted"),
        }

        return SLADashboard(
            slos=slo_summaries,
            breaches=recent_breaches,
            overall_health=overall_health,
            budget_summary=budget_summary,
        )

    # ── Auto-Escalation ──────────────────────────────────────────

    def auto_escalate(self, slo_id: str) -> dict[str, Any]:
        """Trigger auto-escalation for an SLO with critical burn rate.

        Returns escalation details including the recommended action,
        notification targets, and current budget state.
        """
        slo = self._slos.get(slo_id)
        if slo is None:
            raise ValueError(f"SLO not found: {slo_id}")

        budget = self.calculate_error_budget(slo_id)

        escalation = {
            "slo_id": slo_id,
            "slo_name": slo.name,
            "service": slo.service,
            "target": slo.target,
            "budget_status": budget.status,
            "remaining_minutes": budget.remaining_minutes,
            "remaining_percentage": budget.remaining_percentage,
            "burn_rate": budget.burn_rate,
            "escalated_at": datetime.now(UTC).isoformat(),
            "action": "page_oncall",
            "priority": "P1" if budget.status == "exhausted" else "P2",
            "notification_targets": ["oncall-sre", "service-owner", "engineering-lead"],
            "message": (
                f"SLO '{slo.name}' for service '{slo.service}' has "
                f"{budget.remaining_percentage:.1f}% error budget remaining "
                f"(burn rate: {budget.burn_rate:.2f}x). "
                f"Immediate attention required."
            ),
        }

        logger.warning(
            "sla_escalation_triggered",
            slo_id=slo_id,
            service=slo.service,
            priority=escalation["priority"],
            remaining_pct=budget.remaining_percentage,
        )

        return escalation
