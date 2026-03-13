"""Span Criticality Scoring Engine —
score span criticality in trace trees,
identify critical paths, rank spans by importance."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class SpanRole(StrEnum):
    ENTRY = "entry"
    INTERNAL = "internal"
    LEAF = "leaf"
    ERROR = "error"


class CriticalityFactor(StrEnum):
    LATENCY_CONTRIBUTION = "latency_contribution"
    ERROR_RATE = "error_rate"
    DEPENDENCY_COUNT = "dependency_count"
    CALL_FREQUENCY = "call_frequency"


class ScoreConfidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNCERTAIN = "uncertain"


# --- Models ---


class SpanCriticalityRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    span_id: str = ""
    trace_id: str = ""
    service_name: str = ""
    operation_name: str = ""
    span_role: SpanRole = SpanRole.INTERNAL
    criticality_factor: CriticalityFactor = CriticalityFactor.LATENCY_CONTRIBUTION
    score_confidence: ScoreConfidence = ScoreConfidence.MEDIUM
    criticality_score: float = 0.0
    latency_ms: float = 0.0
    dependency_count: int = 0
    call_count: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class SpanCriticalityAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    span_id: str = ""
    service_name: str = ""
    operation_name: str = ""
    span_role: SpanRole = SpanRole.INTERNAL
    final_score: float = 0.0
    is_critical_path: bool = False
    confidence: ScoreConfidence = ScoreConfidence.MEDIUM
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class SpanCriticalityReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_criticality_score: float = 0.0
    by_span_role: dict[str, int] = Field(default_factory=dict)
    by_criticality_factor: dict[str, int] = Field(default_factory=dict)
    by_confidence: dict[str, int] = Field(default_factory=dict)
    critical_spans: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class SpanCriticalityScoringEngine:
    """Score span criticality in trace trees,
    identify critical paths, rank spans by importance."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[SpanCriticalityRecord] = []
        self._analyses: dict[str, SpanCriticalityAnalysis] = {}
        logger.info("span_criticality_scoring_engine.init", max_records=max_records)

    def add_record(
        self,
        span_id: str = "",
        trace_id: str = "",
        service_name: str = "",
        operation_name: str = "",
        span_role: SpanRole = SpanRole.INTERNAL,
        criticality_factor: CriticalityFactor = CriticalityFactor.LATENCY_CONTRIBUTION,
        score_confidence: ScoreConfidence = ScoreConfidence.MEDIUM,
        criticality_score: float = 0.0,
        latency_ms: float = 0.0,
        dependency_count: int = 0,
        call_count: int = 0,
        description: str = "",
    ) -> SpanCriticalityRecord:
        record = SpanCriticalityRecord(
            span_id=span_id,
            trace_id=trace_id,
            service_name=service_name,
            operation_name=operation_name,
            span_role=span_role,
            criticality_factor=criticality_factor,
            score_confidence=score_confidence,
            criticality_score=criticality_score,
            latency_ms=latency_ms,
            dependency_count=dependency_count,
            call_count=call_count,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "span_criticality.record_added",
            record_id=record.id,
            span_id=span_id,
        )
        return record

    def process(self, key: str) -> SpanCriticalityAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        conf_weights = {"high": 1.0, "medium": 0.75, "low": 0.5, "uncertain": 0.25}
        weight = conf_weights.get(rec.score_confidence.value, 0.5)
        final = round(rec.criticality_score * weight, 2)
        analysis = SpanCriticalityAnalysis(
            span_id=rec.span_id,
            service_name=rec.service_name,
            operation_name=rec.operation_name,
            span_role=rec.span_role,
            final_score=final,
            is_critical_path=final > 75.0,
            confidence=rec.score_confidence,
            description=f"Span {rec.span_id} score {final} role {rec.span_role.value}",
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> SpanCriticalityReport:
        by_role: dict[str, int] = {}
        by_factor: dict[str, int] = {}
        by_conf: dict[str, int] = {}
        scores: list[float] = []
        for r in self._records:
            rl = r.span_role.value
            by_role[rl] = by_role.get(rl, 0) + 1
            fc = r.criticality_factor.value
            by_factor[fc] = by_factor.get(fc, 0) + 1
            cf = r.score_confidence.value
            by_conf[cf] = by_conf.get(cf, 0) + 1
            scores.append(r.criticality_score)
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        crit_spans = list({r.span_id for r in self._records if r.criticality_score > 75.0})[:10]
        recs: list[str] = []
        if crit_spans:
            recs.append(f"{len(crit_spans)} spans on critical path")
        if not recs:
            recs.append("No critical span paths detected")
        return SpanCriticalityReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_criticality_score=avg,
            by_span_role=by_role,
            by_criticality_factor=by_factor,
            by_confidence=by_conf,
            critical_spans=crit_spans,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        role_dist: dict[str, int] = {}
        for r in self._records:
            k = r.span_role.value
            role_dist[k] = role_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "role_distribution": role_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("span_criticality_scoring_engine.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def score_span_criticality(self) -> list[dict[str, Any]]:
        """Score all spans and return sorted criticality list."""
        conf_weights = {"high": 1.0, "medium": 0.75, "low": 0.5, "uncertain": 0.25}
        results: list[dict[str, Any]] = []
        for r in self._records:
            w = conf_weights.get(r.score_confidence.value, 0.5)
            final = round(r.criticality_score * w, 2)
            results.append(
                {
                    "span_id": r.span_id,
                    "service_name": r.service_name,
                    "operation_name": r.operation_name,
                    "span_role": r.span_role.value,
                    "final_score": final,
                    "confidence": r.score_confidence.value,
                }
            )
        results.sort(key=lambda x: x["final_score"], reverse=True)
        return results

    def identify_critical_paths(self) -> list[dict[str, Any]]:
        """Identify critical paths in trace trees by trace_id."""
        trace_spans: dict[str, list[dict[str, Any]]] = {}
        for r in self._records:
            trace_spans.setdefault(r.trace_id, []).append(
                {
                    "span_id": r.span_id,
                    "service_name": r.service_name,
                    "latency_ms": r.latency_ms,
                    "criticality_score": r.criticality_score,
                }
            )
        results: list[dict[str, Any]] = []
        for tid, spans in trace_spans.items():
            total_lat = sum(sp["latency_ms"] for sp in spans)
            max_score = max(sp["criticality_score"] for sp in spans)
            results.append(
                {
                    "trace_id": tid,
                    "span_count": len(spans),
                    "total_latency_ms": round(total_lat, 2),
                    "max_criticality_score": round(max_score, 2),
                    "is_critical": max_score > 75.0,
                }
            )
        results.sort(key=lambda x: x["max_criticality_score"], reverse=True)
        return results

    def rank_spans_by_importance(self) -> list[dict[str, Any]]:
        """Rank spans by composite importance including dependencies and call frequency."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            importance = round(
                r.criticality_score * 0.5 + r.dependency_count * 2.0 + r.call_count * 0.1,
                2,
            )
            results.append(
                {
                    "span_id": r.span_id,
                    "service_name": r.service_name,
                    "importance_score": importance,
                    "dependency_count": r.dependency_count,
                    "call_count": r.call_count,
                    "rank": 0,
                }
            )
        results.sort(key=lambda x: x["importance_score"], reverse=True)
        for idx, entry in enumerate(results, 1):
            entry["rank"] = idx
        return results
