"""Platform Stress Tester — execute stress tests and track platform limits."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class StressType(StrEnum):
    LOAD = "load"
    SPIKE = "spike"
    SOAK = "soak"
    BREAKPOINT = "breakpoint"
    CAPACITY = "capacity"


class TargetResource(StrEnum):
    CPU = "cpu"
    MEMORY = "memory"
    NETWORK = "network"
    DISK = "disk"
    CONNECTIONS = "connections"


class StressResult(StrEnum):
    PASSED = "passed"
    DEGRADED = "degraded"
    FAILED = "failed"
    BOTTLENECK = "bottleneck"
    CRASHED = "crashed"


# --- Models ---


class StressTest(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    stress_type: StressType = StressType.LOAD
    target_resource: TargetResource = TargetResource.CPU
    stress_result: StressResult = StressResult.PASSED
    score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class StressAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    stress_type: StressType = StressType.LOAD
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class PlatformStressReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_score: float = 0.0
    by_stress_type: dict[str, int] = Field(default_factory=dict)
    by_resource: dict[str, int] = Field(default_factory=dict)
    by_result: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class PlatformStressTester:
    """Execute platform stress tests and track resource limits and bottlenecks."""

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[StressTest] = []
        self._analyses: list[StressAnalysis] = []
        logger.info(
            "platform_stress_tester.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_test(
        self,
        service: str,
        stress_type: StressType = StressType.LOAD,
        target_resource: TargetResource = TargetResource.CPU,
        stress_result: StressResult = StressResult.PASSED,
        score: float = 0.0,
        team: str = "",
    ) -> StressTest:
        record = StressTest(
            stress_type=stress_type,
            target_resource=target_resource,
            stress_result=stress_result,
            score=score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "platform_stress_tester.test_recorded",
            record_id=record.id,
            service=service,
            stress_type=stress_type.value,
            stress_result=stress_result.value,
        )
        return record

    def get_test(self, record_id: str) -> StressTest | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_tests(
        self,
        stress_type: StressType | None = None,
        target_resource: TargetResource | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[StressTest]:
        results = list(self._records)
        if stress_type is not None:
            results = [r for r in results if r.stress_type == stress_type]
        if target_resource is not None:
            results = [r for r in results if r.target_resource == target_resource]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        stress_type: StressType = StressType.LOAD,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> StressAnalysis:
        analysis = StressAnalysis(
            stress_type=stress_type,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "platform_stress_tester.analysis_added",
            stress_type=stress_type.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_distribution(self) -> dict[str, Any]:
        """Group by stress_type; return count and avg score."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.stress_type.value
            type_data.setdefault(key, []).append(r.score)
        result: dict[str, Any] = {}
        for stype, scores in type_data.items():
            result[stype] = {
                "count": len(scores),
                "avg_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_stress_gaps(self) -> list[dict[str, Any]]:
        """Return records where score < threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.score < self._threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "service": r.service,
                        "stress_type": r.stress_type.value,
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

    def generate_report(self) -> PlatformStressReport:
        by_stress_type: dict[str, int] = {}
        by_resource: dict[str, int] = {}
        by_result: dict[str, int] = {}
        for r in self._records:
            by_stress_type[r.stress_type.value] = by_stress_type.get(r.stress_type.value, 0) + 1
            by_resource[r.target_resource.value] = by_resource.get(r.target_resource.value, 0) + 1
            by_result[r.stress_result.value] = by_result.get(r.stress_result.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.score < self._threshold)
        scores = [r.score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_stress_gaps()
        top_gaps = [o["service"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} stress test(s) below threshold ({self._threshold})")
        if self._records and avg_score < self._threshold:
            recs.append(f"Avg score {avg_score} below threshold ({self._threshold})")
        if not recs:
            recs.append("Platform stress test results are within healthy bounds")
        return PlatformStressReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_score=avg_score,
            by_stress_type=by_stress_type,
            by_resource=by_resource,
            by_result=by_result,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("platform_stress_tester.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.stress_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "stress_type_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
