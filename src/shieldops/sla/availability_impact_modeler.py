"""Availability Impact Modeler — model SLA impact of availability incidents."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ImpactDuration(StrEnum):
    MINUTES = "minutes"
    HOURS = "hours"
    HALF_DAY = "half_day"
    FULL_DAY = "full_day"
    MULTI_DAY = "multi_day"


class SeverityTier(StrEnum):
    P1 = "p1"
    P2 = "p2"
    P3 = "p3"
    P4 = "p4"
    P5 = "p5"


class ModelingApproach(StrEnum):
    HISTORICAL = "historical"
    SIMULATION = "simulation"
    STATISTICAL = "statistical"
    ML_BASED = "ml_based"
    EXPERT = "expert"


# --- Models ---


class AvailabilityImpact(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    impact_duration: ImpactDuration = ImpactDuration.MINUTES
    severity_tier: SeverityTier = SeverityTier.P3
    modeling_approach: ModelingApproach = ModelingApproach.HISTORICAL
    score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class ImpactAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    impact_duration: ImpactDuration = ImpactDuration.MINUTES
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class AvailabilityImpactReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_score: float = 0.0
    by_duration: dict[str, int] = Field(default_factory=dict)
    by_severity: dict[str, int] = Field(default_factory=dict)
    by_approach: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class AvailabilityImpactModeler:
    """Model SLA impact of availability events using multi-approach modeling."""

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[AvailabilityImpact] = []
        self._analyses: list[ImpactAnalysis] = []
        logger.info(
            "availability_impact_modeler.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_impact(
        self,
        service: str,
        impact_duration: ImpactDuration = ImpactDuration.MINUTES,
        severity_tier: SeverityTier = SeverityTier.P3,
        modeling_approach: ModelingApproach = ModelingApproach.HISTORICAL,
        score: float = 0.0,
        team: str = "",
    ) -> AvailabilityImpact:
        record = AvailabilityImpact(
            impact_duration=impact_duration,
            severity_tier=severity_tier,
            modeling_approach=modeling_approach,
            score=score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "availability_impact_modeler.impact_recorded",
            record_id=record.id,
            service=service,
            impact_duration=impact_duration.value,
            severity_tier=severity_tier.value,
        )
        return record

    def get_impact(self, record_id: str) -> AvailabilityImpact | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_impacts(
        self,
        impact_duration: ImpactDuration | None = None,
        severity_tier: SeverityTier | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[AvailabilityImpact]:
        results = list(self._records)
        if impact_duration is not None:
            results = [r for r in results if r.impact_duration == impact_duration]
        if severity_tier is not None:
            results = [r for r in results if r.severity_tier == severity_tier]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        impact_duration: ImpactDuration = ImpactDuration.MINUTES,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> ImpactAnalysis:
        analysis = ImpactAnalysis(
            impact_duration=impact_duration,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "availability_impact_modeler.analysis_added",
            impact_duration=impact_duration.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_distribution(self) -> dict[str, Any]:
        """Group by impact_duration; return count and avg score."""
        dur_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.impact_duration.value
            dur_data.setdefault(key, []).append(r.score)
        result: dict[str, Any] = {}
        for dur, scores in dur_data.items():
            result[dur] = {
                "count": len(scores),
                "avg_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_sla_gaps(self) -> list[dict[str, Any]]:
        """Return records where score < threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.score < self._threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "service": r.service,
                        "impact_duration": r.impact_duration.value,
                        "score": r.score,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["score"])

    def rank_by_score(self) -> list[dict[str, Any]]:
        """Group by service, avg score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_score"])
        return results

    def detect_score_trends(self) -> dict[str, Any]:
        """Split-half comparison on analysis_score; delta threshold 5.0."""
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

    def generate_report(self) -> AvailabilityImpactReport:
        by_duration: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        by_approach: dict[str, int] = {}
        for r in self._records:
            by_duration[r.impact_duration.value] = by_duration.get(r.impact_duration.value, 0) + 1
            by_severity[r.severity_tier.value] = by_severity.get(r.severity_tier.value, 0) + 1
            by_approach[r.modeling_approach.value] = (
                by_approach.get(r.modeling_approach.value, 0) + 1
            )
        gap_count = sum(1 for r in self._records if r.score < self._threshold)
        scores = [r.score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_sla_gaps()
        top_gaps = [o["service"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(
                f"{gap_count} service(s) with SLA impact below threshold ({self._threshold})"
            )
        if self._records and avg_score < self._threshold:
            recs.append(f"Avg score {avg_score} below threshold ({self._threshold})")
        if not recs:
            recs.append("Availability impact models are within acceptable bounds")
        return AvailabilityImpactReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_score=avg_score,
            by_duration=by_duration,
            by_severity=by_severity,
            by_approach=by_approach,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("availability_impact_modeler.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        dur_dist: dict[str, int] = {}
        for r in self._records:
            key = r.impact_duration.value
            dur_dist[key] = dur_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "duration_distribution": dur_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
