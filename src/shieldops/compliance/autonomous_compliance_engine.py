"""Autonomous Compliance Engine — autonomous compliance assessment and remediation."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ComplianceAction(StrEnum):
    ASSESS = "assess"
    REMEDIATE = "remediate"
    VERIFY = "verify"
    REPORT = "report"


class FrameworkScope(StrEnum):
    SOC2 = "soc2"
    HIPAA = "hipaa"
    PCI = "pci"
    ISO27001 = "iso27001"


class AutomationLevel(StrEnum):
    MANUAL = "manual"
    ASSISTED = "assisted"
    AUTOMATED = "automated"
    AUTONOMOUS = "autonomous"


# --- Models ---


class ComplianceRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    compliance_action: ComplianceAction = ComplianceAction.ASSESS
    framework_scope: FrameworkScope = FrameworkScope.SOC2
    automation_level: AutomationLevel = AutomationLevel.MANUAL
    score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class ComplianceAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    compliance_action: ComplianceAction = ComplianceAction.ASSESS
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class AutonomousComplianceReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_score: float = 0.0
    by_compliance_action: dict[str, int] = Field(default_factory=dict)
    by_framework_scope: dict[str, int] = Field(default_factory=dict)
    by_automation_level: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class AutonomousComplianceEngine:
    """Autonomous Compliance Engine
    for compliance assessment and remediation.
    """

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[ComplianceRecord] = []
        self._analyses: list[ComplianceAnalysis] = []
        logger.info(
            "autonomous_compliance_engine.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    def add_record(
        self,
        name: str,
        compliance_action: ComplianceAction = (ComplianceAction.ASSESS),
        framework_scope: FrameworkScope = (FrameworkScope.SOC2),
        automation_level: AutomationLevel = (AutomationLevel.MANUAL),
        score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> ComplianceRecord:
        record = ComplianceRecord(
            name=name,
            compliance_action=compliance_action,
            framework_scope=framework_scope,
            automation_level=automation_level,
            score=score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "autonomous_compliance_engine.record_added",
            record_id=record.id,
            name=name,
        )
        return record

    def get_record(self, record_id: str) -> ComplianceRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        compliance_action: ComplianceAction | None = None,
        framework_scope: FrameworkScope | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[ComplianceRecord]:
        results = list(self._records)
        if compliance_action is not None:
            results = [r for r in results if r.compliance_action == compliance_action]
        if framework_scope is not None:
            results = [r for r in results if r.framework_scope == framework_scope]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        name: str,
        compliance_action: ComplianceAction = (ComplianceAction.ASSESS),
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> ComplianceAnalysis:
        analysis = ComplianceAnalysis(
            name=name,
            compliance_action=compliance_action,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "autonomous_compliance_engine.analysis_added",
            name=name,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------

    def auto_assess_controls(
        self,
    ) -> list[dict[str, Any]]:
        """Auto-assess compliance controls per framework."""
        fw_data: dict[str, list[dict[str, Any]]] = {}
        for r in self._records:
            fw_data.setdefault(r.framework_scope.value, []).append(
                {
                    "name": r.name,
                    "score": r.score,
                    "action": r.compliance_action.value,
                    "service": r.service,
                }
            )
        results: list[dict[str, Any]] = []
        for fw, entries in fw_data.items():
            avg = round(sum(e["score"] for e in entries) / len(entries), 2)
            passing = sum(1 for e in entries if e["score"] >= self._threshold)
            results.append(
                {
                    "framework": fw,
                    "total_controls": len(entries),
                    "passing": passing,
                    "failing": len(entries) - passing,
                    "pass_rate": round(passing / len(entries) * 100, 2),
                    "avg_score": avg,
                }
            )
        results.sort(key=lambda x: x["pass_rate"])
        return results

    def generate_remediation_plan(
        self,
    ) -> list[dict[str, Any]]:
        """Generate remediation plan for failing controls."""
        plan: list[dict[str, Any]] = []
        for r in self._records:
            if r.score < self._threshold:
                plan.append(
                    {
                        "record_id": r.id,
                        "name": r.name,
                        "framework": r.framework_scope.value,
                        "current_score": r.score,
                        "gap": round(self._threshold - r.score, 2),
                        "priority": "critical" if r.score < self._threshold * 0.5 else "high",
                        "automation_level": (r.automation_level.value),
                        "service": r.service,
                    }
                )
        plan.sort(key=lambda x: x["current_score"])
        return plan

    def compute_compliance_velocity(
        self,
    ) -> dict[str, Any]:
        """Compute compliance improvement velocity."""
        if len(self._records) < 4:
            return {
                "velocity": 0.0,
                "reason": "insufficient_data",
            }
        mid = len(self._records) // 2
        first = self._records[:mid]
        second = self._records[mid:]
        avg_first = round(sum(r.score for r in first) / len(first), 2)
        avg_second = round(sum(r.score for r in second) / len(second), 2)
        velocity = round(avg_second - avg_first, 2)
        auto_levels: dict[str, int] = {}
        for r in self._records:
            auto_levels[r.automation_level.value] = auto_levels.get(r.automation_level.value, 0) + 1
        return {
            "velocity": velocity,
            "avg_first_half": avg_first,
            "avg_second_half": avg_second,
            "trend": "improving"
            if velocity > 5
            else "stable"
            if abs(velocity) <= 5
            else "declining",
            "automation_distribution": auto_levels,
        }

    # -- report / stats -----------------------------------------------

    def generate_report(
        self,
    ) -> AutonomousComplianceReport:
        by_e1: dict[str, int] = {}
        by_e2: dict[str, int] = {}
        by_e3: dict[str, int] = {}
        for r in self._records:
            by_e1[r.compliance_action.value] = by_e1.get(r.compliance_action.value, 0) + 1
            by_e2[r.framework_scope.value] = by_e2.get(r.framework_scope.value, 0) + 1
            by_e3[r.automation_level.value] = by_e3.get(r.automation_level.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.score < self._threshold)
        scores = [r.score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gaps = [r.name for r in self._records if r.score < self._threshold][:5]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} item(s) below threshold ({self._threshold})")
        if self._records and avg_score < self._threshold:
            recs.append(f"Avg score {avg_score} below threshold ({self._threshold})")
        if not recs:
            recs.append("Autonomous Compliance Engine is healthy")
        return AutonomousComplianceReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_score=avg_score,
            by_compliance_action=by_e1,
            by_framework_scope=by_e2,
            by_automation_level=by_e3,
            top_gaps=gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("autonomous_compliance_engine.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        e1_dist: dict[str, int] = {}
        for r in self._records:
            key = r.compliance_action.value
            e1_dist[key] = e1_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "compliance_action_distribution": e1_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
