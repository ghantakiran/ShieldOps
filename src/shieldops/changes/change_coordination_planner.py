"""Change Coordination Planner — coordinate changes, assess conflict risk across teams."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class CoordinationStatus(StrEnum):
    ALIGNED = "aligned"
    CONFLICTING = "conflicting"
    OVERLAPPING = "overlapping"
    SEQUENCED = "sequenced"
    INDEPENDENT = "independent"


class ConflictSeverity(StrEnum):
    BLOCKING = "blocking"
    MAJOR = "major"
    MODERATE = "moderate"
    MINOR = "minor"
    NONE = "none"


class ScheduleWindow(StrEnum):
    PEAK_HOURS = "peak_hours"
    OFF_PEAK = "off_peak"
    MAINTENANCE = "maintenance"
    WEEKEND = "weekend"
    EMERGENCY = "emergency"


# --- Models ---


class CoordinationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    change_id: str = ""
    coordination_status: CoordinationStatus = CoordinationStatus.ALIGNED
    conflict_severity: ConflictSeverity = ConflictSeverity.NONE
    schedule_window: ScheduleWindow = ScheduleWindow.OFF_PEAK
    risk_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class CoordinationAssessment(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    change_id: str = ""
    coordination_status: CoordinationStatus = CoordinationStatus.ALIGNED
    assessment_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ChangeCoordinationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_assessments: int = 0
    high_risk_count: int = 0
    avg_risk_score: float = 0.0
    by_status: dict[str, int] = Field(default_factory=dict)
    by_severity: dict[str, int] = Field(default_factory=dict)
    by_window: dict[str, int] = Field(default_factory=dict)
    top_conflicts: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class ChangeCoordinationPlanner:
    """Coordinate changes, assess conflict risk across teams."""

    def __init__(
        self,
        max_records: int = 200000,
        coordination_risk_threshold: float = 60.0,
    ) -> None:
        self._max_records = max_records
        self._coordination_risk_threshold = coordination_risk_threshold
        self._records: list[CoordinationRecord] = []
        self._assessments: list[CoordinationAssessment] = []
        logger.info(
            "change_coordination_planner.initialized",
            max_records=max_records,
            coordination_risk_threshold=coordination_risk_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_coordination(
        self,
        change_id: str,
        coordination_status: CoordinationStatus = CoordinationStatus.ALIGNED,
        conflict_severity: ConflictSeverity = ConflictSeverity.NONE,
        schedule_window: ScheduleWindow = ScheduleWindow.OFF_PEAK,
        risk_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> CoordinationRecord:
        record = CoordinationRecord(
            change_id=change_id,
            coordination_status=coordination_status,
            conflict_severity=conflict_severity,
            schedule_window=schedule_window,
            risk_score=risk_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "change_coordination_planner.coordination_recorded",
            record_id=record.id,
            change_id=change_id,
            coordination_status=coordination_status.value,
            conflict_severity=conflict_severity.value,
        )
        return record

    def get_coordination(self, record_id: str) -> CoordinationRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_coordinations(
        self,
        coordination_status: CoordinationStatus | None = None,
        conflict_severity: ConflictSeverity | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[CoordinationRecord]:
        results = list(self._records)
        if coordination_status is not None:
            results = [r for r in results if r.coordination_status == coordination_status]
        if conflict_severity is not None:
            results = [r for r in results if r.conflict_severity == conflict_severity]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_assessment(
        self,
        change_id: str,
        coordination_status: CoordinationStatus = CoordinationStatus.ALIGNED,
        assessment_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> CoordinationAssessment:
        assessment = CoordinationAssessment(
            change_id=change_id,
            coordination_status=coordination_status,
            assessment_score=assessment_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._assessments.append(assessment)
        if len(self._assessments) > self._max_records:
            self._assessments = self._assessments[-self._max_records :]
        logger.info(
            "change_coordination_planner.assessment_added",
            change_id=change_id,
            coordination_status=coordination_status.value,
            assessment_score=assessment_score,
        )
        return assessment

    # -- domain operations --------------------------------------------------

    def analyze_coordination_distribution(self) -> dict[str, Any]:
        """Group by coordination_status; return count and avg risk_score."""
        status_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.coordination_status.value
            status_data.setdefault(key, []).append(r.risk_score)
        result: dict[str, Any] = {}
        for status, scores in status_data.items():
            result[status] = {
                "count": len(scores),
                "avg_risk_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_high_risk_coordinations(self) -> list[dict[str, Any]]:
        """Return records where risk_score > coordination_risk_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.risk_score > self._coordination_risk_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "change_id": r.change_id,
                        "coordination_status": r.coordination_status.value,
                        "risk_score": r.risk_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["risk_score"], reverse=True)

    def rank_by_risk(self) -> list[dict[str, Any]]:
        """Group by service, avg risk_score, sort descending (highest risk first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.risk_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_risk_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_risk_score"], reverse=True)
        return results

    def detect_coordination_trends(self) -> dict[str, Any]:
        """Split-half comparison on assessment_score; delta threshold 5.0."""
        if len(self._assessments) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [a.assessment_score for a in self._assessments]
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

    def generate_report(self) -> ChangeCoordinationReport:
        by_status: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        by_window: dict[str, int] = {}
        for r in self._records:
            by_status[r.coordination_status.value] = (
                by_status.get(r.coordination_status.value, 0) + 1
            )
            by_severity[r.conflict_severity.value] = (
                by_severity.get(r.conflict_severity.value, 0) + 1
            )
            by_window[r.schedule_window.value] = by_window.get(r.schedule_window.value, 0) + 1
        high_risk_count = sum(
            1 for r in self._records if r.risk_score > self._coordination_risk_threshold
        )
        scores = [r.risk_score for r in self._records]
        avg_risk_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        high_list = self.identify_high_risk_coordinations()
        top_conflicts = [o["change_id"] for o in high_list[:5]]
        recs: list[str] = []
        if self._records and high_risk_count > 0:
            recs.append(
                f"{high_risk_count} coordination(s) exceed risk threshold "
                f"({self._coordination_risk_threshold})"
            )
        if self._records and avg_risk_score > self._coordination_risk_threshold:
            recs.append(
                f"Avg risk score {avg_risk_score} above threshold "
                f"({self._coordination_risk_threshold})"
            )
        if not recs:
            recs.append("Change coordination risk levels are healthy")
        return ChangeCoordinationReport(
            total_records=len(self._records),
            total_assessments=len(self._assessments),
            high_risk_count=high_risk_count,
            avg_risk_score=avg_risk_score,
            by_status=by_status,
            by_severity=by_severity,
            by_window=by_window,
            top_conflicts=top_conflicts,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._assessments.clear()
        logger.info("change_coordination_planner.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        status_dist: dict[str, int] = {}
        for r in self._records:
            key = r.coordination_status.value
            status_dist[key] = status_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_assessments": len(self._assessments),
            "coordination_risk_threshold": self._coordination_risk_threshold,
            "status_distribution": status_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
