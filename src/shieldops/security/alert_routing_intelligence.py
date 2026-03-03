"""Alert Routing Intelligence — intelligently route alerts using skill-based and."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class RoutingStrategy(StrEnum):
    SKILL_BASED = "skill_based"
    ROUND_ROBIN = "round_robin"
    PRIORITY_BASED = "priority_based"
    WORKLOAD_AWARE = "workload_aware"
    ML_OPTIMIZED = "ml_optimized"


class AlertPriority(StrEnum):
    P1_CRITICAL = "p1_critical"
    P2_HIGH = "p2_high"
    P3_MEDIUM = "p3_medium"
    P4_LOW = "p4_low"
    P5_INFORMATIONAL = "p5_informational"


class RoutingOutcome(StrEnum):
    CORRECT = "correct"
    ESCALATED = "escalated"
    REROUTED = "rerouted"
    DELAYED = "delayed"
    MISSED = "missed"


# --- Models ---


class RoutingRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    routing_id: str = ""
    routing_strategy: RoutingStrategy = RoutingStrategy.SKILL_BASED
    alert_priority: AlertPriority = AlertPriority.P3_MEDIUM
    routing_outcome: RoutingOutcome = RoutingOutcome.CORRECT
    routing_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class RoutingAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    routing_id: str = ""
    routing_strategy: RoutingStrategy = RoutingStrategy.SKILL_BASED
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class RoutingReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_routing_score: float = 0.0
    by_strategy: dict[str, int] = Field(default_factory=dict)
    by_priority: dict[str, int] = Field(default_factory=dict)
    by_outcome: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class AlertRoutingIntelligence:
    """Intelligently route alerts using skill-based and ML-optimized strategies."""

    def __init__(
        self,
        max_records: int = 200000,
        routing_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._routing_threshold = routing_threshold
        self._records: list[RoutingRecord] = []
        self._analyses: list[RoutingAnalysis] = []
        logger.info(
            "alert_routing_intelligence.initialized",
            max_records=max_records,
            routing_threshold=routing_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_routing(
        self,
        routing_id: str,
        routing_strategy: RoutingStrategy = RoutingStrategy.SKILL_BASED,
        alert_priority: AlertPriority = AlertPriority.P3_MEDIUM,
        routing_outcome: RoutingOutcome = RoutingOutcome.CORRECT,
        routing_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> RoutingRecord:
        record = RoutingRecord(
            routing_id=routing_id,
            routing_strategy=routing_strategy,
            alert_priority=alert_priority,
            routing_outcome=routing_outcome,
            routing_score=routing_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "alert_routing_intelligence.routing_recorded",
            record_id=record.id,
            routing_id=routing_id,
            routing_strategy=routing_strategy.value,
            alert_priority=alert_priority.value,
        )
        return record

    def get_routing(self, record_id: str) -> RoutingRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_routings(
        self,
        routing_strategy: RoutingStrategy | None = None,
        alert_priority: AlertPriority | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[RoutingRecord]:
        results = list(self._records)
        if routing_strategy is not None:
            results = [r for r in results if r.routing_strategy == routing_strategy]
        if alert_priority is not None:
            results = [r for r in results if r.alert_priority == alert_priority]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        routing_id: str,
        routing_strategy: RoutingStrategy = RoutingStrategy.SKILL_BASED,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> RoutingAnalysis:
        analysis = RoutingAnalysis(
            routing_id=routing_id,
            routing_strategy=routing_strategy,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "alert_routing_intelligence.analysis_added",
            routing_id=routing_id,
            routing_strategy=routing_strategy.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_strategy_distribution(self) -> dict[str, Any]:
        strategy_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.routing_strategy.value
            strategy_data.setdefault(key, []).append(r.routing_score)
        result: dict[str, Any] = {}
        for strategy, scores in strategy_data.items():
            result[strategy] = {
                "count": len(scores),
                "avg_routing_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_routing_gaps(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.routing_score < self._routing_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "routing_id": r.routing_id,
                        "routing_strategy": r.routing_strategy.value,
                        "routing_score": r.routing_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["routing_score"])

    def rank_by_routing(self) -> list[dict[str, Any]]:
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.routing_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_routing_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_routing_score"])
        return results

    def detect_routing_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> RoutingReport:
        by_strategy: dict[str, int] = {}
        by_priority: dict[str, int] = {}
        by_outcome: dict[str, int] = {}
        for r in self._records:
            by_strategy[r.routing_strategy.value] = by_strategy.get(r.routing_strategy.value, 0) + 1
            by_priority[r.alert_priority.value] = by_priority.get(r.alert_priority.value, 0) + 1
            by_outcome[r.routing_outcome.value] = by_outcome.get(r.routing_outcome.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.routing_score < self._routing_threshold)
        scores = [r.routing_score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_routing_gaps()
        top_gaps = [o["routing_id"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} routing(s) below threshold ({self._routing_threshold})")
        if self._records and avg_score < self._routing_threshold:
            recs.append(
                f"Avg routing score {avg_score} below threshold ({self._routing_threshold})"
            )
        if not recs:
            recs.append("Alert routing intelligence is healthy")
        return RoutingReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_routing_score=avg_score,
            by_strategy=by_strategy,
            by_priority=by_priority,
            by_outcome=by_outcome,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("alert_routing_intelligence.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        strategy_dist: dict[str, int] = {}
        for r in self._records:
            key = r.routing_strategy.value
            strategy_dist[key] = strategy_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "routing_threshold": self._routing_threshold,
            "strategy_distribution": strategy_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
