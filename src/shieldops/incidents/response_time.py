"""Incident Response Time Analyzer — measure and analyze incident response times."""

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


class ResponseTrend(StrEnum):
    IMPROVING = "improving"
    STABLE = "stable"
    DEGRADING = "degrading"
    VOLATILE = "volatile"
    INSUFFICIENT_DATA = "insufficient_data"


# --- Models ---


class ResponseTimeRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str = ""
    phase: ResponsePhase = ResponsePhase.DETECTION
    response_minutes: float = 0.0
    speed: ResponseSpeed = ResponseSpeed.ACCEPTABLE
    team: str = ""
    service: str = ""
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class PhaseBreakdown(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str = ""
    phase: ResponsePhase = ResponsePhase.DETECTION
    start_minutes: float = 0.0
    end_minutes: float = 0.0
    duration_minutes: float = 0.0
    created_at: float = Field(default_factory=time.time)


class ResponseTimeReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_breakdowns: int = 0
    avg_response_minutes: float = 0.0
    by_phase: dict[str, int] = Field(default_factory=dict)
    by_speed: dict[str, int] = Field(default_factory=dict)
    by_team: list[str] = Field(default_factory=list)
    slow_incidents: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class IncidentResponseTimeAnalyzer:
    """Measure and analyze incident response times across phases, teams, and services."""

    def __init__(
        self,
        max_records: int = 200000,
        max_response_time_minutes: float = 30.0,
    ) -> None:
        self._max_records = max_records
        self._max_response_time_minutes = max_response_time_minutes
        self._records: list[ResponseTimeRecord] = []
        self._breakdowns: list[PhaseBreakdown] = []
        logger.info(
            "response_time.initialized",
            max_records=max_records,
            max_response_time_minutes=max_response_time_minutes,
        )

    # -- record / get / list ---------------------------------------------

    def record_response(
        self,
        incident_id: str,
        phase: ResponsePhase = ResponsePhase.DETECTION,
        response_minutes: float = 0.0,
        speed: ResponseSpeed = ResponseSpeed.ACCEPTABLE,
        team: str = "",
        service: str = "",
        details: str = "",
    ) -> ResponseTimeRecord:
        record = ResponseTimeRecord(
            incident_id=incident_id,
            phase=phase,
            response_minutes=response_minutes,
            speed=speed,
            team=team,
            service=service,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "response_time.recorded",
            record_id=record.id,
            incident_id=incident_id,
            phase=phase.value,
            speed=speed.value,
        )
        return record

    def get_response(self, record_id: str) -> ResponseTimeRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_responses(
        self,
        phase: ResponsePhase | None = None,
        speed: ResponseSpeed | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[ResponseTimeRecord]:
        results = list(self._records)
        if phase is not None:
            results = [r for r in results if r.phase == phase]
        if speed is not None:
            results = [r for r in results if r.speed == speed]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_breakdown(
        self,
        incident_id: str,
        phase: ResponsePhase = ResponsePhase.DETECTION,
        start_minutes: float = 0.0,
        end_minutes: float = 0.0,
        duration_minutes: float = 0.0,
    ) -> PhaseBreakdown:
        breakdown = PhaseBreakdown(
            incident_id=incident_id,
            phase=phase,
            start_minutes=start_minutes,
            end_minutes=end_minutes,
            duration_minutes=duration_minutes,
        )
        self._breakdowns.append(breakdown)
        if len(self._breakdowns) > self._max_records:
            self._breakdowns = self._breakdowns[-self._max_records :]
        logger.info(
            "response_time.breakdown_added",
            incident_id=incident_id,
            phase=phase.value,
            duration_minutes=duration_minutes,
        )
        return breakdown

    # -- domain operations -----------------------------------------------

    def analyze_response_by_phase(self) -> list[dict[str, Any]]:
        """Analyze average response time per phase."""
        phase_times: dict[str, list[float]] = {}
        for r in self._records:
            phase_times.setdefault(r.phase.value, []).append(r.response_minutes)
        results: list[dict[str, Any]] = []
        for phase, times in phase_times.items():
            results.append(
                {
                    "phase": phase,
                    "avg_response_minutes": round(sum(times) / len(times), 2),
                    "record_count": len(times),
                }
            )
        results.sort(key=lambda x: x["avg_response_minutes"], reverse=True)
        return results

    def identify_slow_responses(self) -> list[dict[str, Any]]:
        """Find incidents where response_minutes exceeds the max threshold."""
        slow: list[dict[str, Any]] = []
        for r in self._records:
            if r.response_minutes > self._max_response_time_minutes:
                slow.append(
                    {
                        "record_id": r.id,
                        "incident_id": r.incident_id,
                        "phase": r.phase.value,
                        "response_minutes": r.response_minutes,
                        "team": r.team,
                    }
                )
        slow.sort(key=lambda x: x["response_minutes"], reverse=True)
        return slow

    def rank_by_response_time(self) -> list[dict[str, Any]]:
        """Rank teams by average response time."""
        team_times: dict[str, list[float]] = {}
        for r in self._records:
            team_times.setdefault(r.team, []).append(r.response_minutes)
        results: list[dict[str, Any]] = []
        for team, times in team_times.items():
            results.append(
                {
                    "team": team,
                    "avg_response_minutes": round(sum(times) / len(times), 2),
                    "record_count": len(times),
                }
            )
        results.sort(key=lambda x: x["avg_response_minutes"], reverse=True)
        return results

    def detect_response_trends(self) -> list[dict[str, Any]]:
        """Detect response time trends using split-half comparison."""
        team_records: dict[str, list[float]] = {}
        for r in self._records:
            team_records.setdefault(r.team, []).append(r.response_minutes)
        results: list[dict[str, Any]] = []
        for team, times in team_records.items():
            if len(times) < 4:
                results.append({"team": team, "trend": ResponseTrend.INSUFFICIENT_DATA.value})
                continue
            mid = len(times) // 2
            first_half_avg = sum(times[:mid]) / mid
            second_half_avg = sum(times[mid:]) / (len(times) - mid)
            delta = second_half_avg - first_half_avg
            if delta > 5.0:
                trend = ResponseTrend.DEGRADING.value
            elif delta < -5.0:
                trend = ResponseTrend.IMPROVING.value
            else:
                trend = ResponseTrend.STABLE.value
            results.append(
                {
                    "team": team,
                    "first_half_avg": round(first_half_avg, 2),
                    "second_half_avg": round(second_half_avg, 2),
                    "delta": round(delta, 2),
                    "trend": trend,
                }
            )
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> ResponseTimeReport:
        by_phase: dict[str, int] = {}
        by_speed: dict[str, int] = {}
        for r in self._records:
            by_phase[r.phase.value] = by_phase.get(r.phase.value, 0) + 1
            by_speed[r.speed.value] = by_speed.get(r.speed.value, 0) + 1
        avg_response = (
            round(
                sum(r.response_minutes for r in self._records) / len(self._records),
                2,
            )
            if self._records
            else 0.0
        )
        slow = self.identify_slow_responses()
        slow_ids = [s["incident_id"] for s in slow[:10]]
        teams = sorted({r.team for r in self._records if r.team})
        recs: list[str] = []
        if avg_response > self._max_response_time_minutes:
            recs.append(
                f"Average response time {avg_response}min exceeds"
                f" {self._max_response_time_minutes}min threshold"
            )
        if len(slow) > 0:
            recs.append(f"{len(slow)} incident(s) with slow response times")
        if not recs:
            recs.append("Response times within acceptable parameters")
        return ResponseTimeReport(
            total_records=len(self._records),
            total_breakdowns=len(self._breakdowns),
            avg_response_minutes=avg_response,
            by_phase=by_phase,
            by_speed=by_speed,
            by_team=teams,
            slow_incidents=slow_ids,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._breakdowns.clear()
        logger.info("response_time.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        phase_dist: dict[str, int] = {}
        for r in self._records:
            key = r.phase.value
            phase_dist[key] = phase_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_breakdowns": len(self._breakdowns),
            "max_response_time_minutes": self._max_response_time_minutes,
            "phase_distribution": phase_dist,
            "unique_incidents": len({r.incident_id for r in self._records}),
        }
