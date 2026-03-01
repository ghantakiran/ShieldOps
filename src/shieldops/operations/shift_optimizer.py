"""Shift Schedule Optimizer — track shifts, coverage gaps, and schedule issues."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ShiftType(StrEnum):
    PRIMARY = "primary"
    SECONDARY = "secondary"
    BACKUP = "backup"
    FOLLOW_THE_SUN = "follow_the_sun"
    SPLIT = "split"


class CoverageStatus(StrEnum):
    FULL = "full"
    PARTIAL = "partial"
    GAP = "gap"
    OVERLAP = "overlap"
    UNDERSTAFFED = "understaffed"


class ScheduleIssue(StrEnum):
    FATIGUE_RISK = "fatigue_risk"
    TIMEZONE_MISMATCH = "timezone_mismatch"
    SKILL_GAP = "skill_gap"
    UNDERSTAFFED = "understaffed"
    OVERLOADED = "overloaded"


# --- Models ---


class ShiftRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    schedule_id: str = ""
    shift_type: ShiftType = ShiftType.PRIMARY
    coverage_status: CoverageStatus = CoverageStatus.FULL
    schedule_issue: ScheduleIssue = ScheduleIssue.FATIGUE_RISK
    coverage_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class CoverageGap(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    schedule_id: str = ""
    shift_type: ShiftType = ShiftType.PRIMARY
    gap_duration_hours: float = 0.0
    severity: int = 0
    auto_fill: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ShiftScheduleReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_gaps: int = 0
    coverage_gap_count: int = 0
    avg_coverage_score: float = 0.0
    by_shift_type: dict[str, int] = Field(default_factory=dict)
    by_coverage_status: dict[str, int] = Field(default_factory=dict)
    by_schedule_issue: dict[str, int] = Field(default_factory=dict)
    top_teams: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class ShiftScheduleOptimizer:
    """Track shift schedules, identify coverage gaps, and detect issues."""

    def __init__(
        self,
        max_records: int = 200000,
        max_coverage_gap_pct: float = 10.0,
    ) -> None:
        self._max_records = max_records
        self._max_coverage_gap_pct = max_coverage_gap_pct
        self._records: list[ShiftRecord] = []
        self._gaps: list[CoverageGap] = []
        logger.info(
            "shift_optimizer.initialized",
            max_records=max_records,
            max_coverage_gap_pct=max_coverage_gap_pct,
        )

    # -- record / get / list ------------------------------------------------

    def record_shift(
        self,
        schedule_id: str,
        shift_type: ShiftType = ShiftType.PRIMARY,
        coverage_status: CoverageStatus = CoverageStatus.FULL,
        schedule_issue: ScheduleIssue = ScheduleIssue.FATIGUE_RISK,
        coverage_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> ShiftRecord:
        record = ShiftRecord(
            schedule_id=schedule_id,
            shift_type=shift_type,
            coverage_status=coverage_status,
            schedule_issue=schedule_issue,
            coverage_score=coverage_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "shift_optimizer.shift_recorded",
            record_id=record.id,
            schedule_id=schedule_id,
            shift_type=shift_type.value,
            coverage_status=coverage_status.value,
        )
        return record

    def get_shift(self, record_id: str) -> ShiftRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_shifts(
        self,
        shift_type: ShiftType | None = None,
        coverage_status: CoverageStatus | None = None,
        service: str | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[ShiftRecord]:
        results = list(self._records)
        if shift_type is not None:
            results = [r for r in results if r.shift_type == shift_type]
        if coverage_status is not None:
            results = [r for r in results if r.coverage_status == coverage_status]
        if service is not None:
            results = [r for r in results if r.service == service]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_gap(
        self,
        schedule_id: str,
        shift_type: ShiftType = ShiftType.PRIMARY,
        gap_duration_hours: float = 0.0,
        severity: int = 0,
        auto_fill: bool = False,
        description: str = "",
    ) -> CoverageGap:
        gap = CoverageGap(
            schedule_id=schedule_id,
            shift_type=shift_type,
            gap_duration_hours=gap_duration_hours,
            severity=severity,
            auto_fill=auto_fill,
            description=description,
        )
        self._gaps.append(gap)
        if len(self._gaps) > self._max_records:
            self._gaps = self._gaps[-self._max_records :]
        logger.info(
            "shift_optimizer.gap_added",
            schedule_id=schedule_id,
            shift_type=shift_type.value,
            gap_duration_hours=gap_duration_hours,
        )
        return gap

    # -- domain operations --------------------------------------------------

    def analyze_coverage_patterns(self) -> dict[str, Any]:
        """Group by shift_type; return count and avg coverage score per type."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.shift_type.value
            type_data.setdefault(key, []).append(r.coverage_score)
        result: dict[str, Any] = {}
        for shift_type, scores in type_data.items():
            result[shift_type] = {
                "count": len(scores),
                "avg_coverage_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_coverage_gaps(self) -> list[dict[str, Any]]:
        """Return records where coverage_status is GAP or UNDERSTAFFED."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.coverage_status in (CoverageStatus.GAP, CoverageStatus.UNDERSTAFFED):
                results.append(
                    {
                        "record_id": r.id,
                        "schedule_id": r.schedule_id,
                        "shift_type": r.shift_type.value,
                        "coverage_status": r.coverage_status.value,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_coverage_score(self) -> list[dict[str, Any]]:
        """Group by team, total records, sort descending by avg coverage score."""
        team_data: dict[str, list[float]] = {}
        for r in self._records:
            team_data.setdefault(r.team, []).append(r.coverage_score)
        results: list[dict[str, Any]] = []
        for team, scores in team_data.items():
            results.append(
                {
                    "team": team,
                    "shift_count": len(scores),
                    "avg_coverage_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_coverage_score"], reverse=True)
        return results

    def detect_schedule_issues(self) -> dict[str, Any]:
        """Split-half on severity; delta threshold 5.0."""
        if len(self._gaps) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        values = [g.severity for g in self._gaps]
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

    def generate_report(self) -> ShiftScheduleReport:
        by_shift_type: dict[str, int] = {}
        by_coverage_status: dict[str, int] = {}
        by_schedule_issue: dict[str, int] = {}
        for r in self._records:
            by_shift_type[r.shift_type.value] = by_shift_type.get(r.shift_type.value, 0) + 1
            by_coverage_status[r.coverage_status.value] = (
                by_coverage_status.get(r.coverage_status.value, 0) + 1
            )
            by_schedule_issue[r.schedule_issue.value] = (
                by_schedule_issue.get(r.schedule_issue.value, 0) + 1
            )
        gap_count = sum(
            1
            for r in self._records
            if r.coverage_status in (CoverageStatus.GAP, CoverageStatus.UNDERSTAFFED)
        )
        scores = [r.coverage_score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        rankings = self.rank_by_coverage_score()
        top_teams = [rk["team"] for rk in rankings[:5]]
        recs: list[str] = []
        gap_rate = round(gap_count / len(self._records) * 100, 2) if self._records else 0.0
        if gap_rate > self._max_coverage_gap_pct:
            recs.append(
                f"Coverage gap rate {gap_rate}% exceeds threshold ({self._max_coverage_gap_pct}%)"
            )
        if gap_count > 0:
            recs.append(f"{gap_count} coverage gap(s) detected — review shift scheduling")
        if not recs:
            recs.append("Shift coverage is acceptable")
        return ShiftScheduleReport(
            total_records=len(self._records),
            total_gaps=len(self._gaps),
            coverage_gap_count=gap_count,
            avg_coverage_score=avg_score,
            by_shift_type=by_shift_type,
            by_coverage_status=by_coverage_status,
            by_schedule_issue=by_schedule_issue,
            top_teams=top_teams,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._gaps.clear()
        logger.info("shift_optimizer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.shift_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_gaps": len(self._gaps),
            "max_coverage_gap_pct": self._max_coverage_gap_pct,
            "shift_type_distribution": type_dist,
            "unique_services": len({r.service for r in self._records}),
            "unique_teams": len({r.team for r in self._records}),
        }
