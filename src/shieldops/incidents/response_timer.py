"""Incident Response Timer — track and benchmark incident response times."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ResponsePhase(StrEnum):
    DETECTION = "detection"
    ACKNOWLEDGMENT = "acknowledgment"
    INVESTIGATION = "investigation"
    MITIGATION = "mitigation"
    RESOLUTION = "resolution"


class ResponseSpeed(StrEnum):
    EXCELLENT = "excellent"
    FAST = "fast"
    ACCEPTABLE = "acceptable"
    SLOW = "slow"
    CRITICAL = "critical"


class BenchmarkType(StrEnum):
    INDUSTRY = "industry"
    ORGANIZATIONAL = "organizational"
    TEAM = "team"
    SERVICE = "service"
    HISTORICAL = "historical"


# --- Models ---


class ResponseTimerRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    phase: ResponsePhase = ResponsePhase.DETECTION
    speed: ResponseSpeed = ResponseSpeed.EXCELLENT
    benchmark_type: BenchmarkType = BenchmarkType.INDUSTRY
    duration_minutes: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class ResponseBenchmark(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    benchmark_name: str = ""
    phase: ResponsePhase = ResponsePhase.DETECTION
    speed: ResponseSpeed = ResponseSpeed.ACCEPTABLE
    target_minutes: float = 30.0
    percentile: float = 95.0
    created_at: float = Field(default_factory=time.time)


class ResponseTimerReport(BaseModel):
    total_responses: int = 0
    total_benchmarks: int = 0
    on_target_rate_pct: float = 0.0
    by_phase: dict[str, int] = Field(default_factory=dict)
    by_speed: dict[str, int] = Field(default_factory=dict)
    slow_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class IncidentResponseTimer:
    """Track and benchmark incident response times."""

    def __init__(
        self,
        max_records: int = 200000,
        target_minutes: float = 30.0,
    ) -> None:
        self._max_records = max_records
        self._target_minutes = target_minutes
        self._records: list[ResponseTimerRecord] = []
        self._benchmarks: list[ResponseBenchmark] = []
        logger.info(
            "response_timer.initialized",
            max_records=max_records,
            target_minutes=target_minutes,
        )

    # -- record / get / list ---------------------------------------------

    def record_response_time(
        self,
        service_name: str,
        phase: ResponsePhase = ResponsePhase.DETECTION,
        speed: ResponseSpeed = ResponseSpeed.EXCELLENT,
        benchmark_type: BenchmarkType = BenchmarkType.INDUSTRY,
        duration_minutes: float = 0.0,
        details: str = "",
    ) -> ResponseTimerRecord:
        record = ResponseTimerRecord(
            service_name=service_name,
            phase=phase,
            speed=speed,
            benchmark_type=benchmark_type,
            duration_minutes=duration_minutes,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "response_timer.response_recorded",
            record_id=record.id,
            service_name=service_name,
            phase=phase.value,
            speed=speed.value,
        )
        return record

    def get_response_time(self, record_id: str) -> ResponseTimerRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_response_times(
        self,
        service_name: str | None = None,
        phase: ResponsePhase | None = None,
        limit: int = 50,
    ) -> list[ResponseTimerRecord]:
        results = list(self._records)
        if service_name is not None:
            results = [r for r in results if r.service_name == service_name]
        if phase is not None:
            results = [r for r in results if r.phase == phase]
        return results[-limit:]

    def add_benchmark(
        self,
        benchmark_name: str,
        phase: ResponsePhase = ResponsePhase.DETECTION,
        speed: ResponseSpeed = ResponseSpeed.ACCEPTABLE,
        target_minutes: float = 30.0,
        percentile: float = 95.0,
    ) -> ResponseBenchmark:
        benchmark = ResponseBenchmark(
            benchmark_name=benchmark_name,
            phase=phase,
            speed=speed,
            target_minutes=target_minutes,
            percentile=percentile,
        )
        self._benchmarks.append(benchmark)
        if len(self._benchmarks) > self._max_records:
            self._benchmarks = self._benchmarks[-self._max_records :]
        logger.info(
            "response_timer.benchmark_added",
            benchmark_name=benchmark_name,
            phase=phase.value,
            speed=speed.value,
        )
        return benchmark

    # -- domain operations -----------------------------------------------

    def analyze_response_speed(self, service_name: str) -> dict[str, Any]:
        """Analyze response speed for a specific service."""
        records = [r for r in self._records if r.service_name == service_name]
        if not records:
            return {"service_name": service_name, "status": "no_data"}
        avg_duration = round(sum(r.duration_minutes for r in records) / len(records), 2)
        return {
            "service_name": service_name,
            "avg_duration": avg_duration,
            "record_count": len(records),
            "meets_target": avg_duration <= self._target_minutes,
        }

    def identify_slow_responses(self) -> list[dict[str, Any]]:
        """Find services with >1 SLOW or CRITICAL response."""
        slow_counts: dict[str, int] = {}
        for r in self._records:
            if r.speed in (ResponseSpeed.SLOW, ResponseSpeed.CRITICAL):
                slow_counts[r.service_name] = slow_counts.get(r.service_name, 0) + 1
        results: list[dict[str, Any]] = []
        for svc, count in slow_counts.items():
            if count > 1:
                results.append(
                    {
                        "service_name": svc,
                        "slow_count": count,
                    }
                )
        results.sort(key=lambda x: x["slow_count"], reverse=True)
        return results

    def rank_by_response_time(self) -> list[dict[str, Any]]:
        """Rank services by avg duration_minutes ascending."""
        durations: dict[str, list[float]] = {}
        for r in self._records:
            durations.setdefault(r.service_name, []).append(r.duration_minutes)
        results: list[dict[str, Any]] = []
        for svc, vals in durations.items():
            results.append(
                {
                    "service_name": svc,
                    "avg_duration_minutes": round(sum(vals) / len(vals), 2),
                }
            )
        results.sort(key=lambda x: x["avg_duration_minutes"])
        return results

    def detect_response_trends(self) -> list[dict[str, Any]]:
        """Detect services with >3 response records."""
        counts: dict[str, int] = {}
        for r in self._records:
            counts[r.service_name] = counts.get(r.service_name, 0) + 1
        results: list[dict[str, Any]] = []
        for svc, count in counts.items():
            if count > 3:
                results.append(
                    {
                        "service_name": svc,
                        "record_count": count,
                        "trend_detected": True,
                    }
                )
        results.sort(key=lambda x: x["record_count"], reverse=True)
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> ResponseTimerReport:
        by_phase: dict[str, int] = {}
        by_speed: dict[str, int] = {}
        for r in self._records:
            by_phase[r.phase.value] = by_phase.get(r.phase.value, 0) + 1
            by_speed[r.speed.value] = by_speed.get(r.speed.value, 0) + 1
        on_target = sum(1 for r in self._records if r.duration_minutes <= self._target_minutes)
        on_target_rate = round(on_target / len(self._records) * 100, 2) if self._records else 0.0
        slow_count = sum(1 for d in self.identify_slow_responses())
        recs: list[str] = []
        if self._records and on_target_rate < 80.0:
            recs.append(f"On-target rate {on_target_rate}% is below 80.0% threshold")
        if slow_count > 0:
            recs.append(f"{slow_count} service(s) with slow responses")
        trends = len(self.detect_response_trends())
        if trends > 0:
            recs.append(f"{trends} service(s) with response trends detected")
        if not recs:
            recs.append("Response times meet targets")
        return ResponseTimerReport(
            total_responses=len(self._records),
            total_benchmarks=len(self._benchmarks),
            on_target_rate_pct=on_target_rate,
            by_phase=by_phase,
            by_speed=by_speed,
            slow_count=slow_count,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._benchmarks.clear()
        logger.info("response_timer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        phase_dist: dict[str, int] = {}
        for r in self._records:
            key = r.phase.value
            phase_dist[key] = phase_dist.get(key, 0) + 1
        return {
            "total_responses": len(self._records),
            "total_benchmarks": len(self._benchmarks),
            "target_minutes": self._target_minutes,
            "phase_distribution": phase_dist,
            "unique_services": len({r.service_name for r in self._records}),
        }
