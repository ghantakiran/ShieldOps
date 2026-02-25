"""Regulatory Change Monitor — track regulatory framework changes."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class RegulatoryBody(StrEnum):
    NIST = "nist"
    ISO = "iso"
    PCI_SSC = "pci_ssc"
    HIPAA_HHS = "hipaa_hhs"
    GDPR_EU = "gdpr_eu"


class ChangeUrgency(StrEnum):
    IMMEDIATE = "immediate"
    WITHIN_30_DAYS = "within_30_days"
    WITHIN_90_DAYS = "within_90_days"
    NEXT_AUDIT_CYCLE = "next_audit_cycle"
    INFORMATIONAL = "informational"


class ComplianceImpact(StrEnum):
    NO_IMPACT = "no_impact"
    MINOR_UPDATE = "minor_update"
    MAJOR_UPDATE = "major_update"
    NEW_CONTROL = "new_control"
    CONTROL_REMOVED = "control_removed"


# --- Models ---


class RegulatoryChange(BaseModel):
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
    )
    body: RegulatoryBody = RegulatoryBody.NIST
    regulation: str = ""
    change_summary: str = ""
    urgency: ChangeUrgency = ChangeUrgency.INFORMATIONAL
    impact: ComplianceImpact = ComplianceImpact.NO_IMPACT
    affected_controls: list[str] = Field(
        default_factory=list,
    )
    effective_date: str = ""
    is_addressed: bool = False
    created_at: float = Field(default_factory=time.time)


class ImpactAssessment(BaseModel):
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
    )
    change_id: str = ""
    service_name: str = ""
    current_compliant: bool = True
    effort_hours: float = 0.0
    priority: int = 0
    assessor: str = ""
    created_at: float = Field(default_factory=time.time)


class RegulatoryReport(BaseModel):
    total_changes: int = 0
    addressed_count: int = 0
    pending_count: int = 0
    by_body: dict[str, int] = Field(
        default_factory=dict,
    )
    by_urgency: dict[str, int] = Field(
        default_factory=dict,
    )
    by_impact: dict[str, int] = Field(
        default_factory=dict,
    )
    overdue_changes: list[str] = Field(
        default_factory=list,
    )
    recommendations: list[str] = Field(
        default_factory=list,
    )
    generated_at: float = Field(default_factory=time.time)


# --- Monitor ---


class RegulatoryChangeMonitor:
    """Track regulatory and compliance framework changes."""

    def __init__(
        self,
        max_changes: int = 50000,
        overdue_grace_days: int = 30,
    ) -> None:
        self._max_changes = max_changes
        self._overdue_grace_days = overdue_grace_days
        self._items: list[RegulatoryChange] = []
        self._assessments: list[ImpactAssessment] = []
        logger.info(
            "regulatory_monitor.initialized",
            max_changes=max_changes,
            overdue_grace_days=overdue_grace_days,
        )

    # -- record / get / list --

    def record_change(
        self,
        body: RegulatoryBody = RegulatoryBody.NIST,
        regulation: str = "",
        change_summary: str = "",
        urgency: ChangeUrgency = ChangeUrgency.INFORMATIONAL,
        impact: ComplianceImpact = ComplianceImpact.NO_IMPACT,
        affected_controls: list[str] | None = None,
        effective_date: str = "",
        **kw: Any,
    ) -> RegulatoryChange:
        """Record a regulatory change event."""
        change = RegulatoryChange(
            body=body,
            regulation=regulation,
            change_summary=change_summary,
            urgency=urgency,
            impact=impact,
            affected_controls=affected_controls or [],
            effective_date=effective_date,
            **kw,
        )
        self._items.append(change)
        if len(self._items) > self._max_changes:
            self._items.pop(0)
        logger.info(
            "regulatory_monitor.change_recorded",
            change_id=change.id,
            body=body,
            regulation=regulation,
        )
        return change

    def get_change(
        self,
        change_id: str,
    ) -> RegulatoryChange | None:
        """Get a single change by ID."""
        for item in self._items:
            if item.id == change_id:
                return item
        return None

    def list_changes(
        self,
        body: RegulatoryBody | None = None,
        urgency: ChangeUrgency | None = None,
        limit: int = 50,
    ) -> list[RegulatoryChange]:
        """List changes with optional filters."""
        results = list(self._items)
        if body is not None:
            results = [r for r in results if r.body == body]
        if urgency is not None:
            results = [r for r in results if r.urgency == urgency]
        return results[-limit:]

    # -- domain operations --

    def assess_impact(
        self,
        change_id: str,
        service_name: str = "",
        effort_hours: float = 0.0,
        assessor: str = "",
        **kw: Any,
    ) -> ImpactAssessment | None:
        """Create an impact assessment for a change."""
        change = self.get_change(change_id)
        if change is None:
            return None
        compliant = effort_hours == 0.0
        priority = self._calculate_priority(change)
        assessment = ImpactAssessment(
            change_id=change_id,
            service_name=service_name,
            current_compliant=compliant,
            effort_hours=effort_hours,
            priority=priority,
            assessor=assessor,
            **kw,
        )
        self._assessments.append(assessment)
        logger.info(
            "regulatory_monitor.impact_assessed",
            assessment_id=assessment.id,
            change_id=change_id,
            service_name=service_name,
        )
        return assessment

    def mark_addressed(
        self,
        change_id: str,
    ) -> RegulatoryChange | None:
        """Mark a regulatory change as addressed."""
        change = self.get_change(change_id)
        if change is None:
            return None
        change.is_addressed = True
        logger.info(
            "regulatory_monitor.addressed",
            change_id=change_id,
        )
        return change

    def identify_overdue_changes(
        self,
    ) -> list[RegulatoryChange]:
        """Identify changes past their grace period."""
        now = time.time()
        grace_seconds = self._overdue_grace_days * 86400
        overdue: list[RegulatoryChange] = []
        for c in self._items:
            if c.is_addressed:
                continue
            age = now - c.created_at
            if age > grace_seconds:
                overdue.append(c)
        return overdue

    def calculate_compliance_gap(
        self,
    ) -> dict[str, Any]:
        """Calculate gap between pending and addressed."""
        total = len(self._items)
        addressed = sum(1 for c in self._items if c.is_addressed)
        pending = total - addressed
        gap_pct = 0.0
        if total > 0:
            gap_pct = round(pending / total * 100, 2)
        return {
            "total_changes": total,
            "addressed": addressed,
            "pending": pending,
            "gap_pct": gap_pct,
        }

    def estimate_total_effort(
        self,
    ) -> dict[str, Any]:
        """Estimate total effort from assessments."""
        total_hours = sum(a.effort_hours for a in self._assessments)
        pending_hours = 0.0
        for a in self._assessments:
            change = self.get_change(a.change_id)
            if change and not change.is_addressed:
                pending_hours += a.effort_hours
        return {
            "total_effort_hours": round(total_hours, 2),
            "pending_effort_hours": round(pending_hours, 2),
            "completed_effort_hours": round(total_hours - pending_hours, 2),
            "total_assessments": len(self._assessments),
        }

    # -- report --

    def generate_regulatory_report(
        self,
    ) -> RegulatoryReport:
        """Generate a comprehensive regulatory report."""
        by_body: dict[str, int] = {}
        by_urgency: dict[str, int] = {}
        by_impact: dict[str, int] = {}
        addressed = 0
        for c in self._items:
            b = c.body.value
            by_body[b] = by_body.get(b, 0) + 1
            u = c.urgency.value
            by_urgency[u] = by_urgency.get(u, 0) + 1
            i = c.impact.value
            by_impact[i] = by_impact.get(i, 0) + 1
            if c.is_addressed:
                addressed += 1
        overdue = self.identify_overdue_changes()
        overdue_ids = [c.id for c in overdue]
        total = len(self._items)
        recs = self._build_recommendations(
            total,
            addressed,
            len(overdue_ids),
        )
        return RegulatoryReport(
            total_changes=total,
            addressed_count=addressed,
            pending_count=total - addressed,
            by_body=by_body,
            by_urgency=by_urgency,
            by_impact=by_impact,
            overdue_changes=overdue_ids,
            recommendations=recs,
        )

    # -- housekeeping --

    def clear_data(self) -> int:
        """Clear all data. Returns records cleared."""
        count = len(self._items)
        self._items.clear()
        self._assessments.clear()
        logger.info(
            "regulatory_monitor.cleared",
            count=count,
        )
        return count

    def get_stats(self) -> dict[str, Any]:
        """Return summary statistics."""
        body_dist: dict[str, int] = {}
        for c in self._items:
            key = c.body.value
            body_dist[key] = body_dist.get(key, 0) + 1
        return {
            "total_changes": len(self._items),
            "total_assessments": len(self._assessments),
            "max_changes": self._max_changes,
            "overdue_grace_days": self._overdue_grace_days,
            "body_distribution": body_dist,
        }

    # -- internal helpers --

    def _calculate_priority(
        self,
        change: RegulatoryChange,
    ) -> int:
        priority_map = {
            ChangeUrgency.IMMEDIATE: 1,
            ChangeUrgency.WITHIN_30_DAYS: 2,
            ChangeUrgency.WITHIN_90_DAYS: 3,
            ChangeUrgency.NEXT_AUDIT_CYCLE: 4,
            ChangeUrgency.INFORMATIONAL: 5,
        }
        return priority_map.get(change.urgency, 5)

    def _build_recommendations(
        self,
        total: int,
        addressed: int,
        overdue: int,
    ) -> list[str]:
        recs: list[str] = []
        if overdue > 0:
            recs.append(f"{overdue} overdue change(s) need attention")
        if total == 0:
            recs.append("No regulatory changes tracked")
        if total > 0 and addressed < total:
            pending = total - addressed
            recs.append(f"{pending} change(s) still pending")
        if not recs:
            recs.append("All regulatory changes addressed")
        return recs
