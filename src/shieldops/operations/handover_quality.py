"""Handover Quality Tracker — track handover quality, checklists, and trends."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class HandoverType(StrEnum):
    SHIFT_CHANGE = "shift_change"
    ESCALATION = "escalation"
    CROSS_TEAM = "cross_team"
    INCIDENT_TRANSFER = "incident_transfer"
    MAINTENANCE_WINDOW = "maintenance_window"


class HandoverQuality(StrEnum):
    EXCELLENT = "excellent"
    GOOD = "good"
    ADEQUATE = "adequate"
    POOR = "poor"
    FAILED = "failed"


class HandoverIssue(StrEnum):
    MISSING_CONTEXT = "missing_context"
    DELAYED_TRANSFER = "delayed_transfer"
    WRONG_RECIPIENT = "wrong_recipient"
    INCOMPLETE_STATUS = "incomplete_status"
    NO_RUNBOOK = "no_runbook"


# --- Models ---


class HandoverRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    handover_id: str = ""
    handover_type: HandoverType = HandoverType.SHIFT_CHANGE
    handover_quality: HandoverQuality = HandoverQuality.ADEQUATE
    handover_issue: HandoverIssue = HandoverIssue.MISSING_CONTEXT
    quality_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class HandoverChecklist(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    handover_id: str = ""
    handover_type: HandoverType = HandoverType.SHIFT_CHANGE
    value: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class HandoverQualityReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_checklists: int = 0
    poor_handovers: int = 0
    avg_quality_score: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_quality: dict[str, int] = Field(default_factory=dict)
    by_issue: dict[str, int] = Field(default_factory=dict)
    top_poor: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class HandoverQualityTracker:
    """Track handover quality, identify patterns, and detect issues."""

    def __init__(
        self,
        max_records: int = 200000,
        min_handover_quality_pct: float = 80.0,
    ) -> None:
        self._max_records = max_records
        self._min_handover_quality_pct = min_handover_quality_pct
        self._records: list[HandoverRecord] = []
        self._checklists: list[HandoverChecklist] = []
        logger.info(
            "handover_quality.initialized",
            max_records=max_records,
            min_handover_quality_pct=min_handover_quality_pct,
        )

    # -- record / get / list ------------------------------------------------

    def record_handover(
        self,
        handover_id: str,
        handover_type: HandoverType = HandoverType.SHIFT_CHANGE,
        handover_quality: HandoverQuality = HandoverQuality.ADEQUATE,
        handover_issue: HandoverIssue = HandoverIssue.MISSING_CONTEXT,
        quality_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> HandoverRecord:
        record = HandoverRecord(
            handover_id=handover_id,
            handover_type=handover_type,
            handover_quality=handover_quality,
            handover_issue=handover_issue,
            quality_score=quality_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "handover_quality.handover_recorded",
            record_id=record.id,
            handover_id=handover_id,
            handover_type=handover_type.value,
            handover_quality=handover_quality.value,
        )
        return record

    def get_handover(self, record_id: str) -> HandoverRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_handovers(
        self,
        htype: HandoverType | None = None,
        quality: HandoverQuality | None = None,
        service: str | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[HandoverRecord]:
        results = list(self._records)
        if htype is not None:
            results = [r for r in results if r.handover_type == htype]
        if quality is not None:
            results = [r for r in results if r.handover_quality == quality]
        if service is not None:
            results = [r for r in results if r.service == service]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_checklist(
        self,
        handover_id: str,
        handover_type: HandoverType = HandoverType.SHIFT_CHANGE,
        value: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> HandoverChecklist:
        checklist = HandoverChecklist(
            handover_id=handover_id,
            handover_type=handover_type,
            value=value,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._checklists.append(checklist)
        if len(self._checklists) > self._max_records:
            self._checklists = self._checklists[-self._max_records :]
        logger.info(
            "handover_quality.checklist_added",
            handover_id=handover_id,
            handover_type=handover_type.value,
            value=value,
        )
        return checklist

    # -- domain operations --------------------------------------------------

    def analyze_handover_quality(self) -> dict[str, Any]:
        """Group by type; return count and avg quality score per type."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.handover_type.value
            type_data.setdefault(key, []).append(r.quality_score)
        result: dict[str, Any] = {}
        for htype, scores in type_data.items():
            result[htype] = {
                "count": len(scores),
                "avg_quality_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_poor_handovers(self) -> list[dict[str, Any]]:
        """Return records where quality == POOR or FAILED."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.handover_quality in (
                HandoverQuality.POOR,
                HandoverQuality.FAILED,
            ):
                results.append(
                    {
                        "record_id": r.id,
                        "handover_id": r.handover_id,
                        "handover_type": r.handover_type.value,
                        "handover_quality": r.handover_quality.value,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_quality_score(self) -> list[dict[str, Any]]:
        """Group by service, total records, sort descending by avg score."""
        service_data: dict[str, list[float]] = {}
        for r in self._records:
            service_data.setdefault(r.service, []).append(r.quality_score)
        results: list[dict[str, Any]] = []
        for service, scores in service_data.items():
            results.append(
                {
                    "service": service,
                    "record_count": len(scores),
                    "avg_quality_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_quality_score"], reverse=True)
        return results

    def detect_handover_issues(self) -> dict[str, Any]:
        """Split-half on value; delta threshold 5.0."""
        if len(self._checklists) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        values = [c.value for c in self._checklists]
        mid = len(values) // 2
        first_half = values[:mid]
        second_half = values[mid:]
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

    def generate_report(self) -> HandoverQualityReport:
        by_type: dict[str, int] = {}
        by_quality: dict[str, int] = {}
        by_issue: dict[str, int] = {}
        for r in self._records:
            by_type[r.handover_type.value] = by_type.get(r.handover_type.value, 0) + 1
            by_quality[r.handover_quality.value] = by_quality.get(r.handover_quality.value, 0) + 1
            by_issue[r.handover_issue.value] = by_issue.get(r.handover_issue.value, 0) + 1
        poor_count = sum(
            1
            for r in self._records
            if r.handover_quality in (HandoverQuality.POOR, HandoverQuality.FAILED)
        )
        scores = [r.quality_score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        rankings = self.rank_by_quality_score()
        top_poor = [rk["service"] for rk in rankings[:5]]
        recs: list[str] = []
        below_threshold = sum(
            1 for r in self._records if r.quality_score < self._min_handover_quality_pct
        )
        below_rate = round(below_threshold / len(self._records) * 100, 2) if self._records else 0.0
        if below_rate > 20.0:
            recs.append(
                f"Low quality rate {below_rate}% exceeds threshold"
                f" ({self._min_handover_quality_pct})"
            )
        if poor_count > 0:
            recs.append(f"{poor_count} poor handover(s) detected — review quality")
        if not recs:
            recs.append("Handover quality levels are acceptable")
        return HandoverQualityReport(
            total_records=len(self._records),
            total_checklists=len(self._checklists),
            poor_handovers=poor_count,
            avg_quality_score=avg_score,
            by_type=by_type,
            by_quality=by_quality,
            by_issue=by_issue,
            top_poor=top_poor,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._checklists.clear()
        logger.info("handover_quality.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.handover_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_checklists": len(self._checklists),
            "min_handover_quality_pct": self._min_handover_quality_pct,
            "type_distribution": type_dist,
            "unique_services": len({r.service for r in self._records}),
            "unique_handovers": len({r.handover_id for r in self._records}),
        }
