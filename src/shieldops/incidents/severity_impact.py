"""Severity Impact Analyzer — analyze blast radius per severity level."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ImpactDimension(StrEnum):
    REVENUE = "revenue"
    CUSTOMER_EXPERIENCE = "customer_experience"
    OPERATIONAL_CAPACITY = "operational_capacity"
    DATA_INTEGRITY = "data_integrity"
    REPUTATION = "reputation"


class ImpactSeverity(StrEnum):
    CATASTROPHIC = "catastrophic"
    SEVERE = "severe"
    SIGNIFICANT = "significant"
    MODERATE = "moderate"
    MINOR = "minor"


class ImpactScope(StrEnum):
    PLATFORM_WIDE = "platform_wide"
    MULTI_SERVICE = "multi_service"
    SINGLE_SERVICE = "single_service"
    SINGLE_COMPONENT = "single_component"
    ISOLATED = "isolated"


# --- Models ---


class SeverityImpactRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str = ""
    impact_dimension: ImpactDimension = ImpactDimension.REVENUE
    impact_severity: ImpactSeverity = ImpactSeverity.MINOR
    impact_scope: ImpactScope = ImpactScope.ISOLATED
    impact_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class ImpactCorrelation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str = ""
    impact_dimension: ImpactDimension = ImpactDimension.REVENUE
    correlation_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class SeverityImpactReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_correlations: int = 0
    high_impact_count: int = 0
    avg_impact_score: float = 0.0
    by_dimension: dict[str, int] = Field(default_factory=dict)
    by_severity: dict[str, int] = Field(default_factory=dict)
    by_scope: dict[str, int] = Field(default_factory=dict)
    top_impacted: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class SeverityImpactAnalyzer:
    """Analyze blast radius per severity level, map severity-to-business-impact correlations."""

    def __init__(
        self,
        max_records: int = 200000,
        max_high_impact_pct: float = 15.0,
    ) -> None:
        self._max_records = max_records
        self._max_high_impact_pct = max_high_impact_pct
        self._records: list[SeverityImpactRecord] = []
        self._correlations: list[ImpactCorrelation] = []
        logger.info(
            "severity_impact.initialized",
            max_records=max_records,
            max_high_impact_pct=max_high_impact_pct,
        )

    # -- record / get / list ------------------------------------------------

    def record_impact(
        self,
        incident_id: str,
        impact_dimension: ImpactDimension = ImpactDimension.REVENUE,
        impact_severity: ImpactSeverity = ImpactSeverity.MINOR,
        impact_scope: ImpactScope = ImpactScope.ISOLATED,
        impact_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> SeverityImpactRecord:
        record = SeverityImpactRecord(
            incident_id=incident_id,
            impact_dimension=impact_dimension,
            impact_severity=impact_severity,
            impact_scope=impact_scope,
            impact_score=impact_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "severity_impact.impact_recorded",
            record_id=record.id,
            incident_id=incident_id,
            impact_dimension=impact_dimension.value,
            impact_severity=impact_severity.value,
        )
        return record

    def get_impact(self, record_id: str) -> SeverityImpactRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_impacts(
        self,
        dimension: ImpactDimension | None = None,
        severity: ImpactSeverity | None = None,
        service: str | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[SeverityImpactRecord]:
        results = list(self._records)
        if dimension is not None:
            results = [r for r in results if r.impact_dimension == dimension]
        if severity is not None:
            results = [r for r in results if r.impact_severity == severity]
        if service is not None:
            results = [r for r in results if r.service == service]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_correlation(
        self,
        incident_id: str,
        impact_dimension: ImpactDimension = ImpactDimension.REVENUE,
        correlation_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> ImpactCorrelation:
        correlation = ImpactCorrelation(
            incident_id=incident_id,
            impact_dimension=impact_dimension,
            correlation_score=correlation_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._correlations.append(correlation)
        if len(self._correlations) > self._max_records:
            self._correlations = self._correlations[-self._max_records :]
        logger.info(
            "severity_impact.correlation_added",
            incident_id=incident_id,
            impact_dimension=impact_dimension.value,
            correlation_score=correlation_score,
        )
        return correlation

    # -- domain operations --------------------------------------------------

    def analyze_impact_distribution(self) -> dict[str, Any]:
        """Group by impact_dimension; return count and avg impact_score."""
        dim_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.impact_dimension.value
            dim_data.setdefault(key, []).append(r.impact_score)
        result: dict[str, Any] = {}
        for dim, scores in dim_data.items():
            result[dim] = {
                "count": len(scores),
                "avg_impact_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_high_impact_incidents(self) -> list[dict[str, Any]]:
        """Return records where severity is CATASTROPHIC or SEVERE."""
        high_severities = {ImpactSeverity.CATASTROPHIC, ImpactSeverity.SEVERE}
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.impact_severity in high_severities:
                results.append(
                    {
                        "record_id": r.id,
                        "incident_id": r.incident_id,
                        "impact_dimension": r.impact_dimension.value,
                        "impact_severity": r.impact_severity.value,
                        "impact_scope": r.impact_scope.value,
                        "impact_score": r.impact_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_impact_score(self) -> list[dict[str, Any]]:
        """Group by service, avg impact_score, sort descending."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.impact_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_impact_score": round(sum(scores) / len(scores), 2),
                    "record_count": len(scores),
                }
            )
        results.sort(key=lambda x: x["avg_impact_score"], reverse=True)
        return results

    def detect_impact_trends(self) -> dict[str, Any]:
        """Split-half comparison on correlation_score; delta threshold 5.0."""
        if len(self._correlations) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        scores = [c.correlation_score for c in self._correlations]
        mid = len(scores) // 2
        first_half = scores[:mid]
        second_half = scores[mid:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        delta = round(avg_second - avg_first, 2)
        if abs(delta) < 5.0:
            trend = "stable"
        elif delta > 0:
            trend = "increasing"
        else:
            trend = "decreasing"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> SeverityImpactReport:
        by_dimension: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        by_scope: dict[str, int] = {}
        for r in self._records:
            by_dimension[r.impact_dimension.value] = (
                by_dimension.get(r.impact_dimension.value, 0) + 1
            )
            by_severity[r.impact_severity.value] = by_severity.get(r.impact_severity.value, 0) + 1
            by_scope[r.impact_scope.value] = by_scope.get(r.impact_scope.value, 0) + 1
        high_impact = self.identify_high_impact_incidents()
        high_impact_count = len(high_impact)
        avg_impact_score = (
            round(sum(r.impact_score for r in self._records) / len(self._records), 2)
            if self._records
            else 0.0
        )
        rankings = self.rank_by_impact_score()
        top_impacted = [rk["service"] for rk in rankings[:5]]
        recs: list[str] = []
        if high_impact_count > 0:
            recs.append(
                f"{high_impact_count} high-impact incident(s) detected — review blast radius"
            )
        if self._records:
            high_pct = round(high_impact_count / len(self._records) * 100, 2)
            if high_pct > self._max_high_impact_pct:
                recs.append(
                    f"High-impact rate {high_pct}% exceeds threshold ({self._max_high_impact_pct}%)"
                )
        if not recs:
            recs.append("Severity impact levels are acceptable")
        return SeverityImpactReport(
            total_records=len(self._records),
            total_correlations=len(self._correlations),
            high_impact_count=high_impact_count,
            avg_impact_score=avg_impact_score,
            by_dimension=by_dimension,
            by_severity=by_severity,
            by_scope=by_scope,
            top_impacted=top_impacted,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._correlations.clear()
        logger.info("severity_impact.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        dim_dist: dict[str, int] = {}
        for r in self._records:
            key = r.impact_dimension.value
            dim_dist[key] = dim_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_correlations": len(self._correlations),
            "max_high_impact_pct": self._max_high_impact_pct,
            "dimension_distribution": dim_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
