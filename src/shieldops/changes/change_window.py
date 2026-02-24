"""Change Window Optimizer — optimal deployment window analysis."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class WindowType(StrEnum):
    STANDARD = "standard"
    EXPEDITED = "expedited"
    EMERGENCY = "emergency"
    MAINTENANCE = "maintenance"
    BLACKOUT = "blackout"


class WindowRisk(StrEnum):
    VERY_LOW = "very_low"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    VERY_HIGH = "very_high"


class DayOfWeek(StrEnum):
    MONDAY = "monday"
    TUESDAY = "tuesday"
    WEDNESDAY = "wednesday"
    THURSDAY = "thursday"
    FRIDAY = "friday"


# --- Models ---


class ChangeWindowRecord(BaseModel):
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
    )
    service_name: str = ""
    window_type: WindowType = WindowType.STANDARD
    day_of_week: DayOfWeek = DayOfWeek.TUESDAY
    hour: int = 10
    is_success: bool = True
    risk_level: WindowRisk = WindowRisk.LOW
    duration_minutes: int = 30
    created_at: float = Field(default_factory=time.time)


class WindowScore(BaseModel):
    day_of_week: DayOfWeek = DayOfWeek.TUESDAY
    hour: int = 10
    window_type: WindowType = WindowType.STANDARD
    success_rate: float = 0.0
    total_changes: int = 0
    risk_level: WindowRisk = WindowRisk.LOW
    score: float = 0.0
    created_at: float = Field(default_factory=time.time)


class WindowReport(BaseModel):
    total_changes: int = 0
    total_windows_analyzed: int = 0
    best_window: dict[str, Any] = Field(
        default_factory=dict,
    )
    worst_window: dict[str, Any] = Field(
        default_factory=dict,
    )
    by_type: dict[str, int] = Field(
        default_factory=dict,
    )
    by_risk: dict[str, int] = Field(
        default_factory=dict,
    )
    recommendations: list[str] = Field(
        default_factory=list,
    )
    generated_at: float = Field(default_factory=time.time)


# --- Optimizer ---


class ChangeWindowOptimizer:
    """Analyze change success rates to find optimal windows."""

    def __init__(
        self,
        max_records: int = 200000,
        min_success_rate: float = 90.0,
    ) -> None:
        self._max_records = max_records
        self._min_success_rate = min_success_rate
        self._items: list[ChangeWindowRecord] = []
        self._scores: dict[str, WindowScore] = {}
        logger.info(
            "change_window.initialized",
            max_records=max_records,
            min_success_rate=min_success_rate,
        )

    # -- record --

    def record_change(
        self,
        service_name: str = "",
        window_type: WindowType = WindowType.STANDARD,
        day_of_week: DayOfWeek = DayOfWeek.TUESDAY,
        hour: int = 10,
        is_success: bool = True,
        risk_level: WindowRisk = WindowRisk.LOW,
        duration_minutes: int = 30,
        **kw: Any,
    ) -> ChangeWindowRecord:
        """Record a change execution."""
        record = ChangeWindowRecord(
            service_name=service_name,
            window_type=window_type,
            day_of_week=day_of_week,
            hour=hour,
            is_success=is_success,
            risk_level=risk_level,
            duration_minutes=duration_minutes,
            **kw,
        )
        self._items.append(record)
        if len(self._items) > self._max_records:
            self._items = self._items[-self._max_records :]
        logger.info(
            "change_window.recorded",
            record_id=record.id,
            service=service_name,
            day=day_of_week,
            hour=hour,
        )
        return record

    # -- get / list --

    def get_record(
        self,
        record_id: str,
    ) -> ChangeWindowRecord | None:
        """Get a single record by ID."""
        for item in self._items:
            if item.id == record_id:
                return item
        return None

    def list_records(
        self,
        service_name: str | None = None,
        window_type: WindowType | None = None,
        limit: int = 50,
    ) -> list[ChangeWindowRecord]:
        """List records with optional filters."""
        results = list(self._items)
        if service_name is not None:
            results = [r for r in results if r.service_name == service_name]
        if window_type is not None:
            results = [r for r in results if r.window_type == window_type]
        return results[-limit:]

    # -- domain operations --

    def calculate_window_score(
        self,
        day_of_week: DayOfWeek,
        hour: int,
    ) -> WindowScore:
        """Calculate success score for a time slot."""
        matches = [r for r in self._items if r.day_of_week == day_of_week and r.hour == hour]
        total = len(matches)
        if total == 0:
            return WindowScore(
                day_of_week=day_of_week,
                hour=hour,
            )
        successes = sum(1 for r in matches if r.is_success)
        success_rate = round(successes / total * 100, 2)
        risk = self._rate_to_risk(success_rate)
        score = success_rate
        key = f"{day_of_week}_{hour}"
        ws = WindowScore(
            day_of_week=day_of_week,
            hour=hour,
            success_rate=success_rate,
            total_changes=total,
            risk_level=risk,
            score=score,
        )
        self._scores[key] = ws
        logger.info(
            "change_window.score_calculated",
            day=day_of_week,
            hour=hour,
            score=score,
        )
        return ws

    def find_optimal_windows(
        self,
        service_name: str | None = None,
    ) -> list[WindowScore]:
        """Find the best deployment windows."""
        items = self._items
        if service_name is not None:
            items = [r for r in items if r.service_name == service_name]
        slots: dict[str, list[ChangeWindowRecord]] = {}
        for r in items:
            key = f"{r.day_of_week}_{r.hour}"
            slots.setdefault(key, []).append(r)
        scores: list[WindowScore] = []
        for key, records in slots.items():
            day_str, hour_str = key.rsplit("_", 1)
            day = DayOfWeek(day_str)
            hour = int(hour_str)
            total = len(records)
            successes = sum(1 for r in records if r.is_success)
            rate = round(successes / total * 100, 2)
            risk = self._rate_to_risk(rate)
            scores.append(
                WindowScore(
                    day_of_week=day,
                    hour=hour,
                    success_rate=rate,
                    total_changes=total,
                    risk_level=risk,
                    score=rate,
                )
            )
        scores.sort(key=lambda s: s.score, reverse=True)
        return scores

    def detect_risky_windows(self) -> list[WindowScore]:
        """Detect windows with low success rates."""
        all_scores = self.find_optimal_windows()
        return [s for s in all_scores if s.success_rate < self._min_success_rate]

    def analyze_by_day_of_week(
        self,
    ) -> dict[str, dict[str, Any]]:
        """Analyze success rates grouped by day."""
        by_day: dict[str, list[ChangeWindowRecord]] = {}
        for r in self._items:
            by_day.setdefault(r.day_of_week, []).append(r)
        result: dict[str, dict[str, Any]] = {}
        for day, records in sorted(by_day.items()):
            total = len(records)
            successes = sum(1 for r in records if r.is_success)
            rate = round(successes / total * 100, 2) if total else 0.0
            result[day] = {
                "total_changes": total,
                "success_count": successes,
                "success_rate": rate,
            }
        return result

    def compare_window_types(
        self,
    ) -> dict[str, dict[str, Any]]:
        """Compare success rates across window types."""
        by_type: dict[str, list[ChangeWindowRecord]] = {}
        for r in self._items:
            by_type.setdefault(
                r.window_type,
                [],
            ).append(r)
        result: dict[str, dict[str, Any]] = {}
        for wtype, records in sorted(by_type.items()):
            total = len(records)
            successes = sum(1 for r in records if r.is_success)
            rate = round(successes / total * 100, 2) if total else 0.0
            result[wtype] = {
                "total_changes": total,
                "success_count": successes,
                "success_rate": rate,
            }
        return result

    # -- report --

    def generate_window_report(self) -> WindowReport:
        """Generate a comprehensive window report."""
        total = len(self._items)
        all_scores = self.find_optimal_windows()
        best: dict[str, Any] = {}
        worst: dict[str, Any] = {}
        if all_scores:
            b = all_scores[0]
            best = {
                "day": b.day_of_week,
                "hour": b.hour,
                "success_rate": b.success_rate,
            }
            w = all_scores[-1]
            worst = {
                "day": w.day_of_week,
                "hour": w.hour,
                "success_rate": w.success_rate,
            }
        by_type: dict[str, int] = {}
        for r in self._items:
            key = r.window_type.value
            by_type[key] = by_type.get(key, 0) + 1
        by_risk: dict[str, int] = {}
        for r in self._items:
            key = r.risk_level.value
            by_risk[key] = by_risk.get(key, 0) + 1
        recs = self._build_recommendations(all_scores)
        return WindowReport(
            total_changes=total,
            total_windows_analyzed=len(all_scores),
            best_window=best,
            worst_window=worst,
            by_type=by_type,
            by_risk=by_risk,
            recommendations=recs,
        )

    # -- housekeeping --

    def clear_data(self) -> int:
        """Clear all records. Returns count cleared."""
        count = len(self._items)
        self._items.clear()
        self._scores.clear()
        logger.info("change_window.cleared", count=count)
        return count

    def get_stats(self) -> dict[str, Any]:
        """Return summary statistics."""
        type_dist: dict[str, int] = {}
        for r in self._items:
            key = r.window_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        day_dist: dict[str, int] = {}
        for r in self._items:
            key = r.day_of_week.value
            day_dist[key] = day_dist.get(key, 0) + 1
        return {
            "total_records": len(self._items),
            "min_success_rate": self._min_success_rate,
            "type_distribution": type_dist,
            "day_distribution": day_dist,
        }

    # -- internal helpers --

    def _rate_to_risk(self, rate: float) -> WindowRisk:
        if rate >= 98:
            return WindowRisk.VERY_LOW
        if rate >= 95:
            return WindowRisk.LOW
        if rate >= 90:
            return WindowRisk.MODERATE
        if rate >= 80:
            return WindowRisk.HIGH
        return WindowRisk.VERY_HIGH

    def _build_recommendations(
        self,
        scores: list[WindowScore],
    ) -> list[str]:
        recs: list[str] = []
        risky = [s for s in scores if s.success_rate < self._min_success_rate]
        if risky:
            recs.append(f"{len(risky)} window(s) below {self._min_success_rate}% success rate")
        if scores:
            best = scores[0]
            recs.append(
                f"Best window: {best.day_of_week} at {best.hour}:00 ({best.success_rate}% success)"
            )
        if not recs:
            recs.append("Insufficient data for analysis")
        return recs
