"""Incident Prevention Engine — proactive incident prevention using precursor signals."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class PrecursorType(StrEnum):
    METRIC_ANOMALY = "metric_anomaly"
    LOG_PATTERN = "log_pattern"
    DEPENDENCY_DEGRADATION = "dependency_degradation"
    CAPACITY_TREND = "capacity_trend"
    SECURITY_SIGNAL = "security_signal"


class PreventionAction(StrEnum):
    AUTO_SCALE = "auto_scale"
    CIRCUIT_BREAK = "circuit_break"
    TRAFFIC_SHIFT = "traffic_shift"
    ALERT_TEAM = "alert_team"
    ROLLBACK = "rollback"


class PreventionOutcome(StrEnum):
    PREVENTED = "prevented"
    MITIGATED = "mitigated"
    FALSE_ALARM = "false_alarm"
    MISSED = "missed"
    INCONCLUSIVE = "inconclusive"


# --- Models ---


class PreventionRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    precursor_type: PrecursorType = PrecursorType.METRIC_ANOMALY
    prevention_action: PreventionAction = PreventionAction.ALERT_TEAM
    prevention_outcome: PreventionOutcome = PreventionOutcome.PREVENTED
    lead_time_minutes: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class PrecursorSignal(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    signal_name: str = ""
    precursor_type: PrecursorType = PrecursorType.LOG_PATTERN
    prevention_action: PreventionAction = PreventionAction.AUTO_SCALE
    confidence_score: float = 0.0
    created_at: float = Field(default_factory=time.time)


class PreventionEngineReport(BaseModel):
    total_preventions: int = 0
    total_signals: int = 0
    prevention_rate_pct: float = 0.0
    by_precursor: dict[str, int] = Field(default_factory=dict)
    by_outcome: dict[str, int] = Field(default_factory=dict)
    missed_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class IncidentPreventionEngine:
    """Proactive incident prevention using precursor signals."""

    def __init__(
        self,
        max_records: int = 200000,
        min_confidence_pct: float = 60.0,
    ) -> None:
        self._max_records = max_records
        self._min_confidence_pct = min_confidence_pct
        self._records: list[PreventionRecord] = []
        self._signals: list[PrecursorSignal] = []
        logger.info(
            "prevention_engine.initialized",
            max_records=max_records,
            min_confidence_pct=min_confidence_pct,
        )

    # -- record / get / list ---------------------------------------------

    def record_prevention(
        self,
        service_name: str,
        precursor_type: PrecursorType = PrecursorType.METRIC_ANOMALY,
        prevention_action: PreventionAction = PreventionAction.ALERT_TEAM,
        prevention_outcome: PreventionOutcome = PreventionOutcome.PREVENTED,
        lead_time_minutes: float = 0.0,
        details: str = "",
    ) -> PreventionRecord:
        record = PreventionRecord(
            service_name=service_name,
            precursor_type=precursor_type,
            prevention_action=prevention_action,
            prevention_outcome=prevention_outcome,
            lead_time_minutes=lead_time_minutes,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "prevention_engine.recorded",
            record_id=record.id,
            service_name=service_name,
            precursor_type=precursor_type.value,
            prevention_outcome=prevention_outcome.value,
        )
        return record

    def get_prevention(self, record_id: str) -> PreventionRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_preventions(
        self,
        service_name: str | None = None,
        precursor_type: PrecursorType | None = None,
        limit: int = 50,
    ) -> list[PreventionRecord]:
        results = list(self._records)
        if service_name is not None:
            results = [r for r in results if r.service_name == service_name]
        if precursor_type is not None:
            results = [r for r in results if r.precursor_type == precursor_type]
        return results[-limit:]

    def add_signal(
        self,
        signal_name: str,
        precursor_type: PrecursorType = PrecursorType.LOG_PATTERN,
        prevention_action: PreventionAction = PreventionAction.AUTO_SCALE,
        confidence_score: float = 0.0,
    ) -> PrecursorSignal:
        signal = PrecursorSignal(
            signal_name=signal_name,
            precursor_type=precursor_type,
            prevention_action=prevention_action,
            confidence_score=confidence_score,
        )
        self._signals.append(signal)
        if len(self._signals) > self._max_records:
            self._signals = self._signals[-self._max_records :]
        logger.info(
            "prevention_engine.signal_added",
            signal_name=signal_name,
            precursor_type=precursor_type.value,
            confidence_score=confidence_score,
        )
        return signal

    # -- domain operations -----------------------------------------------

    def analyze_prevention_effectiveness(self, service_name: str) -> dict[str, Any]:
        svc_records = [r for r in self._records if r.service_name == service_name]
        if not svc_records:
            return {"service_name": service_name, "status": "no_data"}
        prevented = sum(
            1
            for r in svc_records
            if r.prevention_outcome in (PreventionOutcome.PREVENTED, PreventionOutcome.MITIGATED)
        )
        rate = round(prevented / len(svc_records) * 100, 2)
        return {
            "service_name": service_name,
            "total_records": len(svc_records),
            "prevented_count": prevented,
            "prevention_rate_pct": rate,
            "meets_threshold": rate >= self._min_confidence_pct,
        }

    def identify_missed_preventions(self) -> list[dict[str, Any]]:
        svc_counts: dict[str, int] = {}
        for r in self._records:
            if r.prevention_outcome == PreventionOutcome.MISSED:
                svc_counts[r.service_name] = svc_counts.get(r.service_name, 0) + 1
        results: list[dict[str, Any]] = []
        for svc, count in svc_counts.items():
            if count > 1:
                results.append({"service_name": svc, "missed_count": count})
        results.sort(key=lambda x: x["missed_count"], reverse=True)
        return results

    def rank_by_lead_time(self) -> list[dict[str, Any]]:
        svc_times: dict[str, list[float]] = {}
        for r in self._records:
            svc_times.setdefault(r.service_name, []).append(r.lead_time_minutes)
        results: list[dict[str, Any]] = []
        for svc, times in svc_times.items():
            results.append(
                {
                    "service_name": svc,
                    "avg_lead_time_min": round(sum(times) / len(times), 2),
                    "record_count": len(times),
                }
            )
        results.sort(key=lambda x: x["avg_lead_time_min"], reverse=True)
        return results

    def detect_false_alarm_patterns(self) -> list[dict[str, Any]]:
        svc_counts: dict[str, int] = {}
        for r in self._records:
            if r.prevention_outcome == PreventionOutcome.FALSE_ALARM:
                svc_counts[r.service_name] = svc_counts.get(r.service_name, 0) + 1
        results: list[dict[str, Any]] = []
        for svc, count in svc_counts.items():
            if count > 3:
                results.append(
                    {
                        "service_name": svc,
                        "false_alarm_count": count,
                        "recurring": True,
                    }
                )
        results.sort(key=lambda x: x["false_alarm_count"], reverse=True)
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> PreventionEngineReport:
        by_precursor: dict[str, int] = {}
        by_outcome: dict[str, int] = {}
        for r in self._records:
            by_precursor[r.precursor_type.value] = by_precursor.get(r.precursor_type.value, 0) + 1
            by_outcome[r.prevention_outcome.value] = (
                by_outcome.get(r.prevention_outcome.value, 0) + 1
            )
        prevented = sum(
            1
            for r in self._records
            if r.prevention_outcome in (PreventionOutcome.PREVENTED, PreventionOutcome.MITIGATED)
        )
        rate = round(prevented / len(self._records) * 100, 2) if self._records else 0.0
        missed_count = sum(
            1 for r in self._records if r.prevention_outcome == PreventionOutcome.MISSED
        )
        recs: list[str] = []
        if missed_count > 0:
            recs.append(f"{missed_count} missed prevention(s) detected")
        false_alarms = len(self.detect_false_alarm_patterns())
        if false_alarms > 0:
            recs.append(f"{false_alarms} service(s) with recurring false alarm patterns")
        if not recs:
            recs.append("Prevention engine performance meets targets")
        return PreventionEngineReport(
            total_preventions=len(self._records),
            total_signals=len(self._signals),
            prevention_rate_pct=rate,
            by_precursor=by_precursor,
            by_outcome=by_outcome,
            missed_count=missed_count,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._signals.clear()
        logger.info("prevention_engine.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        precursor_dist: dict[str, int] = {}
        for r in self._records:
            key = r.precursor_type.value
            precursor_dist[key] = precursor_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_signals": len(self._signals),
            "min_confidence_pct": self._min_confidence_pct,
            "precursor_distribution": precursor_dist,
            "unique_services": len({r.service_name for r in self._records}),
        }
