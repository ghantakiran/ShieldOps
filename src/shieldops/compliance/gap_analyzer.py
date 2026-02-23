"""Compliance Gap Analyzer — identifies gaps in compliance coverage."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class GapSeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class GapStatus(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    ACCEPTED = "accepted"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class ComplianceControl(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    framework: str
    control_id: str
    title: str
    description: str = ""
    implemented: bool = False
    evidence_count: int = 0
    last_assessed_at: float | None = None


class ComplianceGap(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    control_id: str
    framework: str
    severity: GapSeverity = GapSeverity.HIGH
    status: GapStatus = GapStatus.OPEN
    remediation_plan: str = ""
    assigned_to: str = ""
    detected_at: float = Field(default_factory=time.time)
    resolved_at: float | None = None


# ---------------------------------------------------------------------------
# Analyzer
# ---------------------------------------------------------------------------


class ComplianceGapAnalyzer:
    """Identifies gaps in compliance coverage across frameworks."""

    def __init__(
        self,
        max_controls: int = 5000,
        max_gaps: int = 10000,
    ) -> None:
        self.max_controls = max_controls
        self.max_gaps = max_gaps
        self._controls: dict[str, ComplianceControl] = {}
        self._gaps: dict[str, ComplianceGap] = {}
        logger.info(
            "compliance_gap_analyzer.initialized",
            max_controls=max_controls,
            max_gaps=max_gaps,
        )

    def register_control(
        self,
        framework: str,
        control_id: str,
        title: str,
        **kw: Any,
    ) -> ComplianceControl:
        """Register a compliance control."""
        if len(self._controls) >= self.max_controls:
            oldest_key = next(iter(self._controls))
            del self._controls[oldest_key]
        control = ComplianceControl(
            framework=framework,
            control_id=control_id,
            title=title,
            **kw,
        )
        self._controls[control.id] = control
        logger.info(
            "compliance_gap_analyzer.control_registered",
            internal_id=control.id,
            framework=framework,
            control_id=control_id,
        )
        return control

    def assess_control(
        self,
        control_id_internal: str,
        implemented: bool,
        evidence_count: int = 0,
    ) -> ComplianceControl | None:
        """Assess a control; auto-creates a gap if not implemented."""
        control = self._controls.get(control_id_internal)
        if control is None:
            return None
        control.implemented = implemented
        control.evidence_count = evidence_count
        control.last_assessed_at = time.time()

        if not implemented:
            self.create_gap(
                control_id_internal,
                GapSeverity.HIGH,
                remediation_plan="",
            )

        logger.info(
            "compliance_gap_analyzer.control_assessed",
            internal_id=control_id_internal,
            implemented=implemented,
            evidence_count=evidence_count,
        )
        return control

    def create_gap(
        self,
        control_id_internal: str,
        severity: GapSeverity | str,
        **kw: Any,
    ) -> ComplianceGap:
        """Create a compliance gap for a control."""
        if len(self._gaps) >= self.max_gaps:
            oldest_key = next(iter(self._gaps))
            del self._gaps[oldest_key]
        control = self._controls.get(control_id_internal)
        framework = control.framework if control else ""
        gap = ComplianceGap(
            control_id=control_id_internal,
            framework=framework,
            severity=GapSeverity(severity),
            **kw,
        )
        self._gaps[gap.id] = gap
        logger.info(
            "compliance_gap_analyzer.gap_created",
            gap_id=gap.id,
            control_id=control_id_internal,
            severity=str(severity),
        )
        return gap

    def update_gap_status(
        self,
        gap_id: str,
        status: GapStatus | str,
    ) -> ComplianceGap | None:
        """Update the status of a gap."""
        gap = self._gaps.get(gap_id)
        if gap is None:
            return None
        gap.status = GapStatus(status)
        if gap.status == GapStatus.RESOLVED:
            gap.resolved_at = time.time()
        logger.info(
            "compliance_gap_analyzer.gap_status_updated",
            gap_id=gap_id,
            status=str(status),
        )
        return gap

    def assign_gap(
        self,
        gap_id: str,
        assigned_to: str,
    ) -> ComplianceGap | None:
        """Assign a gap to a person."""
        gap = self._gaps.get(gap_id)
        if gap is None:
            return None
        gap.assigned_to = assigned_to
        logger.info(
            "compliance_gap_analyzer.gap_assigned",
            gap_id=gap_id,
            assigned_to=assigned_to,
        )
        return gap

    def resolve_gap(self, gap_id: str) -> ComplianceGap | None:
        """Mark a gap as resolved."""
        return self.update_gap_status(gap_id, GapStatus.RESOLVED)

    def get_control(
        self,
        control_id_internal: str,
    ) -> ComplianceControl | None:
        """Return a control by its internal ID."""
        return self._controls.get(control_id_internal)

    def list_controls(
        self,
        framework: str | None = None,
        implemented: bool | None = None,
    ) -> list[ComplianceControl]:
        """List controls with optional filters."""
        results = list(self._controls.values())
        if framework is not None:
            results = [c for c in results if c.framework == framework]
        if implemented is not None:
            results = [c for c in results if c.implemented == implemented]
        return results

    def list_gaps(
        self,
        framework: str | None = None,
        severity: GapSeverity | str | None = None,
        status: GapStatus | str | None = None,
    ) -> list[ComplianceGap]:
        """List gaps with optional filters."""
        results = list(self._gaps.values())
        if framework is not None:
            results = [g for g in results if g.framework == framework]
        if severity is not None:
            sev = GapSeverity(severity) if isinstance(severity, str) else severity
            results = [g for g in results if g.severity == sev]
        if status is not None:
            st = GapStatus(status) if isinstance(status, str) else status
            results = [g for g in results if g.status == st]
        return results

    def get_framework_coverage(self, framework: str) -> dict[str, Any]:
        """Compute coverage for a framework."""
        controls = [c for c in self._controls.values() if c.framework == framework]
        total = len(controls)
        implemented = sum(1 for c in controls if c.implemented)
        coverage_pct = round((implemented / total) * 100, 2) if total else 0.0

        gaps = [g for g in self._gaps.values() if g.framework == framework]
        gaps_by_severity: dict[str, int] = {}
        for g in gaps:
            gaps_by_severity[g.severity] = gaps_by_severity.get(g.severity, 0) + 1

        return {
            "total": total,
            "implemented": implemented,
            "coverage_pct": coverage_pct,
            "gaps_by_severity": gaps_by_severity,
        }

    def get_stats(self) -> dict[str, Any]:
        """Return aggregate statistics."""
        controls = list(self._controls.values())
        gaps = list(self._gaps.values())

        frameworks: set[str] = set()
        for c in controls:
            frameworks.add(c.framework)

        severity_dist: dict[str, int] = {}
        status_dist: dict[str, int] = {}
        for g in gaps:
            severity_dist[g.severity] = severity_dist.get(g.severity, 0) + 1
            status_dist[g.status] = status_dist.get(g.status, 0) + 1

        implemented_count = sum(1 for c in controls if c.implemented)
        total = len(controls)
        overall_coverage = round((implemented_count / total) * 100, 2) if total else 0.0

        return {
            "total_controls": total,
            "total_gaps": len(gaps),
            "frameworks_tracked": len(frameworks),
            "overall_coverage_pct": overall_coverage,
            "severity_distribution": severity_dist,
            "status_distribution": status_dist,
        }
