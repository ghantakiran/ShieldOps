"""Dependency Failure Simulator — simulate dependency failures and test fallbacks."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class DependencyType(StrEnum):
    DATABASE = "database"
    CACHE = "cache"
    MESSAGE_QUEUE = "message_queue"
    API = "api"
    DNS = "dns"


class SimulationMode(StrEnum):
    GRADUAL = "gradual"
    SUDDEN = "sudden"
    INTERMITTENT = "intermittent"
    PARTIAL = "partial"
    COMPLETE = "complete"


class FallbackBehavior(StrEnum):
    GRACEFUL_DEGRADATION = "graceful_degradation"
    CIRCUIT_BREAK = "circuit_break"
    RETRY = "retry"
    FAILOVER = "failover"
    ERROR = "error"


# --- Models ---


class DependencySimulation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    dependency_type: DependencyType = DependencyType.DATABASE
    simulation_mode: SimulationMode = SimulationMode.GRADUAL
    fallback_behavior: FallbackBehavior = FallbackBehavior.GRACEFUL_DEGRADATION
    score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class SimulationAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    dependency_type: DependencyType = DependencyType.DATABASE
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class DependencySimulationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_score: float = 0.0
    by_dependency_type: dict[str, int] = Field(default_factory=dict)
    by_mode: dict[str, int] = Field(default_factory=dict)
    by_fallback: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class DependencyFailureSimulator:
    """Simulate dependency failures and validate fallback behavior correctness."""

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[DependencySimulation] = []
        self._analyses: list[SimulationAnalysis] = []
        logger.info(
            "dependency_failure_simulator.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_simulation(
        self,
        service: str,
        dependency_type: DependencyType = DependencyType.DATABASE,
        simulation_mode: SimulationMode = SimulationMode.GRADUAL,
        fallback_behavior: FallbackBehavior = FallbackBehavior.GRACEFUL_DEGRADATION,
        score: float = 0.0,
        team: str = "",
    ) -> DependencySimulation:
        record = DependencySimulation(
            dependency_type=dependency_type,
            simulation_mode=simulation_mode,
            fallback_behavior=fallback_behavior,
            score=score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "dependency_failure_simulator.simulation_recorded",
            record_id=record.id,
            service=service,
            dependency_type=dependency_type.value,
            simulation_mode=simulation_mode.value,
        )
        return record

    def get_simulation(self, record_id: str) -> DependencySimulation | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_simulations(
        self,
        dependency_type: DependencyType | None = None,
        simulation_mode: SimulationMode | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[DependencySimulation]:
        results = list(self._records)
        if dependency_type is not None:
            results = [r for r in results if r.dependency_type == dependency_type]
        if simulation_mode is not None:
            results = [r for r in results if r.simulation_mode == simulation_mode]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        dependency_type: DependencyType = DependencyType.DATABASE,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> SimulationAnalysis:
        analysis = SimulationAnalysis(
            dependency_type=dependency_type,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "dependency_failure_simulator.analysis_added",
            dependency_type=dependency_type.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_distribution(self) -> dict[str, Any]:
        """Group by dependency_type; return count and avg score."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.dependency_type.value
            type_data.setdefault(key, []).append(r.score)
        result: dict[str, Any] = {}
        for dtype, scores in type_data.items():
            result[dtype] = {
                "count": len(scores),
                "avg_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_fallback_gaps(self) -> list[dict[str, Any]]:
        """Return records where score < threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.score < self._threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "service": r.service,
                        "dependency_type": r.dependency_type.value,
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

    def generate_report(self) -> DependencySimulationReport:
        by_dependency_type: dict[str, int] = {}
        by_mode: dict[str, int] = {}
        by_fallback: dict[str, int] = {}
        for r in self._records:
            by_dependency_type[r.dependency_type.value] = (
                by_dependency_type.get(r.dependency_type.value, 0) + 1
            )
            by_mode[r.simulation_mode.value] = by_mode.get(r.simulation_mode.value, 0) + 1
            by_fallback[r.fallback_behavior.value] = (
                by_fallback.get(r.fallback_behavior.value, 0) + 1
            )
        gap_count = sum(1 for r in self._records if r.score < self._threshold)
        scores = [r.score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_fallback_gaps()
        top_gaps = [o["service"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} dependency simulation(s) below threshold ({self._threshold})")
        if self._records and avg_score < self._threshold:
            recs.append(f"Avg score {avg_score} below threshold ({self._threshold})")
        if not recs:
            recs.append("Dependency failure simulations are healthy")
        return DependencySimulationReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_score=avg_score,
            by_dependency_type=by_dependency_type,
            by_mode=by_mode,
            by_fallback=by_fallback,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("dependency_failure_simulator.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.dependency_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "dependency_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
