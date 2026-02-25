"""Runbook Gap Analyzer — identify operational scenarios lacking runbook coverage."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class GapSeverity(StrEnum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"
    URGENT = "urgent"


class GapCategory(StrEnum):
    NO_RUNBOOK = "no_runbook"
    OUTDATED_RUNBOOK = "outdated_runbook"
    PARTIAL_COVERAGE = "partial_coverage"
    WRONG_SERVICE = "wrong_service"
    UNTESTED_RUNBOOK = "untested_runbook"


class DiscoverySource(StrEnum):
    INCIDENT_HISTORY = "incident_history"
    ALERT_ANALYSIS = "alert_analysis"
    FAILURE_MODE_CATALOG = "failure_mode_catalog"
    TEAM_FEEDBACK = "team_feedback"
    AUTOMATED_SCAN = "automated_scan"


# --- Models ---


class RunbookGap(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    scenario: str = ""
    severity: GapSeverity = GapSeverity.LOW
    category: GapCategory = GapCategory.NO_RUNBOOK
    source: DiscoverySource = DiscoverySource.AUTOMATED_SCAN
    incident_count: int = 0
    resolved: bool = False
    created_at: float = Field(default_factory=time.time)


class GapRemediation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    gap_id: str = ""
    action: str = ""
    assignee: str = ""
    status: str = "pending"
    created_at: float = Field(default_factory=time.time)


class GapAnalysisReport(BaseModel):
    total_gaps: int = 0
    total_resolved: int = 0
    total_remediations: int = 0
    by_severity: dict[str, int] = Field(default_factory=dict)
    by_category: dict[str, int] = Field(default_factory=dict)
    by_source: dict[str, int] = Field(default_factory=dict)
    critical_services: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class RunbookGapAnalyzer:
    """Identify operational scenarios lacking runbook coverage."""

    def __init__(
        self,
        max_gaps: int = 100000,
        critical_incident_threshold: int = 3,
    ) -> None:
        self._max_gaps = max_gaps
        self._critical_incident_threshold = critical_incident_threshold
        self._gaps: list[RunbookGap] = []
        self._remediations: list[GapRemediation] = []
        logger.info(
            "runbook_gap_analyzer.initialized",
            max_gaps=max_gaps,
            critical_incident_threshold=critical_incident_threshold,
        )

    # -- register / get / list ---------------------------------------

    def register_gap(
        self,
        service_name: str,
        scenario: str = "",
        severity: GapSeverity = GapSeverity.LOW,
        category: GapCategory = GapCategory.NO_RUNBOOK,
        source: DiscoverySource = DiscoverySource.AUTOMATED_SCAN,
        incident_count: int = 0,
        **kw: Any,
    ) -> RunbookGap:
        gap = RunbookGap(
            service_name=service_name,
            scenario=scenario,
            severity=severity,
            category=category,
            source=source,
            incident_count=incident_count,
            **kw,
        )
        self._gaps.append(gap)
        if len(self._gaps) > self._max_gaps:
            self._gaps = self._gaps[-self._max_gaps :]
        logger.info(
            "runbook_gap_analyzer.gap_registered",
            gap_id=gap.id,
            service_name=service_name,
        )
        return gap

    def get_gap(self, gap_id: str) -> RunbookGap | None:
        for g in self._gaps:
            if g.id == gap_id:
                return g
        return None

    def list_gaps(
        self,
        service_name: str | None = None,
        severity: GapSeverity | None = None,
        category: GapCategory | None = None,
        limit: int = 50,
    ) -> list[RunbookGap]:
        results = list(self._gaps)
        if service_name is not None:
            results = [r for r in results if r.service_name == service_name]
        if severity is not None:
            results = [r for r in results if r.severity == severity]
        if category is not None:
            results = [r for r in results if r.category == category]
        return results[-limit:]

    # -- remediations ------------------------------------------------

    def create_remediation(
        self,
        gap_id: str,
        action: str = "",
        assignee: str = "",
        **kw: Any,
    ) -> GapRemediation | None:
        gap = self.get_gap(gap_id)
        if gap is None:
            return None
        remediation = GapRemediation(
            gap_id=gap_id,
            action=action,
            assignee=assignee,
            **kw,
        )
        self._remediations.append(remediation)
        logger.info(
            "runbook_gap_analyzer.remediation_created",
            remediation_id=remediation.id,
            gap_id=gap_id,
        )
        return remediation

    def list_remediations(
        self,
        gap_id: str | None = None,
        limit: int = 50,
    ) -> list[GapRemediation]:
        results = list(self._remediations)
        if gap_id is not None:
            results = [r for r in results if r.gap_id == gap_id]
        return results[-limit:]

    # -- domain operations -------------------------------------------

    def mark_gap_resolved(self, gap_id: str) -> bool:
        gap = self.get_gap(gap_id)
        if gap is None:
            return False
        gap.resolved = True
        logger.info("runbook_gap_analyzer.gap_resolved", gap_id=gap_id)
        return True

    def correlate_incidents_to_gaps(self) -> list[dict[str, Any]]:
        """Identify gaps with high incident correlation."""
        results: list[dict[str, Any]] = []
        for g in self._gaps:
            if g.incident_count >= self._critical_incident_threshold and not g.resolved:
                results.append(
                    {
                        "gap_id": g.id,
                        "service_name": g.service_name,
                        "scenario": g.scenario,
                        "incident_count": g.incident_count,
                        "severity": g.severity.value,
                        "category": g.category.value,
                    }
                )
        results.sort(key=lambda x: x["incident_count"], reverse=True)
        return results

    def prioritize_gaps(self) -> list[RunbookGap]:
        """Prioritize gaps by severity and incident count."""
        severity_order = {
            GapSeverity.LOW: 0,
            GapSeverity.MODERATE: 1,
            GapSeverity.HIGH: 2,
            GapSeverity.CRITICAL: 3,
            GapSeverity.URGENT: 4,
        }
        unresolved = [g for g in self._gaps if not g.resolved]
        unresolved.sort(
            key=lambda g: (
                severity_order.get(g.severity, 0),
                g.incident_count,
            ),
            reverse=True,
        )
        return unresolved

    # -- report / stats ----------------------------------------------

    def generate_gap_report(self) -> GapAnalysisReport:
        by_severity: dict[str, int] = {}
        for g in self._gaps:
            key = g.severity.value
            by_severity[key] = by_severity.get(key, 0) + 1
        by_category: dict[str, int] = {}
        for g in self._gaps:
            key = g.category.value
            by_category[key] = by_category.get(key, 0) + 1
        by_source: dict[str, int] = {}
        for g in self._gaps:
            key = g.source.value
            by_source[key] = by_source.get(key, 0) + 1
        resolved_count = sum(1 for g in self._gaps if g.resolved)
        critical_svcs = list(
            {
                g.service_name
                for g in self._gaps
                if g.severity in (GapSeverity.CRITICAL, GapSeverity.URGENT) and not g.resolved
            }
        )
        recs: list[str] = []
        unresolved = len(self._gaps) - resolved_count
        if unresolved > 0:
            recs.append(f"{unresolved} unresolved gap(s) need attention")
        if critical_svcs:
            recs.append(f"{len(critical_svcs)} service(s) with critical/urgent gaps")
        if not recs:
            recs.append("All runbook gaps have been addressed")
        return GapAnalysisReport(
            total_gaps=len(self._gaps),
            total_resolved=resolved_count,
            total_remediations=len(self._remediations),
            by_severity=by_severity,
            by_category=by_category,
            by_source=by_source,
            critical_services=sorted(critical_svcs),
            recommendations=recs,
        )

    def clear_data(self) -> int:
        count = len(self._gaps)
        self._gaps.clear()
        self._remediations.clear()
        logger.info("runbook_gap_analyzer.cleared", count=count)
        return count

    def get_stats(self) -> dict[str, Any]:
        sev_dist: dict[str, int] = {}
        for g in self._gaps:
            key = g.severity.value
            sev_dist[key] = sev_dist.get(key, 0) + 1
        return {
            "total_gaps": len(self._gaps),
            "total_remediations": len(self._remediations),
            "critical_incident_threshold": self._critical_incident_threshold,
            "severity_distribution": sev_dist,
        }
