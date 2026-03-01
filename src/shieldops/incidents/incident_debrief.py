"""Incident Debrief Tracker — track debrief quality, action items, and participation."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class DebriefStatus(StrEnum):
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    OVERDUE = "overdue"


class DebriefQuality(StrEnum):
    EXCELLENT = "excellent"
    GOOD = "good"
    ADEQUATE = "adequate"
    POOR = "poor"
    MISSING = "missing"


class ActionItemStatus(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


# --- Models ---


class DebriefRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str = ""
    debrief_status: DebriefStatus = DebriefStatus.SCHEDULED
    debrief_quality: DebriefQuality = DebriefQuality.ADEQUATE
    action_item_status: ActionItemStatus = ActionItemStatus.OPEN
    quality_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class DebriefMetric(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str = ""
    debrief_status: DebriefStatus = DebriefStatus.SCHEDULED
    metric_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class IncidentDebriefReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_metrics: int = 0
    low_quality_count: int = 0
    avg_quality_score: float = 0.0
    by_status: dict[str, int] = Field(default_factory=dict)
    by_quality: dict[str, int] = Field(default_factory=dict)
    by_action_status: dict[str, int] = Field(default_factory=dict)
    top_low_quality: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class IncidentDebriefTracker:
    """Track post-incident debrief quality, action items, and participation."""

    def __init__(
        self,
        max_records: int = 200000,
        min_debrief_quality_pct: float = 70.0,
    ) -> None:
        self._max_records = max_records
        self._min_debrief_quality_pct = min_debrief_quality_pct
        self._records: list[DebriefRecord] = []
        self._metrics: list[DebriefMetric] = []
        logger.info(
            "incident_debrief.initialized",
            max_records=max_records,
            min_debrief_quality_pct=min_debrief_quality_pct,
        )

    # -- record / get / list ------------------------------------------------

    def record_debrief(
        self,
        incident_id: str,
        debrief_status: DebriefStatus = DebriefStatus.SCHEDULED,
        debrief_quality: DebriefQuality = DebriefQuality.ADEQUATE,
        action_item_status: ActionItemStatus = ActionItemStatus.OPEN,
        quality_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> DebriefRecord:
        record = DebriefRecord(
            incident_id=incident_id,
            debrief_status=debrief_status,
            debrief_quality=debrief_quality,
            action_item_status=action_item_status,
            quality_score=quality_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "incident_debrief.debrief_recorded",
            record_id=record.id,
            incident_id=incident_id,
            debrief_status=debrief_status.value,
            debrief_quality=debrief_quality.value,
        )
        return record

    def get_debrief(self, record_id: str) -> DebriefRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_debriefs(
        self,
        status: DebriefStatus | None = None,
        quality: DebriefQuality | None = None,
        service: str | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[DebriefRecord]:
        results = list(self._records)
        if status is not None:
            results = [r for r in results if r.debrief_status == status]
        if quality is not None:
            results = [r for r in results if r.debrief_quality == quality]
        if service is not None:
            results = [r for r in results if r.service == service]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_metric(
        self,
        incident_id: str,
        debrief_status: DebriefStatus = DebriefStatus.SCHEDULED,
        metric_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> DebriefMetric:
        metric = DebriefMetric(
            incident_id=incident_id,
            debrief_status=debrief_status,
            metric_score=metric_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._metrics.append(metric)
        if len(self._metrics) > self._max_records:
            self._metrics = self._metrics[-self._max_records :]
        logger.info(
            "incident_debrief.metric_added",
            incident_id=incident_id,
            debrief_status=debrief_status.value,
            metric_score=metric_score,
        )
        return metric

    # -- domain operations --------------------------------------------------

    def analyze_debrief_quality(self) -> dict[str, Any]:
        """Group by debrief_quality; return count and avg quality_score per quality."""
        quality_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.debrief_quality.value
            quality_data.setdefault(key, []).append(r.quality_score)
        result: dict[str, Any] = {}
        for quality, scores in quality_data.items():
            result[quality] = {
                "count": len(scores),
                "avg_quality_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_low_quality_debriefs(self) -> list[dict[str, Any]]:
        """Return records where debrief_quality is POOR or MISSING."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.debrief_quality in (DebriefQuality.POOR, DebriefQuality.MISSING):
                results.append(
                    {
                        "record_id": r.id,
                        "incident_id": r.incident_id,
                        "debrief_quality": r.debrief_quality.value,
                        "quality_score": r.quality_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_quality_score(self) -> list[dict[str, Any]]:
        """Group by service, avg quality_score, sort ascending."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.quality_score)
        results: list[dict[str, Any]] = []
        for service, scores in svc_scores.items():
            results.append(
                {
                    "service": service,
                    "avg_quality_score": round(sum(scores) / len(scores), 2),
                    "debrief_count": len(scores),
                }
            )
        results.sort(key=lambda x: x["avg_quality_score"])
        return results

    def detect_quality_trends(self) -> dict[str, Any]:
        """Split-half comparison on metric_score; delta threshold 5.0."""
        if len(self._metrics) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        scores = [m.metric_score for m in self._metrics]
        mid = len(scores) // 2
        first_half = scores[:mid]
        second_half = scores[mid:]
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

    def generate_report(self) -> IncidentDebriefReport:
        by_status: dict[str, int] = {}
        by_quality: dict[str, int] = {}
        by_action_status: dict[str, int] = {}
        for r in self._records:
            by_status[r.debrief_status.value] = by_status.get(r.debrief_status.value, 0) + 1
            by_quality[r.debrief_quality.value] = by_quality.get(r.debrief_quality.value, 0) + 1
            by_action_status[r.action_item_status.value] = (
                by_action_status.get(r.action_item_status.value, 0) + 1
            )
        low_quality_count = sum(
            1
            for r in self._records
            if r.debrief_quality in (DebriefQuality.POOR, DebriefQuality.MISSING)
        )
        avg_quality = (
            round(sum(r.quality_score for r in self._records) / len(self._records), 2)
            if self._records
            else 0.0
        )
        rankings = self.rank_by_quality_score()
        top_low_quality = [rk["service"] for rk in rankings[:5]]
        recs: list[str] = []
        if low_quality_count > 0:
            recs.append(
                f"{low_quality_count} low-quality debrief(s) detected — review debrief process"
            )
        quality_pct = (
            round(low_quality_count / len(self._records) * 100, 2) if self._records else 0.0
        )
        if quality_pct > (100.0 - self._min_debrief_quality_pct):
            recs.append(
                f"Low-quality debrief rate {quality_pct}% exceeds "
                f"threshold ({100.0 - self._min_debrief_quality_pct}%)"
            )
        if not recs:
            recs.append("Debrief quality levels are healthy")
        return IncidentDebriefReport(
            total_records=len(self._records),
            total_metrics=len(self._metrics),
            low_quality_count=low_quality_count,
            avg_quality_score=avg_quality,
            by_status=by_status,
            by_quality=by_quality,
            by_action_status=by_action_status,
            top_low_quality=top_low_quality,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._metrics.clear()
        logger.info("incident_debrief.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        status_dist: dict[str, int] = {}
        for r in self._records:
            key = r.debrief_status.value
            status_dist[key] = status_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_metrics": len(self._metrics),
            "min_debrief_quality_pct": self._min_debrief_quality_pct,
            "status_distribution": status_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
