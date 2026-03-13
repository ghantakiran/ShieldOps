"""API Health Composite Scorer.

Compute composite health scores for APIs, identify degraded
endpoints, and benchmark API health across scopes."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class HealthGrade(StrEnum):
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"


class SignalType(StrEnum):
    LATENCY = "latency"
    ERROR_RATE = "error_rate"
    THROUGHPUT = "throughput"
    SATURATION = "saturation"


class BenchmarkScope(StrEnum):
    SERVICE = "service"
    TEAM = "team"
    ORGANIZATION = "organization"
    INDUSTRY = "industry"


# --- Models ---


class ApiHealthRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    endpoint: str = ""
    service: str = ""
    health_grade: HealthGrade = HealthGrade.GOOD
    signal_type: SignalType = SignalType.LATENCY
    benchmark_scope: BenchmarkScope = BenchmarkScope.SERVICE
    score: float = 0.0
    latency_ms: float = 0.0
    error_rate: float = 0.0
    throughput_rps: float = 0.0
    created_at: float = Field(default_factory=time.time)


class ApiHealthAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    endpoint: str = ""
    composite_score: float = 0.0
    health_grade: HealthGrade = HealthGrade.GOOD
    degraded: bool = False
    signal_count: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ApiHealthReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_score: float = 0.0
    by_health_grade: dict[str, int] = Field(default_factory=dict)
    by_signal_type: dict[str, int] = Field(default_factory=dict)
    by_benchmark_scope: dict[str, int] = Field(default_factory=dict)
    degraded_endpoints: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class ApiHealthCompositeScorer:
    """Compute composite health scores, identify degraded
    endpoints, and benchmark API health."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[ApiHealthRecord] = []
        self._analyses: dict[str, ApiHealthAnalysis] = {}
        logger.info(
            "api_health_composite_scorer.init",
            max_records=max_records,
        )

    def record_item(
        self,
        endpoint: str = "",
        service: str = "",
        health_grade: HealthGrade = HealthGrade.GOOD,
        signal_type: SignalType = SignalType.LATENCY,
        benchmark_scope: BenchmarkScope = (BenchmarkScope.SERVICE),
        score: float = 0.0,
        latency_ms: float = 0.0,
        error_rate: float = 0.0,
        throughput_rps: float = 0.0,
    ) -> ApiHealthRecord:
        record = ApiHealthRecord(
            endpoint=endpoint,
            service=service,
            health_grade=health_grade,
            signal_type=signal_type,
            benchmark_scope=benchmark_scope,
            score=score,
            latency_ms=latency_ms,
            error_rate=error_rate,
            throughput_rps=throughput_rps,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "api_health.record_added",
            record_id=record.id,
            endpoint=endpoint,
        )
        return record

    def process(self, key: str) -> ApiHealthAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        signals = sum(1 for r in self._records if r.endpoint == rec.endpoint)
        degraded = rec.health_grade in (
            HealthGrade.FAIR,
            HealthGrade.POOR,
        )
        analysis = ApiHealthAnalysis(
            endpoint=rec.endpoint,
            composite_score=round(rec.score, 2),
            health_grade=rec.health_grade,
            degraded=degraded,
            signal_count=signals,
            description=(f"Endpoint {rec.endpoint} score {rec.score}"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> ApiHealthReport:
        by_hg: dict[str, int] = {}
        by_st: dict[str, int] = {}
        by_bs: dict[str, int] = {}
        scores: list[float] = []
        for r in self._records:
            k = r.health_grade.value
            by_hg[k] = by_hg.get(k, 0) + 1
            k2 = r.signal_type.value
            by_st[k2] = by_st.get(k2, 0) + 1
            k3 = r.benchmark_scope.value
            by_bs[k3] = by_bs.get(k3, 0) + 1
            scores.append(r.score)
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        degraded = list(
            {
                r.endpoint
                for r in self._records
                if r.health_grade in (HealthGrade.FAIR, HealthGrade.POOR)
            }
        )[:10]
        recs: list[str] = []
        if degraded:
            recs.append(f"{len(degraded)} degraded endpoints")
        if not recs:
            recs.append("All endpoints healthy")
        return ApiHealthReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_score=avg,
            by_health_grade=by_hg,
            by_signal_type=by_st,
            by_benchmark_scope=by_bs,
            degraded_endpoints=degraded,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        dist: dict[str, int] = {}
        for r in self._records:
            k = r.health_grade.value
            dist[k] = dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "health_grade_distribution": dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("api_health_composite_scorer.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def compute_composite_health(
        self,
    ) -> list[dict[str, Any]]:
        """Compute composite health per endpoint."""
        ep_scores: dict[str, list[float]] = {}
        ep_svc: dict[str, str] = {}
        for r in self._records:
            ep_scores.setdefault(r.endpoint, []).append(r.score)
            ep_svc[r.endpoint] = r.service
        results: list[dict[str, Any]] = []
        for ep, scores in ep_scores.items():
            avg = round(sum(scores) / len(scores), 2)
            results.append(
                {
                    "endpoint": ep,
                    "service": ep_svc[ep],
                    "composite_score": avg,
                    "signal_count": len(scores),
                }
            )
        results.sort(
            key=lambda x: x["composite_score"],
            reverse=True,
        )
        return results

    def identify_degraded_endpoints(
        self,
    ) -> list[dict[str, Any]]:
        """Identify endpoints with poor health."""
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for r in self._records:
            if r.health_grade in (HealthGrade.FAIR, HealthGrade.POOR) and r.endpoint not in seen:
                seen.add(r.endpoint)
                results.append(
                    {
                        "endpoint": r.endpoint,
                        "service": r.service,
                        "health_grade": (r.health_grade.value),
                        "score": r.score,
                    }
                )
        results.sort(key=lambda x: x["score"])
        return results

    def benchmark_api_health(
        self,
    ) -> list[dict[str, Any]]:
        """Benchmark API health by scope."""
        scope_data: dict[str, list[float]] = {}
        for r in self._records:
            scope_data.setdefault(r.benchmark_scope.value, []).append(r.score)
        results: list[dict[str, Any]] = []
        for scope, scores in scope_data.items():
            avg = round(sum(scores) / len(scores), 2)
            results.append(
                {
                    "scope": scope,
                    "avg_score": avg,
                    "endpoint_count": len(scores),
                }
            )
        results.sort(
            key=lambda x: x["avg_score"],
            reverse=True,
        )
        return results
