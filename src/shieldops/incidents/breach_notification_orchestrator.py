"""Breach Notification Orchestrator — orchestrate breach notifications across channels."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class NotificationChannel(StrEnum):
    EMAIL = "email"
    REGULATOR = "regulator"
    AFFECTED_USERS = "affected_users"
    MEDIA = "media"
    INTERNAL = "internal"


class NotificationDeadline(StrEnum):
    HOURS_24 = "hours_24"
    HOURS_48 = "hours_48"
    HOURS_72 = "hours_72"
    DAYS_30 = "days_30"
    DAYS_60 = "days_60"


class BreachSeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"


# --- Models ---


class NotificationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    breach_id: str = ""
    notification_channel: NotificationChannel = NotificationChannel.INTERNAL
    notification_deadline: NotificationDeadline = NotificationDeadline.HOURS_72
    breach_severity: BreachSeverity = BreachSeverity.MEDIUM
    delivery_score: float = 0.0
    responder: str = ""
    business_unit: str = ""
    created_at: float = Field(default_factory=time.time)


class NotificationAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    breach_id: str = ""
    notification_channel: NotificationChannel = NotificationChannel.INTERNAL
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class BreachNotificationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_delivery_score: float = 0.0
    by_channel: dict[str, int] = Field(default_factory=dict)
    by_deadline: dict[str, int] = Field(default_factory=dict)
    by_severity: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class BreachNotificationOrchestrator:
    """Orchestrate breach notifications; track delivery and deadline compliance."""

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[NotificationRecord] = []
        self._analyses: list[NotificationAnalysis] = []
        logger.info(
            "breach_notification_orchestrator.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_notification(
        self,
        breach_id: str,
        notification_channel: NotificationChannel = NotificationChannel.INTERNAL,
        notification_deadline: NotificationDeadline = NotificationDeadline.HOURS_72,
        breach_severity: BreachSeverity = BreachSeverity.MEDIUM,
        delivery_score: float = 0.0,
        responder: str = "",
        business_unit: str = "",
    ) -> NotificationRecord:
        record = NotificationRecord(
            breach_id=breach_id,
            notification_channel=notification_channel,
            notification_deadline=notification_deadline,
            breach_severity=breach_severity,
            delivery_score=delivery_score,
            responder=responder,
            business_unit=business_unit,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "breach_notification_orchestrator.notification_recorded",
            record_id=record.id,
            breach_id=breach_id,
            notification_channel=notification_channel.value,
            breach_severity=breach_severity.value,
        )
        return record

    def get_notification(self, record_id: str) -> NotificationRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_notifications(
        self,
        notification_channel: NotificationChannel | None = None,
        breach_severity: BreachSeverity | None = None,
        business_unit: str | None = None,
        limit: int = 50,
    ) -> list[NotificationRecord]:
        results = list(self._records)
        if notification_channel is not None:
            results = [r for r in results if r.notification_channel == notification_channel]
        if breach_severity is not None:
            results = [r for r in results if r.breach_severity == breach_severity]
        if business_unit is not None:
            results = [r for r in results if r.business_unit == business_unit]
        return results[-limit:]

    def add_analysis(
        self,
        breach_id: str,
        notification_channel: NotificationChannel = NotificationChannel.INTERNAL,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> NotificationAnalysis:
        analysis = NotificationAnalysis(
            breach_id=breach_id,
            notification_channel=notification_channel,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "breach_notification_orchestrator.analysis_added",
            breach_id=breach_id,
            notification_channel=notification_channel.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_channel_distribution(self) -> dict[str, Any]:
        """Group by notification_channel; return count and avg delivery_score."""
        channel_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.notification_channel.value
            channel_data.setdefault(key, []).append(r.delivery_score)
        result: dict[str, Any] = {}
        for channel, scores in channel_data.items():
            result[channel] = {
                "count": len(scores),
                "avg_delivery_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_notification_gaps(self) -> list[dict[str, Any]]:
        """Return records where delivery_score < threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.delivery_score < self._threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "breach_id": r.breach_id,
                        "notification_channel": r.notification_channel.value,
                        "delivery_score": r.delivery_score,
                        "responder": r.responder,
                        "business_unit": r.business_unit,
                    }
                )
        return sorted(results, key=lambda x: x["delivery_score"])

    def rank_by_delivery(self) -> list[dict[str, Any]]:
        """Group by business_unit, avg delivery_score, sort ascending."""
        unit_scores: dict[str, list[float]] = {}
        for r in self._records:
            unit_scores.setdefault(r.business_unit, []).append(r.delivery_score)
        results: list[dict[str, Any]] = []
        for unit, scores in unit_scores.items():
            results.append(
                {
                    "business_unit": unit,
                    "avg_delivery_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_delivery_score"])
        return results

    def detect_notification_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> BreachNotificationReport:
        by_channel: dict[str, int] = {}
        by_deadline: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        for r in self._records:
            by_channel[r.notification_channel.value] = (
                by_channel.get(r.notification_channel.value, 0) + 1
            )
            by_deadline[r.notification_deadline.value] = (
                by_deadline.get(r.notification_deadline.value, 0) + 1
            )
            by_severity[r.breach_severity.value] = by_severity.get(r.breach_severity.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.delivery_score < self._threshold)
        scores = [r.delivery_score for r in self._records]
        avg_delivery_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_notification_gaps()
        top_gaps = [o["breach_id"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} notification(s) below delivery threshold ({self._threshold})")
        if self._records and avg_delivery_score < self._threshold:
            recs.append(
                f"Avg delivery score {avg_delivery_score} below threshold ({self._threshold})"
            )
        if not recs:
            recs.append("Breach notification coverage is healthy")
        return BreachNotificationReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_delivery_score=avg_delivery_score,
            by_channel=by_channel,
            by_deadline=by_deadline,
            by_severity=by_severity,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("breach_notification_orchestrator.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        channel_dist: dict[str, int] = {}
        for r in self._records:
            key = r.notification_channel.value
            channel_dist[key] = channel_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "channel_distribution": channel_dist,
            "unique_responders": len({r.responder for r in self._records}),
            "unique_units": len({r.business_unit for r in self._records}),
        }
