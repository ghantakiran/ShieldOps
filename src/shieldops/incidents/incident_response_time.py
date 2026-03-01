"""Incident Response Time Tracker — track and analyze incident response times."""

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
    TRIAGE = "triage"
    INVESTIGATION = "investigation"
    MITIGATION = "mitigation"
    RESOLUTION = "resolution"


class ResponseSpeed(StrEnum):
    EXCELLENT = "excellent"
    GOOD = "good"
    ACCEPTABLE = "acceptable"
    SLOW = "slow"
    CRITICAL = "critical"


class ResponseChannel(StrEnum):
    AUTOMATED = "automated"
    PAGER = "pager"
    SLACK = "slack"
    EMAIL = "email"
    MANUAL = "manual"


# --- Models ---


class ResponseTimeRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str = ""
    response_phase: ResponsePhase = ResponsePhase.DETECTION
    response_speed: ResponseSpeed = ResponseSpeed.ACCEPTABLE
    response_channel: ResponseChannel = ResponseChannel.AUTOMATED
    response_time_minutes: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class ResponseBenchmark(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str = ""
    response_phase: ResponsePhase = ResponsePhase.DETECTION
    benchmark_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class IncidentResponseTimeReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_benchmarks: int = 0
    slow_responses: int = 0
    avg_response_time_minutes: float = 0.0
    by_phase: dict[str, int] = Field(default_factory=dict)
    by_speed: dict[str, int] = Field(default_factory=dict)
    by_channel: dict[str, int] = Field(default_factory=dict)
    top_slow_services: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class IncidentResponseTimeTracker:
    """Track and analyze incident response times."""

    def __init__(
        self,
        max_records: int = 200000,
        max_response_time_minutes: float = 30.0,
    ) -> None:
        self._max_records = max_records
        self._max_response_time_minutes = max_response_time_minutes
        self._records: list[ResponseTimeRecord] = []
        self._benchmarks: list[ResponseBenchmark] = []
        logger.info(
            "incident_response_time.initialized",
            max_records=max_records,
            max_response_time_minutes=max_response_time_minutes,
        )

    # -- record / get / list ------------------------------------------------

    def record_response(
        self,
        incident_id: str,
        response_phase: ResponsePhase = ResponsePhase.DETECTION,
        response_speed: ResponseSpeed = ResponseSpeed.ACCEPTABLE,
        response_channel: ResponseChannel = ResponseChannel.AUTOMATED,
        response_time_minutes: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> ResponseTimeRecord:
        record = ResponseTimeRecord(
            incident_id=incident_id,
            response_phase=response_phase,
            response_speed=response_speed,
            response_channel=response_channel,
            response_time_minutes=response_time_minutes,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "incident_response_time.response_recorded",
            record_id=record.id,
            incident_id=incident_id,
            response_phase=response_phase.value,
            response_speed=response_speed.value,
        )
        return record

    def get_response(self, record_id: str) -> ResponseTimeRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_responses(
        self,
        response_phase: ResponsePhase | None = None,
        response_speed: ResponseSpeed | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[ResponseTimeRecord]:
        results = list(self._records)
        if response_phase is not None:
            results = [r for r in results if r.response_phase == response_phase]
        if response_speed is not None:
            results = [r for r in results if r.response_speed == response_speed]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_benchmark(
        self,
        incident_id: str,
        response_phase: ResponsePhase = ResponsePhase.DETECTION,
        benchmark_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> ResponseBenchmark:
        benchmark = ResponseBenchmark(
            incident_id=incident_id,
            response_phase=response_phase,
            benchmark_score=benchmark_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._benchmarks.append(benchmark)
        if len(self._benchmarks) > self._max_records:
            self._benchmarks = self._benchmarks[-self._max_records :]
        logger.info(
            "incident_response_time.benchmark_added",
            incident_id=incident_id,
            response_phase=response_phase.value,
            benchmark_score=benchmark_score,
        )
        return benchmark

    # -- domain operations --------------------------------------------------

    def analyze_response_distribution(self) -> dict[str, Any]:
        """Group by response_phase; return count and avg response time."""
        phase_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.response_phase.value
            phase_data.setdefault(key, []).append(r.response_time_minutes)
        result: dict[str, Any] = {}
        for phase, times in phase_data.items():
            result[phase] = {
                "count": len(times),
                "avg_response_time": round(sum(times) / len(times), 2),
            }
        return result

    def identify_slow_responses(self) -> list[dict[str, Any]]:
        """Return responses where response_time > max_response_time_minutes."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.response_time_minutes > self._max_response_time_minutes:
                results.append(
                    {
                        "record_id": r.id,
                        "incident_id": r.incident_id,
                        "response_phase": r.response_phase.value,
                        "response_speed": r.response_speed.value,
                        "response_time_minutes": r.response_time_minutes,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        results.sort(key=lambda x: x["response_time_minutes"], reverse=True)
        return results

    def rank_by_response_time(self) -> list[dict[str, Any]]:
        """Group by service, avg response time, sort desc."""
        service_times: dict[str, list[float]] = {}
        for r in self._records:
            service_times.setdefault(r.service, []).append(r.response_time_minutes)
        results: list[dict[str, Any]] = []
        for svc, times in service_times.items():
            results.append(
                {
                    "service": svc,
                    "avg_response_time": round(sum(times) / len(times), 2),
                    "record_count": len(times),
                }
            )
        results.sort(key=lambda x: x["avg_response_time"], reverse=True)
        return results

    def detect_response_trends(self) -> dict[str, Any]:
        """Split-half comparison on benchmark_score; delta threshold 5.0."""
        if len(self._benchmarks) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        scores = [b.benchmark_score for b in self._benchmarks]
        mid = len(scores) // 2
        first_half = scores[:mid]
        second_half = scores[mid:]
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

    def generate_report(self) -> IncidentResponseTimeReport:
        by_phase: dict[str, int] = {}
        by_speed: dict[str, int] = {}
        by_channel: dict[str, int] = {}
        for r in self._records:
            by_phase[r.response_phase.value] = by_phase.get(r.response_phase.value, 0) + 1
            by_speed[r.response_speed.value] = by_speed.get(r.response_speed.value, 0) + 1
            by_channel[r.response_channel.value] = by_channel.get(r.response_channel.value, 0) + 1
        slow_responses = len(self.identify_slow_responses())
        avg_response_time = (
            round(
                sum(r.response_time_minutes for r in self._records) / len(self._records),
                2,
            )
            if self._records
            else 0.0
        )
        slow_list = self.identify_slow_responses()
        top_slow_services = list(dict.fromkeys(s["service"] for s in slow_list))
        recs: list[str] = []
        if slow_responses > 0:
            recs.append(f"{slow_responses} slow response(s) detected — review response procedures")
        over_threshold = sum(
            1 for r in self._records if r.response_time_minutes > self._max_response_time_minutes
        )
        if over_threshold > 0:
            recs.append(
                f"{over_threshold} response(s) above threshold"
                f" ({self._max_response_time_minutes} min)"
            )
        if not recs:
            recs.append("Response time levels are acceptable")
        return IncidentResponseTimeReport(
            total_records=len(self._records),
            total_benchmarks=len(self._benchmarks),
            slow_responses=slow_responses,
            avg_response_time_minutes=avg_response_time,
            by_phase=by_phase,
            by_speed=by_speed,
            by_channel=by_channel,
            top_slow_services=top_slow_services,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._benchmarks.clear()
        logger.info("incident_response_time.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        phase_dist: dict[str, int] = {}
        for r in self._records:
            key = r.response_phase.value
            phase_dist[key] = phase_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_benchmarks": len(self._benchmarks),
            "max_response_time_minutes": self._max_response_time_minutes,
            "phase_distribution": phase_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_incidents": len({r.incident_id for r in self._records}),
        }
