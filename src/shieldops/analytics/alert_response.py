"""Alert Response Analyzer — analyze alert response times, identify slow responses."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ResponseAction(StrEnum):
    ACKNOWLEDGED = "acknowledged"
    INVESTIGATED = "investigated"
    ESCALATED = "escalated"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"


class ResponseSpeed(StrEnum):
    IMMEDIATE = "immediate"
    FAST = "fast"
    NORMAL = "normal"
    SLOW = "slow"
    MISSED = "missed"


class AlertOutcome(StrEnum):
    TRUE_POSITIVE = "true_positive"
    FALSE_POSITIVE = "false_positive"
    NOISE = "noise"
    DUPLICATE = "duplicate"
    INFORMATIONAL = "informational"


# --- Models ---


class AlertResponseRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    alert_id: str = ""
    response_action: ResponseAction = ResponseAction.ACKNOWLEDGED
    response_speed: ResponseSpeed = ResponseSpeed.NORMAL
    alert_outcome: AlertOutcome = AlertOutcome.TRUE_POSITIVE
    response_time_minutes: float = 0.0
    responder: str = ""
    created_at: float = Field(default_factory=time.time)


class ResponseMetric(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    metric_name: str = ""
    response_action: ResponseAction = ResponseAction.ACKNOWLEDGED
    avg_response_time: float = 0.0
    total_responses: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class AlertResponseReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_metrics: int = 0
    measured_responders: int = 0
    avg_response_time_minutes: float = 0.0
    by_action: dict[str, int] = Field(default_factory=dict)
    by_speed: dict[str, int] = Field(default_factory=dict)
    by_outcome: dict[str, int] = Field(default_factory=dict)
    slow_alerts: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class AlertResponseAnalyzer:
    """Analyze alert response times, identify slow responses, track responder performance."""

    def __init__(
        self,
        max_records: int = 200000,
        max_response_time_minutes: float = 15.0,
    ) -> None:
        self._max_records = max_records
        self._max_response_time_minutes = max_response_time_minutes
        self._records: list[AlertResponseRecord] = []
        self._metrics: list[ResponseMetric] = []
        logger.info(
            "alert_response.initialized",
            max_records=max_records,
            max_response_time_minutes=max_response_time_minutes,
        )

    # -- record / get / list ------------------------------------------------

    def record_response(
        self,
        alert_id: str,
        response_action: ResponseAction = ResponseAction.ACKNOWLEDGED,
        response_speed: ResponseSpeed = ResponseSpeed.NORMAL,
        alert_outcome: AlertOutcome = AlertOutcome.TRUE_POSITIVE,
        response_time_minutes: float = 0.0,
        responder: str = "",
    ) -> AlertResponseRecord:
        record = AlertResponseRecord(
            alert_id=alert_id,
            response_action=response_action,
            response_speed=response_speed,
            alert_outcome=alert_outcome,
            response_time_minutes=response_time_minutes,
            responder=responder,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "alert_response.response_recorded",
            record_id=record.id,
            alert_id=alert_id,
            response_action=response_action.value,
            response_time_minutes=response_time_minutes,
        )
        return record

    def get_response(self, record_id: str) -> AlertResponseRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_responses(
        self,
        response_action: ResponseAction | None = None,
        response_speed: ResponseSpeed | None = None,
        responder: str | None = None,
        limit: int = 50,
    ) -> list[AlertResponseRecord]:
        results = list(self._records)
        if response_action is not None:
            results = [r for r in results if r.response_action == response_action]
        if response_speed is not None:
            results = [r for r in results if r.response_speed == response_speed]
        if responder is not None:
            results = [r for r in results if r.responder == responder]
        return results[-limit:]

    def add_metric(
        self,
        metric_name: str,
        response_action: ResponseAction = ResponseAction.ACKNOWLEDGED,
        avg_response_time: float = 0.0,
        total_responses: int = 0,
        description: str = "",
    ) -> ResponseMetric:
        metric = ResponseMetric(
            metric_name=metric_name,
            response_action=response_action,
            avg_response_time=avg_response_time,
            total_responses=total_responses,
            description=description,
        )
        self._metrics.append(metric)
        if len(self._metrics) > self._max_records:
            self._metrics = self._metrics[-self._max_records :]
        logger.info(
            "alert_response.metric_added",
            metric_name=metric_name,
            response_action=response_action.value,
            avg_response_time=avg_response_time,
        )
        return metric

    # -- domain operations --------------------------------------------------

    def analyze_response_times(self) -> dict[str, Any]:
        """Group by response_action; return count and avg response_time_minutes per action."""
        action_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.response_action.value
            action_data.setdefault(key, []).append(r.response_time_minutes)
        result: dict[str, Any] = {}
        for action, times in action_data.items():
            result[action] = {
                "count": len(times),
                "avg_response_time_minutes": round(sum(times) / len(times), 2),
            }
        return result

    def identify_slow_responses(self) -> list[dict[str, Any]]:
        """Return records where response_time_minutes > max_response_time_minutes."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.response_time_minutes > self._max_response_time_minutes:
                results.append(
                    {
                        "record_id": r.id,
                        "alert_id": r.alert_id,
                        "response_time_minutes": r.response_time_minutes,
                        "response_action": r.response_action.value,
                        "responder": r.responder,
                    }
                )
        return results

    def rank_by_response_speed(self) -> list[dict[str, Any]]:
        """Group by responder, total response_time_minutes, sort ascending (fastest first)."""
        responder_times: dict[str, float] = {}
        for r in self._records:
            responder_times[r.responder] = (
                responder_times.get(r.responder, 0) + r.response_time_minutes
            )
        results: list[dict[str, Any]] = []
        for responder, total in responder_times.items():
            results.append(
                {
                    "responder": responder,
                    "total_response_time": total,
                }
            )
        results.sort(key=lambda x: x["total_response_time"])
        return results

    def detect_response_patterns(self) -> dict[str, Any]:
        """Split-half on response_time_minutes; delta threshold 5.0."""
        if len(self._records) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        counts = [r.response_time_minutes for r in self._records]
        mid = len(counts) // 2
        first_half = counts[:mid]
        second_half = counts[mid:]
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

    def generate_report(self) -> AlertResponseReport:
        by_action: dict[str, int] = {}
        by_speed: dict[str, int] = {}
        by_outcome: dict[str, int] = {}
        for r in self._records:
            by_action[r.response_action.value] = by_action.get(r.response_action.value, 0) + 1
            by_speed[r.response_speed.value] = by_speed.get(r.response_speed.value, 0) + 1
            by_outcome[r.alert_outcome.value] = by_outcome.get(r.alert_outcome.value, 0) + 1
        slow_count = sum(
            1 for r in self._records if r.response_time_minutes > self._max_response_time_minutes
        )
        measured_responders = len(
            {r.responder for r in self._records if r.response_time_minutes > 0}
        )
        avg_time = (
            round(
                sum(r.response_time_minutes for r in self._records) / len(self._records),
                2,
            )
            if self._records
            else 0.0
        )
        slow_alert_ids = [
            r.alert_id
            for r in self._records
            if r.response_time_minutes > self._max_response_time_minutes
        ][:5]
        recs: list[str] = []
        if slow_count > 0:
            recs.append(
                f"{slow_count} response(s) exceeded maximum time"
                f" ({self._max_response_time_minutes} min)"
            )
        if self._records and avg_time > self._max_response_time_minutes:
            recs.append(
                f"Average response time {avg_time} min exceeds threshold"
                f" ({self._max_response_time_minutes} min)"
            )
        if not recs:
            recs.append("Alert response times are healthy")
        return AlertResponseReport(
            total_records=len(self._records),
            total_metrics=len(self._metrics),
            measured_responders=measured_responders,
            avg_response_time_minutes=avg_time,
            by_action=by_action,
            by_speed=by_speed,
            by_outcome=by_outcome,
            slow_alerts=slow_alert_ids,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._metrics.clear()
        logger.info("alert_response.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        action_dist: dict[str, int] = {}
        for r in self._records:
            key = r.response_action.value
            action_dist[key] = action_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_metrics": len(self._metrics),
            "max_response_time_minutes": self._max_response_time_minutes,
            "action_distribution": action_dist,
            "unique_alerts": len({r.alert_id for r in self._records}),
            "unique_responders": len({r.responder for r in self._records}),
        }
