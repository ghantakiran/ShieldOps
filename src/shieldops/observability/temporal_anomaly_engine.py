"""Temporal Anomaly Engine

Detects time-context violations such as off-hours
deployments, unexpected access, and schedule drift.
"""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class TemporalContext(StrEnum):
    BUSINESS_HOURS = "business_hours"
    OFF_HOURS = "off_hours"
    WEEKEND = "weekend"
    HOLIDAY = "holiday"
    CHANGE_WINDOW = "change_window"
    MAINTENANCE = "maintenance"


class TemporalViolation(StrEnum):
    OFF_HOURS_DEPLOY = "off_hours_deploy"
    UNEXPECTED_ACCESS = "unexpected_access"
    WINDOW_BREACH = "window_breach"
    SCHEDULE_DRIFT = "schedule_drift"
    UNUSUAL_FREQUENCY = "unusual_frequency"


class RiskLevel(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"


# --- Models ---


class TemporalAnomalyRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = ""
    service: str = ""
    timestamp_hour: int = 0
    day_of_week: str = ""
    temporal_context: TemporalContext = TemporalContext.BUSINESS_HOURS
    violation_type: TemporalViolation = TemporalViolation.SCHEDULE_DRIFT
    risk_level: RiskLevel = RiskLevel.MEDIUM
    expected_window: str = ""
    operator: str = ""
    created_at: float = Field(default_factory=time.time)


class TemporalAnomalyAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service: str = ""
    analysis_score: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class TemporalAnomalyReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    violation_count: int = 0
    schedule_adherence_pct: float = 0.0
    by_context: dict[str, int] = Field(default_factory=dict)
    by_violation: dict[str, int] = Field(default_factory=dict)
    by_risk: dict[str, int] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class TemporalAnomalyEngine:
    """Temporal Anomaly Engine

    Detects time-context violations such as off-hours
    deployments and schedule drift.
    """

    def __init__(
        self,
        max_records: int = 200000,
        risk_threshold: float = 0.5,
    ) -> None:
        self._max_records = max_records
        self._risk_threshold = risk_threshold
        self._records: list[TemporalAnomalyRecord] = []
        self._analyses: list[TemporalAnomalyAnalysis] = []
        logger.info(
            "temporal_anomaly_engine.initialized",
            max_records=max_records,
            risk_threshold=risk_threshold,
        )

    def add_record(
        self,
        event_type: str,
        service: str,
        timestamp_hour: int = 0,
        day_of_week: str = "",
        temporal_context: TemporalContext = (TemporalContext.BUSINESS_HOURS),
        violation_type: TemporalViolation = (TemporalViolation.SCHEDULE_DRIFT),
        risk_level: RiskLevel = RiskLevel.MEDIUM,
        expected_window: str = "",
        operator: str = "",
    ) -> TemporalAnomalyRecord:
        record = TemporalAnomalyRecord(
            event_type=event_type,
            service=service,
            timestamp_hour=timestamp_hour,
            day_of_week=day_of_week,
            temporal_context=temporal_context,
            violation_type=violation_type,
            risk_level=risk_level,
            expected_window=expected_window,
            operator=operator,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "temporal_anomaly_engine.record_added",
            record_id=record.id,
            event_type=event_type,
            service=service,
        )
        return record

    def detect_temporal_violations(self, service: str = "") -> list[dict[str, Any]]:
        matching = list(self._records)
        if service:
            matching = [r for r in matching if r.service == service]
        violations = [r for r in matching if r.risk_level in (RiskLevel.CRITICAL, RiskLevel.HIGH)]
        return [
            {
                "event_type": r.event_type,
                "service": r.service,
                "violation": r.violation_type.value,
                "risk": r.risk_level.value,
                "hour": r.timestamp_hour,
                "day": r.day_of_week,
                "operator": r.operator,
            }
            for r in violations
        ]

    def compute_schedule_adherence(self, service: str = "") -> dict[str, Any]:
        matching = list(self._records)
        if service:
            matching = [r for r in matching if r.service == service]
        if not matching:
            return {
                "service": service or "all",
                "status": "no_data",
            }
        in_window = sum(
            1
            for r in matching
            if r.temporal_context
            in (
                TemporalContext.BUSINESS_HOURS,
                TemporalContext.CHANGE_WINDOW,
                TemporalContext.MAINTENANCE,
            )
        )
        adherence = round(in_window / len(matching), 4)
        return {
            "service": service or "all",
            "total_events": len(matching),
            "in_window": in_window,
            "adherence_pct": adherence,
        }

    def identify_unusual_patterns(
        self,
    ) -> list[dict[str, Any]]:
        hour_counts: dict[int, int] = {}
        for r in self._records:
            hour_counts[r.timestamp_hour] = hour_counts.get(r.timestamp_hour, 0) + 1
        if not hour_counts:
            return []
        total = sum(hour_counts.values())
        avg = total / max(len(hour_counts), 1)
        unusual = []
        for hour, count in sorted(hour_counts.items()):
            if count > avg * 2:
                unusual.append(
                    {
                        "hour": hour,
                        "count": count,
                        "ratio_vs_avg": round(count / avg, 2),
                    }
                )
        return unusual

    def process(self, service: str) -> dict[str, Any]:
        matching = [r for r in self._records if r.service == service]
        if not matching:
            return {
                "service": service,
                "status": "no_data",
            }
        violations = sum(
            1 for r in matching if r.risk_level in (RiskLevel.CRITICAL, RiskLevel.HIGH)
        )
        in_window = sum(
            1
            for r in matching
            if r.temporal_context
            in (
                TemporalContext.BUSINESS_HOURS,
                TemporalContext.CHANGE_WINDOW,
            )
        )
        adherence = round(in_window / len(matching), 4)
        return {
            "service": service,
            "event_count": len(matching),
            "violations": violations,
            "adherence_pct": adherence,
        }

    def generate_report(self) -> TemporalAnomalyReport:
        by_ctx: dict[str, int] = {}
        by_viol: dict[str, int] = {}
        by_risk: dict[str, int] = {}
        for r in self._records:
            cv = r.temporal_context.value
            by_ctx[cv] = by_ctx.get(cv, 0) + 1
            vv = r.violation_type.value
            by_viol[vv] = by_viol.get(vv, 0) + 1
            rv = r.risk_level.value
            by_risk[rv] = by_risk.get(rv, 0) + 1
        total = len(self._records)
        violations = by_risk.get("critical", 0) + by_risk.get("high", 0)
        in_window = (
            by_ctx.get("business_hours", 0)
            + by_ctx.get("change_window", 0)
            + by_ctx.get("maintenance", 0)
        )
        adherence = round(in_window / total, 4) if total else 0.0
        recs: list[str] = []
        if violations > 0:
            recs.append(f"{violations} high/critical temporal violations detected")
        if adherence < 0.7:
            recs.append(f"Schedule adherence {adherence:.0%} — enforce change windows")
        if not recs:
            recs.append("Temporal compliance is nominal")
        return TemporalAnomalyReport(
            total_records=total,
            total_analyses=len(self._analyses),
            violation_count=violations,
            schedule_adherence_pct=adherence,
            by_context=by_ctx,
            by_violation=by_viol,
            by_risk=by_risk,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        risk_dist: dict[str, int] = {}
        for r in self._records:
            k = r.risk_level.value
            risk_dist[k] = risk_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "risk_threshold": self._risk_threshold,
            "risk_distribution": risk_dist,
            "unique_services": len({r.service for r in self._records}),
            "unique_operators": len({r.operator for r in self._records}),
        }

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("temporal_anomaly_engine.cleared")
        return {"status": "cleared"}
