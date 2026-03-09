"""OperationalRiskIntelligence
Operational risk scoring, risk trend analysis, mitigation tracking, risk heat maps."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class RiskDomain(StrEnum):
    AVAILABILITY = "availability"
    SECURITY = "security"
    COMPLIANCE = "compliance"
    PERFORMANCE = "performance"
    COST = "cost"
    OPERATIONAL = "operational"


class RiskSeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    ACCEPTED = "accepted"


class MitigationStatus(StrEnum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    MITIGATED = "mitigated"
    ACCEPTED = "accepted"
    TRANSFERRED = "transferred"


# --- Models ---


class OperationalRiskRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    risk_domain: RiskDomain = RiskDomain.OPERATIONAL
    risk_severity: RiskSeverity = RiskSeverity.MEDIUM
    mitigation_status: MitigationStatus = MitigationStatus.NOT_STARTED
    risk_score: float = 0.0
    likelihood_pct: float = 0.0
    impact_score: float = 0.0
    residual_risk: float = 0.0
    mitigation_effectiveness_pct: float = 0.0
    days_open: int = 0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class OperationalRiskAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    risk_domain: RiskDomain = RiskDomain.OPERATIONAL
    analysis_score: float = 0.0
    aggregate_risk_score: float = 0.0
    open_risks: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class OperationalRiskReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_risk_score: float = 0.0
    critical_count: int = 0
    unmitigated_count: int = 0
    avg_days_open: float = 0.0
    by_domain: dict[str, int] = Field(default_factory=dict)
    by_severity: dict[str, int] = Field(default_factory=dict)
    by_mitigation: dict[str, int] = Field(default_factory=dict)
    risk_heat_map: dict[str, float] = Field(default_factory=dict)
    top_risks: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class OperationalRiskIntelligence:
    """Operational risk scoring with trend analysis, mitigation tracking, and heat maps."""

    SEVERITY_WEIGHTS: dict[str, float] = {
        "critical": 100.0,
        "high": 75.0,
        "medium": 50.0,
        "low": 25.0,
        "accepted": 10.0,
    }

    def __init__(
        self,
        max_records: int = 200000,
        risk_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._risk_threshold = risk_threshold
        self._records: list[OperationalRiskRecord] = []
        self._analyses: list[OperationalRiskAnalysis] = []
        logger.info(
            "operational.risk.intelligence.initialized",
            max_records=max_records,
            risk_threshold=risk_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_item(
        self,
        name: str,
        risk_domain: RiskDomain = RiskDomain.OPERATIONAL,
        risk_severity: RiskSeverity = RiskSeverity.MEDIUM,
        mitigation_status: MitigationStatus = MitigationStatus.NOT_STARTED,
        risk_score: float = 0.0,
        likelihood_pct: float = 0.0,
        impact_score: float = 0.0,
        residual_risk: float = 0.0,
        mitigation_effectiveness_pct: float = 0.0,
        days_open: int = 0,
        service: str = "",
        team: str = "",
    ) -> OperationalRiskRecord:
        record = OperationalRiskRecord(
            name=name,
            risk_domain=risk_domain,
            risk_severity=risk_severity,
            mitigation_status=mitigation_status,
            risk_score=risk_score,
            likelihood_pct=likelihood_pct,
            impact_score=impact_score,
            residual_risk=residual_risk,
            mitigation_effectiveness_pct=mitigation_effectiveness_pct,
            days_open=days_open,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "operational.risk.intelligence.item_recorded",
            record_id=record.id,
            name=name,
            risk_domain=risk_domain.value,
            risk_severity=risk_severity.value,
        )
        return record

    def get_record(self, record_id: str) -> OperationalRiskRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        risk_domain: RiskDomain | None = None,
        risk_severity: RiskSeverity | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[OperationalRiskRecord]:
        results = list(self._records)
        if risk_domain is not None:
            results = [r for r in results if r.risk_domain == risk_domain]
        if risk_severity is not None:
            results = [r for r in results if r.risk_severity == risk_severity]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        name: str,
        risk_domain: RiskDomain = RiskDomain.OPERATIONAL,
        analysis_score: float = 0.0,
        aggregate_risk_score: float = 0.0,
        open_risks: int = 0,
        description: str = "",
    ) -> OperationalRiskAnalysis:
        analysis = OperationalRiskAnalysis(
            name=name,
            risk_domain=risk_domain,
            analysis_score=analysis_score,
            aggregate_risk_score=aggregate_risk_score,
            open_risks=open_risks,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "operational.risk.intelligence.analysis_added",
            name=name,
            risk_domain=risk_domain.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def calculate_risk_scores(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for r in self._records:
            severity_weight = self.SEVERITY_WEIGHTS.get(r.risk_severity.value, 50.0)
            composite_score = round(
                (r.likelihood_pct / 100 * r.impact_score * severity_weight / 100), 2
            )
            results.append(
                {
                    "record_id": r.id,
                    "name": r.name,
                    "risk_domain": r.risk_domain.value,
                    "composite_risk_score": composite_score,
                    "likelihood": r.likelihood_pct,
                    "impact": r.impact_score,
                    "severity_weight": severity_weight,
                    "mitigation_status": r.mitigation_status.value,
                }
            )
        return sorted(results, key=lambda x: x["composite_risk_score"], reverse=True)

    def generate_heat_map(self) -> dict[str, Any]:
        domain_scores: dict[str, list[float]] = {}
        for r in self._records:
            domain_scores.setdefault(r.risk_domain.value, []).append(r.risk_score)
        heat_map: dict[str, Any] = {}
        for domain, scores in domain_scores.items():
            avg = round(sum(scores) / len(scores), 2)
            heat_map[domain] = {
                "avg_risk_score": avg,
                "risk_count": len(scores),
                "max_risk_score": round(max(scores), 2),
                "heat_level": "critical"
                if avg > 75
                else ("high" if avg > 50 else ("medium" if avg > 25 else "low")),
            }
        return heat_map

    def track_mitigation_progress(self) -> dict[str, Any]:
        status_counts: dict[str, int] = {}
        mitigated_effectiveness: list[float] = []
        for r in self._records:
            status_counts[r.mitigation_status.value] = (
                status_counts.get(r.mitigation_status.value, 0) + 1
            )
            if r.mitigation_status == MitigationStatus.MITIGATED:
                mitigated_effectiveness.append(r.mitigation_effectiveness_pct)
        total = len(self._records)
        mitigated = status_counts.get("mitigated", 0)
        avg_effectiveness = (
            round(sum(mitigated_effectiveness) / len(mitigated_effectiveness), 2)
            if mitigated_effectiveness
            else 0.0
        )
        return {
            "mitigation_rate": round(mitigated / total * 100, 2) if total else 0.0,
            "by_status": status_counts,
            "avg_mitigation_effectiveness": avg_effectiveness,
            "open_risks": total - mitigated - status_counts.get("accepted", 0),
        }

    def detect_trends(self) -> dict[str, Any]:
        if len(self._analyses) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [a.analysis_score for a in self._analyses]
        mid = len(vals) // 2
        avg_first = sum(vals[:mid]) / len(vals[:mid])
        avg_second = sum(vals[mid:]) / len(vals[mid:])
        delta = round(avg_second - avg_first, 2)
        trend = "stable" if abs(delta) < 5.0 else ("improving" if delta > 0 else "degrading")
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> OperationalRiskReport:
        by_domain: dict[str, int] = {}
        by_sev: dict[str, int] = {}
        by_mit: dict[str, int] = {}
        for r in self._records:
            by_domain[r.risk_domain.value] = by_domain.get(r.risk_domain.value, 0) + 1
            by_sev[r.risk_severity.value] = by_sev.get(r.risk_severity.value, 0) + 1
            by_mit[r.mitigation_status.value] = by_mit.get(r.mitigation_status.value, 0) + 1
        scores = [r.risk_score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        critical = sum(1 for r in self._records if r.risk_severity == RiskSeverity.CRITICAL)
        unmitigated = sum(
            1
            for r in self._records
            if r.mitigation_status in (MitigationStatus.NOT_STARTED, MitigationStatus.IN_PROGRESS)
        )
        days = [r.days_open for r in self._records]
        avg_days = round(sum(days) / len(days), 2) if days else 0.0
        heat_map_data = self.generate_heat_map()
        risk_heat_map = {k: v["avg_risk_score"] for k, v in heat_map_data.items()}
        scored = self.calculate_risk_scores()
        top_risks = [s["name"] for s in scored[:5]]
        recs: list[str] = []
        if critical > 0:
            recs.append(f"{critical} critical risk(s) require immediate attention")
        if unmitigated > 0:
            recs.append(f"{unmitigated} risk(s) have no mitigation in place")
        if avg_days > 90:
            recs.append(f"Avg risk age {avg_days} days — accelerate mitigation timelines")
        if avg_score > self._risk_threshold:
            recs.append(f"Avg risk score {avg_score} exceeds threshold {self._risk_threshold}")
        if not recs:
            recs.append("Operational risk posture is healthy — risks well-managed")
        return OperationalRiskReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_risk_score=avg_score,
            critical_count=critical,
            unmitigated_count=unmitigated,
            avg_days_open=avg_days,
            by_domain=by_domain,
            by_severity=by_sev,
            by_mitigation=by_mit,
            risk_heat_map=risk_heat_map,
            top_risks=top_risks,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("operational.risk.intelligence.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        domain_dist: dict[str, int] = {}
        for r in self._records:
            domain_dist[r.risk_domain.value] = domain_dist.get(r.risk_domain.value, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "risk_threshold": self._risk_threshold,
            "domain_distribution": domain_dist,
            "unique_services": len({r.service for r in self._records}),
            "unique_teams": len({r.team for r in self._records}),
        }
