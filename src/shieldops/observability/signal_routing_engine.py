"""SignalRoutingEngine — telemetry signal routing."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class SignalType(StrEnum):
    METRIC = "metric"
    TRACE = "trace"
    LOG = "log"
    EVENT = "event"


class RoutingRule(StrEnum):
    DROP = "drop"
    SAMPLE = "sample"
    TRANSFORM = "transform"
    FORWARD = "forward"


class RoutingPriority(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# --- Models ---


class SignalRoutingEngineRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    signal_type: SignalType = SignalType.METRIC
    routing_rule: RoutingRule = RoutingRule.FORWARD
    routing_priority: RoutingPriority = RoutingPriority.MEDIUM
    score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class SignalRoutingEngineAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    signal_type: SignalType = SignalType.METRIC
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class SignalRoutingEngineReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_score: float = 0.0
    by_signal_type: dict[str, int] = Field(default_factory=dict)
    by_routing_rule: dict[str, int] = Field(default_factory=dict)
    by_routing_priority: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class SignalRoutingEngine:
    """Telemetry signal routing engine."""

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[SignalRoutingEngineRecord] = []
        self._analyses: list[SignalRoutingEngineAnalysis] = []
        logger.info(
            "signal.routing.engine.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    def add_record(
        self,
        name: str,
        signal_type: SignalType = SignalType.METRIC,
        routing_rule: RoutingRule = RoutingRule.FORWARD,
        routing_priority: RoutingPriority = (RoutingPriority.MEDIUM),
        score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> SignalRoutingEngineRecord:
        record = SignalRoutingEngineRecord(
            name=name,
            signal_type=signal_type,
            routing_rule=routing_rule,
            routing_priority=routing_priority,
            score=score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "signal.routing.engine.record_added",
            record_id=record.id,
            name=name,
        )
        return record

    def process(self, key: str) -> dict[str, Any]:
        """Find record by id, create analysis."""
        for r in self._records:
            if r.id == key:
                analysis = SignalRoutingEngineAnalysis(
                    name=r.name,
                    signal_type=r.signal_type,
                    analysis_score=r.score,
                    threshold=self._threshold,
                    breached=(r.score < self._threshold),
                    description=(f"Processed {r.name}"),
                )
                self._analyses.append(analysis)
                return {
                    "status": "processed",
                    "analysis_id": analysis.id,
                    "breached": analysis.breached,
                }
        return {"status": "not_found", "key": key}

    # -- domain methods ---

    def evaluate_routing_rules(
        self,
    ) -> dict[str, Any]:
        """Evaluate routing rules distribution."""
        rule_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.routing_rule.value
            rule_data.setdefault(key, []).append(r.score)
        result: dict[str, Any] = {}
        for k, scores in rule_data.items():
            result[k] = {
                "count": len(scores),
                "avg_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def compute_routing_efficiency(
        self,
    ) -> list[dict[str, Any]]:
        """Compute routing efficiency per service."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            avg = round(sum(scores) / len(scores), 2)
            results.append(
                {
                    "service": svc,
                    "avg_efficiency": avg,
                }
            )
        results.sort(key=lambda x: x["avg_efficiency"])
        return results

    def detect_routing_conflicts(
        self,
    ) -> list[dict[str, Any]]:
        """Detect signals with conflicting rules."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.score < self._threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "name": r.name,
                        "signal_type": (r.signal_type.value),
                        "routing_rule": (r.routing_rule.value),
                        "score": r.score,
                        "service": r.service,
                    }
                )
        return sorted(results, key=lambda x: x["score"])

    # -- report / stats ---

    def generate_report(
        self,
    ) -> SignalRoutingEngineReport:
        by_e1: dict[str, int] = {}
        by_e2: dict[str, int] = {}
        by_e3: dict[str, int] = {}
        for r in self._records:
            v1 = r.signal_type.value
            by_e1[v1] = by_e1.get(v1, 0) + 1
            v2 = r.routing_rule.value
            by_e2[v2] = by_e2.get(v2, 0) + 1
            v3 = r.routing_priority.value
            by_e3[v3] = by_e3.get(v3, 0) + 1
        gap_count = sum(1 for r in self._records if r.score < self._threshold)
        scores = [r.score for r in self._records]
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} item(s) below threshold ({self._threshold})")
        if self._records and avg < self._threshold:
            recs.append(f"Avg score {avg} below threshold ({self._threshold})")
        if not recs:
            recs.append("Signal Routing Engine is healthy")
        return SignalRoutingEngineReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_score=avg,
            by_signal_type=by_e1,
            by_routing_rule=by_e2,
            by_routing_priority=by_e3,
            top_gaps=[r.name for r in self._records if r.score < self._threshold][:5],
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("signal.routing.engine.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        e1_dist: dict[str, int] = {}
        for r in self._records:
            key = r.signal_type.value
            e1_dist[key] = e1_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "signal_type_distribution": e1_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
