"""SLA Impact Analyzer — track and analyze SLA impact events across services."""

from __future__ import annotations

import time
from enum import StrEnum
from typing import Any
from uuid import uuid4

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ImpactType(StrEnum):
    AVAILABILITY = "availability"
    LATENCY = "latency"
    ERROR_RATE = "error_rate"
    THROUGHPUT = "throughput"
    DATA_LOSS = "data_loss"


class ImpactSeverity(StrEnum):
    CATASTROPHIC = "catastrophic"
    MAJOR = "major"
    MODERATE = "moderate"
    MINOR = "minor"
    NEGLIGIBLE = "negligible"


class SLAStatus(StrEnum):
    HEALTHY = "healthy"
    AT_RISK = "at_risk"
    BREACHED = "breached"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


# --- Models ---


class ImpactRecord(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    service: str = ""
    impact_type: ImpactType = ImpactType.AVAILABILITY
    severity: ImpactSeverity = ImpactSeverity.NEGLIGIBLE
    sla_status: SLAStatus = SLAStatus.UNKNOWN
    impact_score: float = 0.0
    duration_seconds: float = 0.0
    breached: bool = False
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class ImpactContributor(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    contributor_name: str = ""
    impact_type: ImpactType = ImpactType.AVAILABILITY
    severity: ImpactSeverity = ImpactSeverity.NEGLIGIBLE
    contribution_pct: float = 0.0
    service: str = ""
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class SLAImpactReport(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    total_records: int = 0
    total_contributors: int = 0
    breach_count: int = 0
    healthy_count: int = 0
    breach_rate_pct: float = 0.0
    by_impact_type: dict[str, int] = Field(default_factory=dict)
    by_severity: dict[str, int] = Field(default_factory=dict)
    by_sla_status: dict[str, int] = Field(default_factory=dict)
    top_impacted_services: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class SLAImpactAnalyzer:
    """Analyze SLA impact events and identify breach patterns across services."""

    def __init__(
        self,
        max_records: int = 200000,
        max_breach_count: float = 3.0,
    ) -> None:
        self._max_records = max_records
        self._max_breach_count = max_breach_count
        self._records: list[ImpactRecord] = []
        self._contributors: list[ImpactContributor] = []
        logger.info(
            "sla_impact.initialized",
            max_records=max_records,
            max_breach_count=max_breach_count,
        )

    # -- CRUD --

    def record_impact(
        self,
        service: str,
        impact_type: ImpactType = ImpactType.AVAILABILITY,
        severity: ImpactSeverity = ImpactSeverity.NEGLIGIBLE,
        sla_status: SLAStatus = SLAStatus.UNKNOWN,
        impact_score: float = 0.0,
        duration_seconds: float = 0.0,
        breached: bool = False,
        details: str = "",
    ) -> ImpactRecord:
        record = ImpactRecord(
            service=service,
            impact_type=impact_type,
            severity=severity,
            sla_status=sla_status,
            impact_score=impact_score,
            duration_seconds=duration_seconds,
            breached=breached,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "sla_impact.recorded",
            record_id=record.id,
            service=service,
            severity=severity.value,
        )
        return record

    def get_impact(self, record_id: str) -> ImpactRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_impacts(
        self,
        impact_type: ImpactType | None = None,
        severity: ImpactSeverity | None = None,
        sla_status: SLAStatus | None = None,
        limit: int = 50,
    ) -> list[ImpactRecord]:
        results = list(self._records)
        if impact_type is not None:
            results = [r for r in results if r.impact_type == impact_type]
        if severity is not None:
            results = [r for r in results if r.severity == severity]
        if sla_status is not None:
            results = [r for r in results if r.sla_status == sla_status]
        return results[-limit:]

    def add_contributor(
        self,
        contributor_name: str,
        impact_type: ImpactType = ImpactType.AVAILABILITY,
        severity: ImpactSeverity = ImpactSeverity.NEGLIGIBLE,
        contribution_pct: float = 0.0,
        service: str = "",
        description: str = "",
    ) -> ImpactContributor:
        contributor = ImpactContributor(
            contributor_name=contributor_name,
            impact_type=impact_type,
            severity=severity,
            contribution_pct=contribution_pct,
            service=service,
            description=description,
        )
        self._contributors.append(contributor)
        if len(self._contributors) > self._max_records:
            self._contributors = self._contributors[-self._max_records :]
        logger.info(
            "sla_impact.contributor_added",
            contributor_id=contributor.id,
            contributor_name=contributor_name,
            service=service,
        )
        return contributor

    # -- Domain operations --

    def analyze_impact_by_service(self) -> dict[str, Any]:
        """Compute impact metrics grouped by service."""
        service_data: dict[str, dict[str, Any]] = {}
        for r in self._records:
            if not r.service:
                continue
            if r.service not in service_data:
                service_data[r.service] = {"total": 0, "breaches": 0, "scores": []}
            service_data[r.service]["total"] += 1
            service_data[r.service]["scores"].append(r.impact_score)
            if r.breached:
                service_data[r.service]["breaches"] += 1
        breakdown: list[dict[str, Any]] = []
        for service, data in service_data.items():
            scores = data["scores"]
            avg_score = round(sum(scores) / len(scores), 4) if scores else 0.0
            breach_rate = round(data["breaches"] / data["total"] * 100, 2) if data["total"] else 0.0
            breakdown.append(
                {
                    "service": service,
                    "total_events": data["total"],
                    "breach_count": data["breaches"],
                    "breach_rate_pct": breach_rate,
                    "avg_impact_score": avg_score,
                }
            )
        breakdown.sort(key=lambda x: x["breach_count"], reverse=True)
        return {
            "total_services": len(service_data),
            "breakdown": breakdown,
        }

    def identify_sla_breaches(self) -> list[dict[str, Any]]:
        """Return all records where SLA was breached, sorted by severity."""
        severity_order = {
            ImpactSeverity.CATASTROPHIC: 0,
            ImpactSeverity.MAJOR: 1,
            ImpactSeverity.MODERATE: 2,
            ImpactSeverity.MINOR: 3,
            ImpactSeverity.NEGLIGIBLE: 4,
        }
        breached = [r for r in self._records if r.breached]
        breached.sort(key=lambda r: severity_order.get(r.severity, 99))
        return [
            {
                "record_id": r.id,
                "service": r.service,
                "impact_type": r.impact_type.value,
                "severity": r.severity.value,
                "impact_score": r.impact_score,
                "duration_seconds": r.duration_seconds,
            }
            for r in breached
        ]

    def rank_by_impact_severity(self) -> list[dict[str, Any]]:
        """Rank services by average impact score."""
        service_scores: dict[str, list[float]] = {}
        for r in self._records:
            if not r.service:
                continue
            service_scores.setdefault(r.service, []).append(r.impact_score)
        results: list[dict[str, Any]] = []
        for service, scores in service_scores.items():
            avg_score = round(sum(scores) / len(scores), 4) if scores else 0.0
            results.append(
                {
                    "service": service,
                    "avg_impact_score": avg_score,
                    "event_count": len(scores),
                }
            )
        results.sort(key=lambda x: x["avg_impact_score"], reverse=True)
        return results

    def detect_impact_trends(self) -> dict[str, Any]:
        """Detect whether SLA impact is improving or worsening over time."""
        if len(self._records) < 4:
            return {"trend": "insufficient_data", "sample_count": len(self._records)}
        mid = len(self._records) // 2
        first_half = self._records[:mid]
        second_half = self._records[mid:]

        def _breach_rate(records: list[ImpactRecord]) -> float:
            if not records:
                return 0.0
            breaches = sum(1 for r in records if r.breached)
            return round(breaches / len(records) * 100, 2)

        first_rate = _breach_rate(first_half)
        second_rate = _breach_rate(second_half)
        delta = round(second_rate - first_rate, 2)
        if delta > 5.0:
            trend = "worsening"
        elif delta < -5.0:
            trend = "improving"
        else:
            trend = "stable"
        return {
            "trend": trend,
            "first_half_breach_pct": first_rate,
            "second_half_breach_pct": second_rate,
            "delta_pct": delta,
            "total_records": len(self._records),
        }

    # -- Report --

    def generate_report(self) -> SLAImpactReport:
        by_impact_type: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        by_sla_status: dict[str, int] = {}
        for r in self._records:
            by_impact_type[r.impact_type.value] = by_impact_type.get(r.impact_type.value, 0) + 1
            by_severity[r.severity.value] = by_severity.get(r.severity.value, 0) + 1
            by_sla_status[r.sla_status.value] = by_sla_status.get(r.sla_status.value, 0) + 1
        total = len(self._records)
        breach_count = sum(1 for r in self._records if r.breached)
        healthy_count = by_sla_status.get(SLAStatus.HEALTHY.value, 0)
        breach_rate = round(breach_count / total * 100, 2) if total else 0.0
        service_data = self.analyze_impact_by_service()
        top_services = [b["service"] for b in service_data.get("breakdown", [])[:5]]
        recs: list[str] = []
        if breach_count > self._max_breach_count:
            recs.append(
                f"Breach count {breach_count} exceeds max {int(self._max_breach_count)}"
                " — investigate top impacted services"
            )
        if top_services:
            recs.append(
                f"Service '{top_services[0]}' has the most SLA breaches"
                " — prioritize reliability work"
            )
        if not self._contributors:
            recs.append(
                "No impact contributors registered — add contributors for root cause tracking"
            )
        if not recs:
            recs.append("SLA impact is within acceptable thresholds")
        return SLAImpactReport(
            total_records=total,
            total_contributors=len(self._contributors),
            breach_count=breach_count,
            healthy_count=healthy_count,
            breach_rate_pct=breach_rate,
            by_impact_type=by_impact_type,
            by_severity=by_severity,
            by_sla_status=by_sla_status,
            top_impacted_services=top_services,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._contributors.clear()
        logger.info("sla_impact.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        severity_dist: dict[str, int] = {}
        for r in self._records:
            severity_dist[r.severity.value] = severity_dist.get(r.severity.value, 0) + 1
        breach_count = sum(1 for r in self._records if r.breached)
        avg_score = (
            round(sum(r.impact_score for r in self._records) / len(self._records), 4)
            if self._records
            else 0.0
        )
        return {
            "total_records": len(self._records),
            "total_contributors": len(self._contributors),
            "breach_count": breach_count,
            "max_breach_count": self._max_breach_count,
            "avg_impact_score": avg_score,
            "severity_distribution": severity_dist,
            "unique_services": len({r.service for r in self._records if r.service}),
        }
