"""Regulatory Intelligence Engine
change tracking, impact assessment, gap detection, requirement mapping."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class RegulationType(StrEnum):
    GDPR = "gdpr"
    CCPA = "ccpa"
    HIPAA = "hipaa"
    SOX = "sox"
    PCI_DSS = "pci_dss"


class ChangeImpact(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"


class ComplianceGapStatus(StrEnum):
    OPEN = "open"
    IN_REMEDIATION = "in_remediation"
    CLOSED = "closed"
    DEFERRED = "deferred"
    MONITORING = "monitoring"


# --- Models ---


class RegulatoryRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    regulation_name: str = ""
    regulation_type: RegulationType = RegulationType.GDPR
    change_impact: ChangeImpact = ChangeImpact.MEDIUM
    gap_status: ComplianceGapStatus = ComplianceGapStatus.OPEN
    readiness_score: float = 0.0
    affected_controls: int = 0
    days_until_deadline: int = 0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class RegulatoryAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    regulation_name: str = ""
    regulation_type: RegulationType = RegulationType.GDPR
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class RegulatoryIntelligenceReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_readiness: float = 0.0
    critical_changes: int = 0
    open_gaps: int = 0
    by_regulation_type: dict[str, int] = Field(default_factory=dict)
    by_change_impact: dict[str, int] = Field(default_factory=dict)
    by_gap_status: dict[str, int] = Field(default_factory=dict)
    urgent_regulations: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class RegulatoryIntelligenceEngine:
    """Regulatory change tracking, impact assessment, compliance gap detection
    requirement mapping."""

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 70.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[RegulatoryRecord] = []
        self._analyses: list[RegulatoryAnalysis] = []
        logger.info(
            "regulatory_intelligence_engine.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    # -- record / get / list ------------------------------------------------

    def add_record(
        self,
        regulation_name: str,
        regulation_type: RegulationType = RegulationType.GDPR,
        change_impact: ChangeImpact = ChangeImpact.MEDIUM,
        gap_status: ComplianceGapStatus = ComplianceGapStatus.OPEN,
        readiness_score: float = 0.0,
        affected_controls: int = 0,
        days_until_deadline: int = 0,
        service: str = "",
        team: str = "",
    ) -> RegulatoryRecord:
        record = RegulatoryRecord(
            regulation_name=regulation_name,
            regulation_type=regulation_type,
            change_impact=change_impact,
            gap_status=gap_status,
            readiness_score=readiness_score,
            affected_controls=affected_controls,
            days_until_deadline=days_until_deadline,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "regulatory_intelligence_engine.record_added",
            record_id=record.id,
            regulation_name=regulation_name,
            regulation_type=regulation_type.value,
        )
        return record

    def get_record(self, record_id: str) -> RegulatoryRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        regulation_type: RegulationType | None = None,
        change_impact: ChangeImpact | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[RegulatoryRecord]:
        results = list(self._records)
        if regulation_type is not None:
            results = [r for r in results if r.regulation_type == regulation_type]
        if change_impact is not None:
            results = [r for r in results if r.change_impact == change_impact]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        regulation_name: str,
        regulation_type: RegulationType = RegulationType.GDPR,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> RegulatoryAnalysis:
        analysis = RegulatoryAnalysis(
            regulation_name=regulation_name,
            regulation_type=regulation_type,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "regulatory_intelligence_engine.analysis_added",
            regulation_name=regulation_name,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def assess_impact(self) -> list[dict[str, Any]]:
        impact_weight = {
            ChangeImpact.CRITICAL: 5,
            ChangeImpact.HIGH: 4,
            ChangeImpact.MEDIUM: 3,
            ChangeImpact.LOW: 2,
            ChangeImpact.NONE: 1,
        }
        results: list[dict[str, Any]] = []
        for r in self._records:
            weight = impact_weight.get(r.change_impact, 1)
            urgency = max(0, 1 + (90 - r.days_until_deadline) * 0.01)
            impact_score = round(weight * r.affected_controls * urgency, 2)
            results.append(
                {
                    "regulation_name": r.regulation_name,
                    "regulation_type": r.regulation_type.value,
                    "impact_score": impact_score,
                    "change_impact": r.change_impact.value,
                    "affected_controls": r.affected_controls,
                    "days_until_deadline": r.days_until_deadline,
                }
            )
        return sorted(results, key=lambda x: x["impact_score"], reverse=True)

    def detect_compliance_gaps(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.gap_status in (ComplianceGapStatus.OPEN, ComplianceGapStatus.IN_REMEDIATION):
                results.append(
                    {
                        "regulation_name": r.regulation_name,
                        "regulation_type": r.regulation_type.value,
                        "gap_status": r.gap_status.value,
                        "readiness_score": r.readiness_score,
                        "days_until_deadline": r.days_until_deadline,
                        "affected_controls": r.affected_controls,
                    }
                )
        return sorted(results, key=lambda x: x["readiness_score"])

    def map_requirements(self) -> dict[str, Any]:
        reg_data: dict[str, dict[str, Any]] = {}
        for r in self._records:
            key = r.regulation_type.value
            reg_data.setdefault(key, {"controls": 0, "scores": [], "regulations": set()})
            reg_data[key]["controls"] += r.affected_controls
            reg_data[key]["scores"].append(r.readiness_score)
            reg_data[key]["regulations"].add(r.regulation_name)
        results: dict[str, Any] = {}
        for reg_type, data in reg_data.items():
            scores = data["scores"]
            results[reg_type] = {
                "total_controls": data["controls"],
                "avg_readiness": round(sum(scores) / len(scores), 2) if scores else 0.0,
                "regulation_count": len(data["regulations"]),
            }
        return results

    def identify_approaching_deadlines(self, days_window: int = 30) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for r in self._records:
            if 0 < r.days_until_deadline <= days_window:
                results.append(
                    {
                        "regulation_name": r.regulation_name,
                        "days_until_deadline": r.days_until_deadline,
                        "readiness_score": r.readiness_score,
                        "gap_status": r.gap_status.value,
                        "change_impact": r.change_impact.value,
                    }
                )
        return sorted(results, key=lambda x: x["days_until_deadline"])

    def detect_trends(self) -> dict[str, Any]:
        if len(self._analyses) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [a.analysis_score for a in self._analyses]
        mid = len(vals) // 2
        first_half = vals[:mid]
        second_half = vals[mid:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        delta = round(avg_second - avg_first, 2)
        if abs(delta) < 5.0:
            trend = "stable"
        elif delta > 0:
            trend = "improving"
        else:
            trend = "degrading"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def process(self, regulation_name: str) -> dict[str, Any]:
        matching = [r for r in self._records if r.regulation_name == regulation_name]
        if not matching:
            return {"regulation_name": regulation_name, "status": "no_data"}
        scores = [r.readiness_score for r in matching]
        controls = sum(r.affected_controls for r in matching)
        return {
            "regulation_name": regulation_name,
            "record_count": len(matching),
            "avg_readiness": round(sum(scores) / len(scores), 2),
            "total_affected_controls": controls,
            "latest_gap_status": matching[-1].gap_status.value,
        }

    def generate_report(self) -> RegulatoryIntelligenceReport:
        by_rt: dict[str, int] = {}
        by_ci: dict[str, int] = {}
        by_gs: dict[str, int] = {}
        for r in self._records:
            by_rt[r.regulation_type.value] = by_rt.get(r.regulation_type.value, 0) + 1
            by_ci[r.change_impact.value] = by_ci.get(r.change_impact.value, 0) + 1
            by_gs[r.gap_status.value] = by_gs.get(r.gap_status.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.readiness_score < self._threshold)
        scores = [r.readiness_score for r in self._records]
        avg_readiness = round(sum(scores) / len(scores), 2) if scores else 0.0
        critical = sum(1 for r in self._records if r.change_impact == ChangeImpact.CRITICAL)
        open_gaps = by_gs.get("open", 0)
        approaching = self.identify_approaching_deadlines()
        urgent = [a["regulation_name"] for a in approaching[:5]]
        recs: list[str] = []
        if gap_count > 0:
            recs.append(f"{gap_count} regulation(s) below readiness threshold ({self._threshold})")
        if critical > 0:
            recs.append(f"{critical} critical-impact regulatory change(s) require attention")
        if approaching:
            recs.append(f"{len(approaching)} regulation(s) with deadlines within 30 days")
        if open_gaps > 0:
            recs.append(f"{open_gaps} open compliance gap(s) — begin remediation")
        if not recs:
            recs.append("Regulatory intelligence posture is healthy")
        return RegulatoryIntelligenceReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_readiness=avg_readiness,
            critical_changes=critical,
            open_gaps=open_gaps,
            by_regulation_type=by_rt,
            by_change_impact=by_ci,
            by_gap_status=by_gs,
            urgent_regulations=urgent,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        rt_dist: dict[str, int] = {}
        for r in self._records:
            key = r.regulation_type.value
            rt_dist[key] = rt_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "regulation_type_distribution": rt_dist,
            "unique_regulations": len({r.regulation_name for r in self._records}),
            "unique_teams": len({r.team for r in self._records}),
        }

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("regulatory_intelligence_engine.cleared")
        return {"status": "cleared"}
