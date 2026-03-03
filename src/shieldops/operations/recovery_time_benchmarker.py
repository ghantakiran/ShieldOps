"""Recovery Time Benchmarker — benchmark recovery times against RTO/RPO targets."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class RecoveryType(StrEnum):
    FAILOVER = "failover"
    RESTART = "restart"
    ROLLBACK = "rollback"
    REBUILD = "rebuild"
    RESTORE = "restore"


class BenchmarkResult(StrEnum):
    EXCEEDS = "exceeds"
    MEETS = "meets"
    BELOW = "below"
    CRITICAL = "critical"
    UNTESTED = "untested"


class RecoveryTarget(StrEnum):
    RTO = "rto"
    RPO = "rpo"
    MTTR = "mttr"
    MTTD = "mttd"
    MTTF = "mttf"


# --- Models ---


class RecoveryBenchmark(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    recovery_type: RecoveryType = RecoveryType.FAILOVER
    benchmark_result: BenchmarkResult = BenchmarkResult.MEETS
    recovery_target: RecoveryTarget = RecoveryTarget.RTO
    score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class BenchmarkAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    recovery_type: RecoveryType = RecoveryType.FAILOVER
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class RecoveryBenchmarkReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_score: float = 0.0
    by_recovery_type: dict[str, int] = Field(default_factory=dict)
    by_result: dict[str, int] = Field(default_factory=dict)
    by_target: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class RecoveryTimeBenchmarker:
    """Benchmark recovery times and track compliance with RTO/RPO/MTTR targets."""

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[RecoveryBenchmark] = []
        self._analyses: list[BenchmarkAnalysis] = []
        logger.info(
            "recovery_time_benchmarker.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_benchmark(
        self,
        service: str,
        recovery_type: RecoveryType = RecoveryType.FAILOVER,
        benchmark_result: BenchmarkResult = BenchmarkResult.MEETS,
        recovery_target: RecoveryTarget = RecoveryTarget.RTO,
        score: float = 0.0,
        team: str = "",
    ) -> RecoveryBenchmark:
        record = RecoveryBenchmark(
            recovery_type=recovery_type,
            benchmark_result=benchmark_result,
            recovery_target=recovery_target,
            score=score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "recovery_time_benchmarker.benchmark_recorded",
            record_id=record.id,
            service=service,
            recovery_type=recovery_type.value,
            benchmark_result=benchmark_result.value,
        )
        return record

    def get_benchmark(self, record_id: str) -> RecoveryBenchmark | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_benchmarks(
        self,
        recovery_type: RecoveryType | None = None,
        benchmark_result: BenchmarkResult | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[RecoveryBenchmark]:
        results = list(self._records)
        if recovery_type is not None:
            results = [r for r in results if r.recovery_type == recovery_type]
        if benchmark_result is not None:
            results = [r for r in results if r.benchmark_result == benchmark_result]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        recovery_type: RecoveryType = RecoveryType.FAILOVER,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> BenchmarkAnalysis:
        analysis = BenchmarkAnalysis(
            recovery_type=recovery_type,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "recovery_time_benchmarker.analysis_added",
            recovery_type=recovery_type.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_distribution(self) -> dict[str, Any]:
        """Group by recovery_type; return count and avg score."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.recovery_type.value
            type_data.setdefault(key, []).append(r.score)
        result: dict[str, Any] = {}
        for rtype, scores in type_data.items():
            result[rtype] = {
                "count": len(scores),
                "avg_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_benchmark_gaps(self) -> list[dict[str, Any]]:
        """Return records where score < threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.score < self._threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "service": r.service,
                        "recovery_type": r.recovery_type.value,
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

    def generate_report(self) -> RecoveryBenchmarkReport:
        by_recovery_type: dict[str, int] = {}
        by_result: dict[str, int] = {}
        by_target: dict[str, int] = {}
        for r in self._records:
            by_recovery_type[r.recovery_type.value] = (
                by_recovery_type.get(r.recovery_type.value, 0) + 1
            )
            by_result[r.benchmark_result.value] = by_result.get(r.benchmark_result.value, 0) + 1
            by_target[r.recovery_target.value] = by_target.get(r.recovery_target.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.score < self._threshold)
        scores = [r.score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_benchmark_gaps()
        top_gaps = [o["service"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(
                f"{gap_count} service(s) missing recovery targets (threshold {self._threshold})"
            )
        if self._records and avg_score < self._threshold:
            recs.append(f"Avg score {avg_score} below threshold ({self._threshold})")
        if not recs:
            recs.append("Recovery time benchmarks are within targets")
        return RecoveryBenchmarkReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_score=avg_score,
            by_recovery_type=by_recovery_type,
            by_result=by_result,
            by_target=by_target,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("recovery_time_benchmarker.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.recovery_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "type_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
