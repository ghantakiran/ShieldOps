"""Service Dependency Scorer — score service dependency health, detect fragile deps."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class CouplingLevel(StrEnum):
    TIGHT = "tight"
    MODERATE = "moderate"
    LOOSE = "loose"
    ASYNC = "async"
    INDEPENDENT = "independent"


class DependencyHealth(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FRAGILE = "fragile"
    BROKEN = "broken"
    UNKNOWN = "unknown"


class DependencyDirection(StrEnum):
    UPSTREAM = "upstream"
    DOWNSTREAM = "downstream"
    BIDIRECTIONAL = "bidirectional"
    CIRCULAR = "circular"
    OPTIONAL = "optional"


# --- Models ---


class DependencyScoreRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    dependency_id: str = ""
    coupling_level: CouplingLevel = CouplingLevel.LOOSE
    dependency_health: DependencyHealth = DependencyHealth.UNKNOWN
    dependency_direction: DependencyDirection = DependencyDirection.DOWNSTREAM
    health_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class DependencyMetric(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    dependency_id: str = ""
    coupling_level: CouplingLevel = CouplingLevel.LOOSE
    metric_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ServiceDependencyReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_metrics: int = 0
    fragile_count: int = 0
    avg_health_score: float = 0.0
    by_coupling: dict[str, int] = Field(default_factory=dict)
    by_health: dict[str, int] = Field(default_factory=dict)
    by_direction: dict[str, int] = Field(default_factory=dict)
    top_fragile: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class ServiceDependencyScorer:
    """Score service dependency health, detect fragile dependencies."""

    def __init__(
        self,
        max_records: int = 200000,
        min_health_score: float = 60.0,
    ) -> None:
        self._max_records = max_records
        self._min_health_score = min_health_score
        self._records: list[DependencyScoreRecord] = []
        self._metrics: list[DependencyMetric] = []
        logger.info(
            "service_dependency_scorer.initialized",
            max_records=max_records,
            min_health_score=min_health_score,
        )

    # -- record / get / list ------------------------------------------------

    def record_dependency(
        self,
        dependency_id: str,
        coupling_level: CouplingLevel = CouplingLevel.LOOSE,
        dependency_health: DependencyHealth = DependencyHealth.UNKNOWN,
        dependency_direction: DependencyDirection = DependencyDirection.DOWNSTREAM,
        health_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> DependencyScoreRecord:
        record = DependencyScoreRecord(
            dependency_id=dependency_id,
            coupling_level=coupling_level,
            dependency_health=dependency_health,
            dependency_direction=dependency_direction,
            health_score=health_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "service_dependency_scorer.dependency_recorded",
            record_id=record.id,
            dependency_id=dependency_id,
            coupling_level=coupling_level.value,
            dependency_health=dependency_health.value,
        )
        return record

    def get_dependency(self, record_id: str) -> DependencyScoreRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_dependencies(
        self,
        coupling_level: CouplingLevel | None = None,
        dependency_health: DependencyHealth | None = None,
        service: str | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[DependencyScoreRecord]:
        results = list(self._records)
        if coupling_level is not None:
            results = [r for r in results if r.coupling_level == coupling_level]
        if dependency_health is not None:
            results = [r for r in results if r.dependency_health == dependency_health]
        if service is not None:
            results = [r for r in results if r.service == service]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_metric(
        self,
        dependency_id: str,
        coupling_level: CouplingLevel = CouplingLevel.LOOSE,
        metric_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> DependencyMetric:
        metric = DependencyMetric(
            dependency_id=dependency_id,
            coupling_level=coupling_level,
            metric_score=metric_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._metrics.append(metric)
        if len(self._metrics) > self._max_records:
            self._metrics = self._metrics[-self._max_records :]
        logger.info(
            "service_dependency_scorer.metric_added",
            dependency_id=dependency_id,
            coupling_level=coupling_level.value,
            metric_score=metric_score,
        )
        return metric

    # -- domain operations --------------------------------------------------

    def analyze_dependency_distribution(self) -> dict[str, Any]:
        """Group by coupling_level; return count and avg health_score."""
        level_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.coupling_level.value
            level_data.setdefault(key, []).append(r.health_score)
        result: dict[str, Any] = {}
        for level, scores in level_data.items():
            result[level] = {
                "count": len(scores),
                "avg_health_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_fragile_dependencies(self) -> list[dict[str, Any]]:
        """Return records where dependency_health is FRAGILE or BROKEN."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.dependency_health in (
                DependencyHealth.FRAGILE,
                DependencyHealth.BROKEN,
            ):
                results.append(
                    {
                        "record_id": r.id,
                        "dependency_id": r.dependency_id,
                        "dependency_health": r.dependency_health.value,
                        "health_score": r.health_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_health_score(self) -> list[dict[str, Any]]:
        """Group by service, avg health_score, sort ascending (worst first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.health_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_health_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_health_score"])
        return results

    def detect_dependency_trends(self) -> dict[str, Any]:
        """Split-half comparison on metric_score; delta threshold 5.0."""
        if len(self._metrics) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [m.metric_score for m in self._metrics]
        mid = len(vals) // 2
        first_half = vals[:mid]
        second_half = vals[mid:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        delta = round(avg_second - avg_first, 2)
        if abs(delta) < 5.0:
            trend = "stable"
        elif delta > 0:
            trend = "growing"
        else:
            trend = "shrinking"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> ServiceDependencyReport:
        by_coupling: dict[str, int] = {}
        by_health: dict[str, int] = {}
        by_direction: dict[str, int] = {}
        for r in self._records:
            by_coupling[r.coupling_level.value] = by_coupling.get(r.coupling_level.value, 0) + 1
            by_health[r.dependency_health.value] = by_health.get(r.dependency_health.value, 0) + 1
            by_direction[r.dependency_direction.value] = (
                by_direction.get(r.dependency_direction.value, 0) + 1
            )
        fragile_count = sum(
            1
            for r in self._records
            if r.dependency_health in (DependencyHealth.FRAGILE, DependencyHealth.BROKEN)
        )
        scores = [r.health_score for r in self._records]
        avg_health_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        fragile_list = self.identify_fragile_dependencies()
        top_fragile = [o["dependency_id"] for o in fragile_list[:5]]
        recs: list[str] = []
        if self._records and avg_health_score < self._min_health_score:
            recs.append(
                f"Avg health score {avg_health_score} below threshold ({self._min_health_score})"
            )
        if fragile_count > 0:
            recs.append(f"{fragile_count} fragile dependency(ies) — prioritize remediation")
        if not recs:
            recs.append("Dependency health levels are healthy")
        return ServiceDependencyReport(
            total_records=len(self._records),
            total_metrics=len(self._metrics),
            fragile_count=fragile_count,
            avg_health_score=avg_health_score,
            by_coupling=by_coupling,
            by_health=by_health,
            by_direction=by_direction,
            top_fragile=top_fragile,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._metrics.clear()
        logger.info("service_dependency_scorer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        coupling_dist: dict[str, int] = {}
        for r in self._records:
            key = r.coupling_level.value
            coupling_dist[key] = coupling_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_metrics": len(self._metrics),
            "min_health_score": self._min_health_score,
            "coupling_distribution": coupling_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
