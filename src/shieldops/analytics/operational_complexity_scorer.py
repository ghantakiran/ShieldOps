"""Operational Complexity Scorer — complexity scoring and simplification."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ComplexityDimension(StrEnum):
    ARCHITECTURAL = "architectural"
    OPERATIONAL = "operational"
    ORGANIZATIONAL = "organizational"
    TECHNICAL = "technical"


class ComplexityDriver(StrEnum):
    DEPENDENCIES = "dependencies"
    SCALE = "scale"
    HETEROGENEITY = "heterogeneity"
    CHANGE_RATE = "change_rate"


class RiskImpact(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"


# --- Models ---


class ComplexityRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    complexity_dimension: ComplexityDimension = ComplexityDimension.TECHNICAL
    complexity_driver: ComplexityDriver = ComplexityDriver.DEPENDENCIES
    risk_impact: RiskImpact = RiskImpact.MODERATE
    score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class ComplexityAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    complexity_dimension: ComplexityDimension = ComplexityDimension.TECHNICAL
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class OperationalComplexityReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_score: float = 0.0
    by_complexity_dimension: dict[str, int] = Field(default_factory=dict)
    by_complexity_driver: dict[str, int] = Field(default_factory=dict)
    by_risk_impact: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class OperationalComplexityScorer:
    """Operational Complexity Scorer
    for complexity scoring and simplification.
    """

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[ComplexityRecord] = []
        self._analyses: list[ComplexityAnalysis] = []
        logger.info(
            "operational_complexity_scorer.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    def add_record(
        self,
        name: str,
        complexity_dimension: ComplexityDimension = (ComplexityDimension.TECHNICAL),
        complexity_driver: ComplexityDriver = (ComplexityDriver.DEPENDENCIES),
        risk_impact: RiskImpact = RiskImpact.MODERATE,
        score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> ComplexityRecord:
        record = ComplexityRecord(
            name=name,
            complexity_dimension=complexity_dimension,
            complexity_driver=complexity_driver,
            risk_impact=risk_impact,
            score=score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "operational_complexity_scorer.record_added",
            record_id=record.id,
            name=name,
        )
        return record

    def get_record(self, record_id: str) -> ComplexityRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        complexity_dimension: (ComplexityDimension | None) = None,
        risk_impact: RiskImpact | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[ComplexityRecord]:
        results = list(self._records)
        if complexity_dimension is not None:
            results = [r for r in results if r.complexity_dimension == complexity_dimension]
        if risk_impact is not None:
            results = [r for r in results if r.risk_impact == risk_impact]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        name: str,
        complexity_dimension: ComplexityDimension = (ComplexityDimension.TECHNICAL),
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> ComplexityAnalysis:
        analysis = ComplexityAnalysis(
            name=name,
            complexity_dimension=complexity_dimension,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "operational_complexity_scorer.analysis_added",
            name=name,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------

    def compute_complexity_score(
        self,
    ) -> dict[str, Any]:
        """Compute aggregate complexity scores."""
        dim_data: dict[str, list[float]] = {}
        for r in self._records:
            dim_data.setdefault(r.complexity_dimension.value, []).append(r.score)
        impact_weight = {
            "critical": 4.0,
            "high": 3.0,
            "moderate": 2.0,
            "low": 1.0,
        }
        weighted_total = 0.0
        weight_sum = 0.0
        for r in self._records:
            w = impact_weight.get(r.risk_impact.value, 1.0)
            weighted_total += r.score * w
            weight_sum += w
        overall = round(weighted_total / weight_sum, 2) if weight_sum > 0 else 0.0
        by_dim: dict[str, Any] = {}
        for dim, scores in dim_data.items():
            by_dim[dim] = {
                "count": len(scores),
                "avg_score": round(sum(scores) / len(scores), 2),
            }
        return {
            "overall_complexity": overall,
            "by_dimension": by_dim,
            "total_records": len(self._records),
        }

    def identify_complexity_hotspots(
        self,
    ) -> list[dict[str, Any]]:
        """Identify services with highest complexity."""
        svc_data: dict[str, list[dict[str, Any]]] = {}
        for r in self._records:
            svc_data.setdefault(r.service, []).append(
                {
                    "score": r.score,
                    "dimension": r.complexity_dimension.value,
                    "driver": r.complexity_driver.value,
                    "impact": r.risk_impact.value,
                }
            )
        hotspots: list[dict[str, Any]] = []
        for svc, entries in svc_data.items():
            avg = round(sum(e["score"] for e in entries) / len(entries), 2)
            dims = {e["dimension"] for e in entries}
            drivers = {e["driver"] for e in entries}
            hotspots.append(
                {
                    "service": svc,
                    "avg_complexity": avg,
                    "dimension_count": len(dims),
                    "driver_count": len(drivers),
                    "record_count": len(entries),
                    "is_hotspot": avg > self._threshold,
                }
            )
        hotspots.sort(
            key=lambda x: x["avg_complexity"],
            reverse=True,
        )
        return hotspots

    def recommend_simplification(
        self,
    ) -> list[dict[str, Any]]:
        """Recommend simplification actions."""
        driver_data: dict[str, list[float]] = {}
        for r in self._records:
            driver_data.setdefault(r.complexity_driver.value, []).append(r.score)
        recs: list[dict[str, Any]] = []
        for driver, scores in driver_data.items():
            avg = round(sum(scores) / len(scores), 2)
            if avg > self._threshold:
                recs.append(
                    {
                        "driver": driver,
                        "avg_complexity": avg,
                        "affected_count": len(scores),
                        "recommendation": (f"Reduce {driver} complexity (avg {avg})"),
                        "priority": "high" if avg > self._threshold * 1.5 else "medium",
                    }
                )
        recs.sort(
            key=lambda x: x["avg_complexity"],
            reverse=True,
        )
        return recs

    # -- report / stats -----------------------------------------------

    def generate_report(
        self,
    ) -> OperationalComplexityReport:
        by_e1: dict[str, int] = {}
        by_e2: dict[str, int] = {}
        by_e3: dict[str, int] = {}
        for r in self._records:
            by_e1[r.complexity_dimension.value] = by_e1.get(r.complexity_dimension.value, 0) + 1
            by_e2[r.complexity_driver.value] = by_e2.get(r.complexity_driver.value, 0) + 1
            by_e3[r.risk_impact.value] = by_e3.get(r.risk_impact.value, 0) + 1
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
            recs.append("Operational Complexity Scorer is healthy")
        return OperationalComplexityReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_score=avg_score,
            by_complexity_dimension=by_e1,
            by_complexity_driver=by_e2,
            by_risk_impact=by_e3,
            top_gaps=gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("operational_complexity_scorer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        e1_dist: dict[str, int] = {}
        for r in self._records:
            key = r.complexity_dimension.value
            e1_dist[key] = e1_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "complexity_dimension_distribution": e1_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
