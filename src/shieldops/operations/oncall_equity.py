"""Team On-Call Equity Analyzer — measure on-call equity."""

from __future__ import annotations

import time
from enum import StrEnum
from typing import Any
from uuid import uuid4

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ShiftType(StrEnum):
    WEEKDAY_DAY = "weekday_day"
    WEEKDAY_NIGHT = "weekday_night"
    WEEKEND_DAY = "weekend_day"
    WEEKEND_NIGHT = "weekend_night"
    HOLIDAY = "holiday"


class LoadCategory(StrEnum):
    PAGES = "pages"
    INCIDENTS = "incidents"
    ESCALATIONS = "escalations"
    AFTER_HOURS = "after_hours"
    TOIL = "toil"


class EquityStatus(StrEnum):
    EQUITABLE = "equitable"
    SLIGHTLY_UNEVEN = "slightly_uneven"
    MODERATELY_UNEVEN = "moderately_uneven"
    HIGHLY_UNEVEN = "highly_uneven"
    CRITICAL = "critical"


# --- Models ---


class OnCallEquityRecord(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    team_member: str = ""
    team: str = ""
    shift_type: ShiftType = ShiftType.WEEKDAY_DAY
    load_category: LoadCategory = LoadCategory.PAGES
    load_count: int = 0
    load_hours: float = 0.0
    equity_score: float = 0.0
    period: str = ""
    created_at: float = Field(default_factory=time.time)


class EquityAdjustment(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    team_member: str = ""
    adjustment_type: str = ""
    reason: str = ""
    shift_change: str = ""
    created_at: float = Field(default_factory=time.time)


class OnCallEquityReport(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    total_records: int = 0
    total_adjustments: int = 0
    avg_equity_score: float = 0.0
    by_shift_type: dict[str, int] = Field(default_factory=dict)
    by_load_category: dict[str, int] = Field(default_factory=dict)
    by_equity_status: dict[str, int] = Field(default_factory=dict)
    overloaded_members: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class TeamOnCallEquityAnalyzer:
    """Measure and track on-call equity across teams."""

    def __init__(
        self,
        max_records: int = 200000,
        max_inequity_pct: float = 25.0,
    ) -> None:
        self._max_records = max_records
        self._max_inequity_pct = max_inequity_pct
        self._records: list[OnCallEquityRecord] = []
        self._adjustments: list[EquityAdjustment] = []
        logger.info(
            "oncall_equity.initialized",
            max_records=max_records,
            max_inequity_pct=max_inequity_pct,
        )

    # -- record / get / list -----------------------------------------

    def record_equity(
        self,
        team_member: str,
        team: str,
        shift_type: ShiftType = ShiftType.WEEKDAY_DAY,
        load_category: LoadCategory = (LoadCategory.PAGES),
        load_count: int = 0,
        load_hours: float = 0.0,
        equity_score: float = 0.0,
        period: str = "",
    ) -> OnCallEquityRecord:
        record = OnCallEquityRecord(
            team_member=team_member,
            team=team,
            shift_type=shift_type,
            load_category=load_category,
            load_count=load_count,
            load_hours=load_hours,
            equity_score=equity_score,
            period=period,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "oncall_equity.recorded",
            record_id=record.id,
            team_member=team_member,
            team=team,
            shift_type=shift_type.value,
        )
        return record

    def get_equity(self, record_id: str) -> OnCallEquityRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_equities(
        self,
        shift_type: ShiftType | None = None,
        load_category: LoadCategory | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[OnCallEquityRecord]:
        results = list(self._records)
        if shift_type is not None:
            results = [r for r in results if r.shift_type == shift_type]
        if load_category is not None:
            results = [r for r in results if r.load_category == load_category]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_adjustment(
        self,
        team_member: str,
        adjustment_type: str,
        reason: str,
        shift_change: str,
    ) -> EquityAdjustment:
        adjustment = EquityAdjustment(
            team_member=team_member,
            adjustment_type=adjustment_type,
            reason=reason,
            shift_change=shift_change,
        )
        self._adjustments.append(adjustment)
        if len(self._adjustments) > self._max_records:
            self._adjustments = self._adjustments[-self._max_records :]
        logger.info(
            "oncall_equity.adjustment_added",
            adjustment_id=adjustment.id,
            team_member=team_member,
            adjustment_type=adjustment_type,
        )
        return adjustment

    # -- domain operations -------------------------------------------

    def analyze_equity_by_team(
        self,
    ) -> dict[str, Any]:
        """Analyze equity grouped by team."""
        team_data: dict[str, dict[str, Any]] = {}
        for r in self._records:
            t = r.team or "unknown"
            if t not in team_data:
                team_data[t] = {
                    "total": 0,
                    "scores": [],
                }
            team_data[t]["total"] += 1
            team_data[t]["scores"].append(r.equity_score)
        breakdown: list[dict[str, Any]] = []
        for t, data in team_data.items():
            scores = data["scores"]
            avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
            breakdown.append(
                {
                    "team": t,
                    "total_records": data["total"],
                    "avg_equity_score": avg_score,
                }
            )
        breakdown.sort(
            key=lambda x: x["avg_equity_score"],
        )
        return {
            "total_teams": len(team_data),
            "breakdown": breakdown,
        }

    def identify_overloaded_members(
        self,
    ) -> list[dict[str, Any]]:
        """Find members whose equity_score deviates
        beyond max_inequity threshold."""
        if not self._records:
            return []
        all_scores = [r.equity_score for r in self._records]
        avg_score = sum(all_scores) / len(all_scores)
        results: list[dict[str, Any]] = []
        for r in self._records:
            deviation = abs(r.equity_score - avg_score)
            if deviation > self._max_inequity_pct:
                results.append(
                    {
                        "team_member": r.team_member,
                        "team": r.team,
                        "equity_score": (r.equity_score),
                        "deviation": round(deviation, 2),
                    }
                )
        results.sort(
            key=lambda x: x["deviation"],
            reverse=True,
        )
        return results

    def rank_by_equity_score(
        self,
    ) -> list[dict[str, Any]]:
        """Rank members by average equity score."""
        member_vals: dict[str, list[float]] = {}
        for r in self._records:
            member_vals.setdefault(r.team_member, []).append(r.equity_score)
        results: list[dict[str, Any]] = []
        for member, vals in member_vals.items():
            avg = round(sum(vals) / len(vals), 2)
            results.append(
                {
                    "team_member": member,
                    "avg_equity_score": avg,
                    "record_count": len(vals),
                }
            )
        results.sort(
            key=lambda x: x["avg_equity_score"],
        )
        return results

    def detect_equity_trends(
        self,
    ) -> dict[str, Any]:
        """Detect equity trends via split-half."""
        if len(self._records) < 4:
            return {
                "trend": "insufficient_data",
                "sample_count": len(self._records),
            }
        mid = len(self._records) // 2
        first_half = self._records[:mid]
        second_half = self._records[mid:]

        def _avg_score(
            records: list[OnCallEquityRecord],
        ) -> float:
            if not records:
                return 0.0
            return round(
                sum(r.equity_score for r in records) / len(records),
                2,
            )

        first_score = _avg_score(first_half)
        second_score = _avg_score(second_half)
        delta = round(second_score - first_score, 2)
        if delta > 5.0:
            trend = "improving"
        elif delta < -5.0:
            trend = "worsening"
        else:
            trend = "stable"
        return {
            "trend": trend,
            "first_half_avg_score": first_score,
            "second_half_avg_score": second_score,
            "delta": delta,
            "total_records": len(self._records),
        }

    # -- report / stats ----------------------------------------------

    def generate_report(
        self,
    ) -> OnCallEquityReport:
        by_shift: dict[str, int] = {}
        by_load: dict[str, int] = {}
        for r in self._records:
            by_shift[r.shift_type.value] = by_shift.get(r.shift_type.value, 0) + 1
            by_load[r.load_category.value] = by_load.get(r.load_category.value, 0) + 1
        avg_score = (
            round(
                sum(r.equity_score for r in self._records) / len(self._records),
                2,
            )
            if self._records
            else 0.0
        )
        overloaded = self.identify_overloaded_members()
        overloaded_names = list({o["team_member"] for o in overloaded})
        # Classify equity status distribution
        by_equity_status: dict[str, int] = {}
        for r in self._records:
            dev = abs(r.equity_score - avg_score)
            if dev <= 5:
                status = "equitable"
            elif dev <= 15:
                status = "slightly_uneven"
            elif dev <= 25:
                status = "moderately_uneven"
            elif dev <= 40:
                status = "highly_uneven"
            else:
                status = "critical"
            by_equity_status[status] = by_equity_status.get(status, 0) + 1
        recs: list[str] = []
        if overloaded_names:
            recs.append(f"{len(overloaded_names)} member(s) with inequitable on-call load")
        trends = self.detect_equity_trends()
        if trends.get("trend") == "worsening":
            recs.append("On-call equity trend is worsening")
        if not recs:
            recs.append("On-call load is equitably distributed")
        return OnCallEquityReport(
            total_records=len(self._records),
            total_adjustments=len(self._adjustments),
            avg_equity_score=avg_score,
            by_shift_type=by_shift,
            by_load_category=by_load,
            by_equity_status=by_equity_status,
            overloaded_members=overloaded_names,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._adjustments.clear()
        logger.info("oncall_equity.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        shift_dist: dict[str, int] = {}
        for r in self._records:
            key = r.shift_type.value
            shift_dist[key] = shift_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_adjustments": len(self._adjustments),
            "max_inequity_pct": (self._max_inequity_pct),
            "shift_type_distribution": shift_dist,
            "unique_members": len({r.team_member for r in self._records}),
        }
