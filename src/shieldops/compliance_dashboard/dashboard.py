"""Compliance Dashboard — aggregation, filtering, reporting."""

from __future__ import annotations

import time
from typing import Any

import structlog

from shieldops.compliance_dashboard.evidence_collector import (
    EvidenceCollector,
)
from shieldops.compliance_dashboard.models import (
    ComplianceControl,
    ComplianceFramework,
    ComplianceSummary,
    ControlStatus,
)
from shieldops.compliance_dashboard.soc2_mapper import SOC2Mapper

logger = structlog.get_logger()


class ComplianceDashboard:
    """Aggregates compliance posture across frameworks."""

    def __init__(self) -> None:
        self._soc2_mapper = SOC2Mapper()
        self._evidence_collector = EvidenceCollector()
        # Posture snapshots keyed by (framework, timestamp).
        self._timeline: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    @property
    def soc2_mapper(self) -> SOC2Mapper:
        return self._soc2_mapper

    @property
    def evidence_collector(self) -> EvidenceCollector:
        return self._evidence_collector

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    async def get_summary(self, framework: ComplianceFramework) -> ComplianceSummary:
        """Return a posture summary for the given framework."""
        controls = self._controls_for(framework)
        total = len(controls)
        compliant = sum(1 for c in controls if c.status == ControlStatus.COMPLIANT)
        non_compliant = sum(1 for c in controls if c.status == ControlStatus.NON_COMPLIANT)
        partial = sum(1 for c in controls if c.status == ControlStatus.PARTIAL)
        not_assessed = sum(1 for c in controls if c.status == ControlStatus.NOT_ASSESSED)
        pct = round(compliant / total * 100, 2) if total else 0.0

        assessed_ts = [c.last_assessed for c in controls if c.last_assessed is not None]
        last_full = min(assessed_ts) if assessed_ts else None

        # Simple risk: higher = worse.  Weight non-compliant
        # heavily, partial less so.
        risk = round(
            (non_compliant * 10 + partial * 5 + not_assessed * 3) / max(total, 1),
            2,
        )

        summary = ComplianceSummary(
            framework=framework,
            total_controls=total,
            compliant=compliant,
            non_compliant=non_compliant,
            partial=partial,
            not_assessed=not_assessed,
            compliance_percentage=pct,
            last_full_assessment=last_full,
            risk_score=risk,
        )

        # Record snapshot for timeline.
        self._timeline.append(
            {
                "framework": framework,
                "timestamp": time.time(),
                "summary": summary.model_dump(),
            }
        )

        logger.info(
            "compliance_dashboard.summary",
            framework=framework,
            compliance_pct=pct,
            risk_score=risk,
        )
        return summary

    # ------------------------------------------------------------------
    # Filtered controls
    # ------------------------------------------------------------------

    async def get_controls(
        self,
        framework: ComplianceFramework,
        status_filter: ControlStatus | None = None,
        category_filter: str | None = None,
    ) -> list[ComplianceControl]:
        """Return controls with optional status/category filters."""
        controls = self._controls_for(framework)

        if status_filter is not None:
            controls = [c for c in controls if c.status == status_filter]
        if category_filter is not None:
            controls = [c for c in controls if c.category.lower() == category_filter.lower()]

        logger.info(
            "compliance_dashboard.get_controls",
            framework=framework,
            status_filter=status_filter,
            category_filter=category_filter,
            count=len(controls),
        )
        return controls

    # ------------------------------------------------------------------
    # Timeline
    # ------------------------------------------------------------------

    async def get_timeline(
        self,
        framework: ComplianceFramework | None = None,
    ) -> list[dict[str, Any]]:
        """Return compliance posture snapshots over time."""
        entries = self._timeline
        if framework is not None:
            entries = [e for e in entries if e["framework"] == framework]
        return entries

    # ------------------------------------------------------------------
    # Report export
    # ------------------------------------------------------------------

    async def export_report(
        self,
        framework: ComplianceFramework,
        fmt: str = "markdown",
    ) -> str:
        """Generate a compliance report.

        Supported formats: ``markdown`` (default), ``json``.
        """
        summary = await self.get_summary(framework)
        controls = self._controls_for(framework)

        if fmt == "json":
            import json

            payload = {
                "summary": summary.model_dump(),
                "controls": [c.model_dump() for c in controls],
            }
            return json.dumps(payload, indent=2)

        # Markdown (default)
        lines: list[str] = [
            f"# Compliance Report — {framework.value.upper()}",
            "",
            f"**Generated:** {time.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## Summary",
            "",
            "| Metric | Value |",
            "|--------|-------|",
            f"| Total Controls | {summary.total_controls} |",
            f"| Compliant | {summary.compliant} |",
            f"| Non-Compliant | {summary.non_compliant} |",
            f"| Partial | {summary.partial} |",
            f"| Not Assessed | {summary.not_assessed} |",
            (f"| Compliance % | {summary.compliance_percentage}% |"),
            f"| Risk Score | {summary.risk_score} |",
            "",
            "## Controls",
            "",
        ]

        for ctrl in controls:
            lines.append(f"### {ctrl.control_id} — {ctrl.title}")
            lines.append("")
            lines.append(f"**Status:** {ctrl.status.value}")
            lines.append(f"**Category:** {ctrl.category}")
            lines.append(f"**Description:** {ctrl.description}")
            if ctrl.notes:
                lines.append(f"**Notes:** {ctrl.notes}")
            if ctrl.remediation_steps:
                lines.append("**Remediation:**")
                for step in ctrl.remediation_steps:
                    lines.append(f"- {step}")
            lines.append("")

        report = "\n".join(lines)
        logger.info(
            "compliance_dashboard.report_exported",
            framework=framework,
            format=fmt,
            length=len(report),
        )
        return report

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _controls_for(self, framework: ComplianceFramework) -> list[ComplianceControl]:
        """Retrieve controls for the given framework.

        Currently only SOC2 is pre-populated; other frameworks
        return an empty list until their mappers are added.
        """
        if framework == ComplianceFramework.SOC2:
            return self._soc2_mapper.list_controls()
        return []
