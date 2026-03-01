"""Incident Response Optimizer — optimize response times, bottlenecks, and efficiency."""

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


class ResponseEfficiency(StrEnum):
    EXCELLENT = "excellent"
    GOOD = "good"
    ADEQUATE = "adequate"
    SLOW = "slow"
    CRITICAL = "critical"


class EscalationLevel(StrEnum):
    L1 = "l1"
    L2 = "l2"
    L3 = "l3"
    MANAGEMENT = "management"
    EXECUTIVE = "executive"


# --- Models ---


class ResponseRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str = ""
    response_phase: ResponsePhase = ResponsePhase.DETECTION
    response_efficiency: ResponseEfficiency = ResponseEfficiency.ADEQUATE
    escalation_level: EscalationLevel = EscalationLevel.L1
    response_time_minutes: float = 0.0
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class ResponsePattern(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    phase_pattern: str = ""
    response_phase: ResponsePhase = ResponsePhase.DETECTION
    efficiency_threshold: float = 0.0
    avg_time_minutes: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ResponseOptimizerReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_patterns: int = 0
    slow_responses: int = 0
    avg_response_time: float = 0.0
    by_phase: dict[str, int] = Field(default_factory=dict)
    by_efficiency: dict[str, int] = Field(default_factory=dict)
    by_escalation: dict[str, int] = Field(default_factory=dict)
    bottlenecks: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class IncidentResponseOptimizer:
    """Optimize incident response times, identify bottlenecks, track efficiency."""

    def __init__(
        self,
        max_records: int = 200000,
        max_response_time_minutes: float = 30.0,
    ) -> None:
        self._max_records = max_records
        self._max_response_time_minutes = max_response_time_minutes
        self._records: list[ResponseRecord] = []
        self._patterns: list[ResponsePattern] = []
        logger.info(
            "response_optimizer.initialized",
            max_records=max_records,
            max_response_time_minutes=max_response_time_minutes,
        )

    # -- record / get / list ------------------------------------------------

    def record_response(
        self,
        incident_id: str,
        response_phase: ResponsePhase = ResponsePhase.DETECTION,
        response_efficiency: ResponseEfficiency = ResponseEfficiency.ADEQUATE,
        escalation_level: EscalationLevel = EscalationLevel.L1,
        response_time_minutes: float = 0.0,
        team: str = "",
    ) -> ResponseRecord:
        record = ResponseRecord(
            incident_id=incident_id,
            response_phase=response_phase,
            response_efficiency=response_efficiency,
            escalation_level=escalation_level,
            response_time_minutes=response_time_minutes,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "response_optimizer.response_recorded",
            record_id=record.id,
            incident_id=incident_id,
            response_phase=response_phase.value,
            response_efficiency=response_efficiency.value,
        )
        return record

    def get_response(self, record_id: str) -> ResponseRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_responses(
        self,
        phase: ResponsePhase | None = None,
        efficiency: ResponseEfficiency | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[ResponseRecord]:
        results = list(self._records)
        if phase is not None:
            results = [r for r in results if r.response_phase == phase]
        if efficiency is not None:
            results = [r for r in results if r.response_efficiency == efficiency]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_pattern(
        self,
        phase_pattern: str,
        response_phase: ResponsePhase = ResponsePhase.DETECTION,
        efficiency_threshold: float = 0.0,
        avg_time_minutes: float = 0.0,
        description: str = "",
    ) -> ResponsePattern:
        pattern = ResponsePattern(
            phase_pattern=phase_pattern,
            response_phase=response_phase,
            efficiency_threshold=efficiency_threshold,
            avg_time_minutes=avg_time_minutes,
            description=description,
        )
        self._patterns.append(pattern)
        if len(self._patterns) > self._max_records:
            self._patterns = self._patterns[-self._max_records :]
        logger.info(
            "response_optimizer.pattern_added",
            phase_pattern=phase_pattern,
            response_phase=response_phase.value,
            efficiency_threshold=efficiency_threshold,
        )
        return pattern

    # -- domain operations --------------------------------------------------

    def analyze_response_efficiency(self) -> dict[str, Any]:
        """Group by phase; return count and avg response time per phase."""
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

    def identify_bottlenecks(self) -> list[dict[str, Any]]:
        """Return records where efficiency is SLOW or CRITICAL."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.response_efficiency in (ResponseEfficiency.SLOW, ResponseEfficiency.CRITICAL):
                results.append(
                    {
                        "record_id": r.id,
                        "incident_id": r.incident_id,
                        "response_phase": r.response_phase.value,
                        "response_time_minutes": r.response_time_minutes,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_response_time(self) -> list[dict[str, Any]]:
        """Group by team, avg response time, sort descending."""
        team_times: dict[str, list[float]] = {}
        for r in self._records:
            team_times.setdefault(r.team, []).append(r.response_time_minutes)
        results: list[dict[str, Any]] = []
        for team, times in team_times.items():
            results.append(
                {
                    "team": team,
                    "avg_response_time": round(sum(times) / len(times), 2),
                    "count": len(times),
                }
            )
        results.sort(key=lambda x: x["avg_response_time"], reverse=True)
        return results

    def detect_response_trends(self) -> dict[str, Any]:
        """Split-half on avg_time_minutes; delta threshold 5.0."""
        if len(self._patterns) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        times = [p.avg_time_minutes for p in self._patterns]
        mid = len(times) // 2
        first_half = times[:mid]
        second_half = times[mid:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        delta = round(avg_second - avg_first, 2)
        if abs(delta) < 5.0:
            trend = "stable"
        elif delta > 0:
            trend = "increasing"
        else:
            trend = "decreasing"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> ResponseOptimizerReport:
        by_phase: dict[str, int] = {}
        by_efficiency: dict[str, int] = {}
        by_escalation: dict[str, int] = {}
        for r in self._records:
            by_phase[r.response_phase.value] = by_phase.get(r.response_phase.value, 0) + 1
            by_efficiency[r.response_efficiency.value] = (
                by_efficiency.get(r.response_efficiency.value, 0) + 1
            )
            by_escalation[r.escalation_level.value] = (
                by_escalation.get(r.escalation_level.value, 0) + 1
            )
        slow_count = sum(
            1
            for r in self._records
            if r.response_efficiency in (ResponseEfficiency.SLOW, ResponseEfficiency.CRITICAL)
        )
        avg_time = (
            round(sum(r.response_time_minutes for r in self._records) / len(self._records), 2)
            if self._records
            else 0.0
        )
        rankings = self.rank_by_response_time()
        bottlenecks = [rk["team"] for rk in rankings[:5]]
        recs: list[str] = []
        if avg_time > self._max_response_time_minutes:
            recs.append(
                f"Avg response time {avg_time}min exceeds "
                f"threshold ({self._max_response_time_minutes}min)"
            )
        if slow_count > 0:
            recs.append(f"{slow_count} slow response(s) detected — review bottlenecks")
        if not recs:
            recs.append("Response times are within acceptable limits")
        return ResponseOptimizerReport(
            total_records=len(self._records),
            total_patterns=len(self._patterns),
            slow_responses=slow_count,
            avg_response_time=avg_time,
            by_phase=by_phase,
            by_efficiency=by_efficiency,
            by_escalation=by_escalation,
            bottlenecks=bottlenecks,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._patterns.clear()
        logger.info("response_optimizer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        phase_dist: dict[str, int] = {}
        for r in self._records:
            key = r.response_phase.value
            phase_dist[key] = phase_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_patterns": len(self._patterns),
            "max_response_time_minutes": self._max_response_time_minutes,
            "phase_distribution": phase_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_incidents": len({r.incident_id for r in self._records}),
        }
