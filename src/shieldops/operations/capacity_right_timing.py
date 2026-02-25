"""Capacity Right-Timing Advisor.

Recommend WHEN to scale based on traffic pattern prediction and cost windows.
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


class ScaleDirection(StrEnum):
    SCALE_UP = "scale_up"
    SCALE_DOWN = "scale_down"
    SCALE_OUT = "scale_out"
    SCALE_IN = "scale_in"
    NO_CHANGE = "no_change"


class TimingConfidence(StrEnum):
    VERY_LOW = "very_low"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    VERY_HIGH = "very_high"


class TrafficPattern(StrEnum):
    DIURNAL = "diurnal"
    WEEKLY_CYCLE = "weekly_cycle"
    SEASONAL = "seasonal"
    EVENT_DRIVEN = "event_driven"
    UNPREDICTABLE = "unpredictable"


# --- Models ---


class TimingRecommendation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    direction: ScaleDirection = ScaleDirection.NO_CHANGE
    recommended_at_hour: int = 0
    confidence: TimingConfidence = TimingConfidence.VERY_LOW
    traffic_pattern: TrafficPattern = TrafficPattern.DIURNAL
    cost_saving_pct: float = 0.0
    reason: str = ""
    status: str = "pending"
    created_at: float = Field(default_factory=time.time)


class TrafficForecastWindow(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    start_hour: int = 0
    end_hour: int = 23
    expected_load_pct: float = 0.0
    pattern: TrafficPattern = TrafficPattern.DIURNAL
    day_of_week: int = 0
    created_at: float = Field(default_factory=time.time)


class TimingReport(BaseModel):
    total_recommendations: int = 0
    total_windows: int = 0
    by_direction: dict[str, int] = Field(default_factory=dict)
    by_pattern: dict[str, int] = Field(default_factory=dict)
    by_confidence: dict[str, int] = Field(default_factory=dict)
    avg_cost_saving_pct: float = 0.0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class CapacityRightTimingAdvisor:
    """Recommend WHEN to scale based on traffic pattern prediction and cost windows."""

    def __init__(
        self,
        max_records: int = 200000,
        lookahead_hours: int = 24,
    ) -> None:
        self._max_records = max_records
        self._lookahead_hours = lookahead_hours
        self._items: list[TimingRecommendation] = []
        self._windows: list[TrafficForecastWindow] = []
        logger.info(
            "capacity_right_timing.initialized",
            max_records=max_records,
            lookahead_hours=lookahead_hours,
        )

    # -- create / get / list -----------------------------------------

    def create_recommendation(
        self,
        service_name: str,
        direction: ScaleDirection = ScaleDirection.NO_CHANGE,
        recommended_at_hour: int = 0,
        confidence: TimingConfidence = TimingConfidence.VERY_LOW,
        traffic_pattern: TrafficPattern = TrafficPattern.DIURNAL,
        cost_saving_pct: float = 0.0,
        reason: str = "",
        **kw: Any,
    ) -> TimingRecommendation:
        rec = TimingRecommendation(
            service_name=service_name,
            direction=direction,
            recommended_at_hour=recommended_at_hour,
            confidence=confidence,
            traffic_pattern=traffic_pattern,
            cost_saving_pct=cost_saving_pct,
            reason=reason,
            **kw,
        )
        self._items.append(rec)
        if len(self._items) > self._max_records:
            self._items = self._items[-self._max_records :]
        logger.info(
            "capacity_right_timing.recommendation_created",
            rec_id=rec.id,
            service_name=service_name,
        )
        return rec

    def get_recommendation(self, rec_id: str) -> TimingRecommendation | None:
        for item in self._items:
            if item.id == rec_id:
                return item
        return None

    def list_recommendations(
        self,
        service_name: str | None = None,
        direction: ScaleDirection | None = None,
        limit: int = 50,
    ) -> list[TimingRecommendation]:
        results = list(self._items)
        if service_name is not None:
            results = [r for r in results if r.service_name == service_name]
        if direction is not None:
            results = [r for r in results if r.direction == direction]
        return results[-limit:]

    # -- traffic windows ---------------------------------------------

    def register_traffic_window(
        self,
        service_name: str,
        start_hour: int = 0,
        end_hour: int = 23,
        expected_load_pct: float = 0.0,
        pattern: TrafficPattern = TrafficPattern.DIURNAL,
        day_of_week: int = 0,
        **kw: Any,
    ) -> TrafficForecastWindow:
        window = TrafficForecastWindow(
            service_name=service_name,
            start_hour=start_hour,
            end_hour=end_hour,
            expected_load_pct=expected_load_pct,
            pattern=pattern,
            day_of_week=day_of_week,
            **kw,
        )
        self._windows.append(window)
        if len(self._windows) > self._max_records:
            self._windows = self._windows[-self._max_records :]
        logger.info(
            "capacity_right_timing.window_registered",
            window_id=window.id,
            service_name=service_name,
        )
        return window

    def list_traffic_windows(
        self,
        service_name: str | None = None,
        limit: int = 50,
    ) -> list[TrafficForecastWindow]:
        results = list(self._windows)
        if service_name is not None:
            results = [r for r in results if r.service_name == service_name]
        return results[-limit:]

    # -- domain operations -------------------------------------------

    def find_optimal_scale_time(
        self,
        service_name: str,
        direction: ScaleDirection = ScaleDirection.SCALE_UP,
    ) -> TimingRecommendation:
        """Find the optimal time to scale for a service based on traffic windows."""
        windows = [w for w in self._windows if w.service_name == service_name]
        if not windows:
            return self.create_recommendation(
                service_name=service_name,
                direction=direction,
                confidence=TimingConfidence.VERY_LOW,
                reason="No traffic windows registered",
            )
        if direction in (ScaleDirection.SCALE_UP, ScaleDirection.SCALE_OUT):
            # Scale up before peak — find lowest load window before peak
            sorted_w = sorted(windows, key=lambda w: w.expected_load_pct)
            best = sorted_w[0]
            hour = max(0, best.start_hour - 1)
            saving = round(max(0, 100 - best.expected_load_pct) * 0.1, 2)
        else:
            # Scale down at lowest load
            sorted_w = sorted(windows, key=lambda w: w.expected_load_pct)
            best = sorted_w[0]
            hour = best.start_hour
            saving = round(best.expected_load_pct * 0.5, 2)
        confidence = (
            TimingConfidence.HIGH
            if len(windows) >= 3
            else TimingConfidence.MODERATE
            if len(windows) >= 2
            else TimingConfidence.LOW
        )
        return self.create_recommendation(
            service_name=service_name,
            direction=direction,
            recommended_at_hour=hour,
            confidence=confidence,
            traffic_pattern=best.pattern,
            cost_saving_pct=saving,
            reason=f"Based on {len(windows)} traffic window(s)",
        )

    def evaluate_timing(
        self,
        rec_id: str,
    ) -> dict[str, Any]:
        """Evaluate whether a timing recommendation is still valid."""
        rec = self.get_recommendation(rec_id)
        if rec is None:
            return {"valid": False, "reason": "Recommendation not found"}
        windows = [w for w in self._windows if w.service_name == rec.service_name]
        if not windows:
            return {"valid": False, "reason": "No traffic windows available"}
        return {
            "valid": True,
            "recommendation_id": rec.id,
            "direction": rec.direction.value,
            "recommended_hour": rec.recommended_at_hour,
            "window_count": len(windows),
            "confidence": rec.confidence.value,
        }

    def cancel_recommendation(self, rec_id: str) -> bool:
        """Cancel a pending recommendation."""
        rec = self.get_recommendation(rec_id)
        if rec is None:
            return False
        rec.status = "cancelled"
        logger.info("capacity_right_timing.cancelled", rec_id=rec_id)
        return True

    # -- report / stats ----------------------------------------------

    def generate_timing_report(self) -> TimingReport:
        by_direction: dict[str, int] = {}
        for r in self._items:
            key = r.direction.value
            by_direction[key] = by_direction.get(key, 0) + 1
        by_pattern: dict[str, int] = {}
        for r in self._items:
            key = r.traffic_pattern.value
            by_pattern[key] = by_pattern.get(key, 0) + 1
        by_confidence: dict[str, int] = {}
        for r in self._items:
            key = r.confidence.value
            by_confidence[key] = by_confidence.get(key, 0) + 1
        savings = [r.cost_saving_pct for r in self._items if r.cost_saving_pct > 0]
        avg_saving = round(sum(savings) / len(savings), 2) if savings else 0.0
        recs: list[str] = []
        pending = [r for r in self._items if r.status == "pending"]
        if pending:
            recs.append(f"{len(pending)} pending recommendation(s) to review")
        if not recs:
            recs.append("No pending capacity timing actions")
        return TimingReport(
            total_recommendations=len(self._items),
            total_windows=len(self._windows),
            by_direction=by_direction,
            by_pattern=by_pattern,
            by_confidence=by_confidence,
            avg_cost_saving_pct=avg_saving,
            recommendations=recs,
        )

    def clear_data(self) -> int:
        count = len(self._items)
        self._items.clear()
        self._windows.clear()
        logger.info("capacity_right_timing.cleared", count=count)
        return count

    def get_stats(self) -> dict[str, Any]:
        direction_dist: dict[str, int] = {}
        for r in self._items:
            key = r.direction.value
            direction_dist[key] = direction_dist.get(key, 0) + 1
        return {
            "total_recommendations": len(self._items),
            "total_windows": len(self._windows),
            "lookahead_hours": self._lookahead_hours,
            "direction_distribution": direction_dist,
        }
