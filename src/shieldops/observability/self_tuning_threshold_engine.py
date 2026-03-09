"""Self-Tuning Threshold Engine — auto-adjusting alert thresholds based on patterns."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class SeasonalityType(StrEnum):
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    NONE = "none"


class TuningAction(StrEnum):
    RAISE = "raise"
    LOWER = "lower"
    HOLD = "hold"
    RESET = "reset"


class ThresholdStatus(StrEnum):
    ACTIVE = "active"
    TUNING = "tuning"
    DISABLED = "disabled"
    LOCKED = "locked"


# --- Models ---


class ThresholdRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    metric_name: str = ""
    current_value: float = 0.0
    baseline: float = 0.0
    upper_bound: float = 100.0
    lower_bound: float = 0.0
    status: ThresholdStatus = ThresholdStatus.ACTIVE
    seasonality: SeasonalityType = SeasonalityType.NONE
    created_at: float = Field(default_factory=time.time)


class TuningEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    metric_name: str = ""
    action: TuningAction = TuningAction.HOLD
    old_value: float = 0.0
    new_value: float = 0.0
    reason: str = ""
    created_at: float = Field(default_factory=time.time)


class ThresholdReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_thresholds: int = 0
    total_tuning_events: int = 0
    avg_baseline: float = 0.0
    by_status: dict[str, int] = Field(default_factory=dict)
    by_seasonality: dict[str, int] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class SelfTuningThresholdEngine:
    """Auto-adjusting alert thresholds based on patterns."""

    def __init__(
        self,
        max_records: int = 100000,
        sensitivity: float = 2.0,
    ) -> None:
        self._max_records = max_records
        self._sensitivity = sensitivity
        self._thresholds: list[ThresholdRecord] = []
        self._tuning_history: list[TuningEvent] = []
        logger.info(
            "self_tuning_threshold_engine.initialized",
            max_records=max_records,
            sensitivity=sensitivity,
        )

    def add_threshold(
        self,
        metric_name: str,
        baseline: float = 50.0,
        upper_bound: float = 100.0,
        lower_bound: float = 0.0,
        status: ThresholdStatus = ThresholdStatus.ACTIVE,
    ) -> ThresholdRecord:
        """Register a metric threshold."""
        record = ThresholdRecord(
            metric_name=metric_name,
            current_value=baseline,
            baseline=baseline,
            upper_bound=upper_bound,
            lower_bound=lower_bound,
            status=status,
        )
        self._thresholds.append(record)
        if len(self._thresholds) > self._max_records:
            self._thresholds = self._thresholds[-self._max_records :]
        logger.info(
            "self_tuning_threshold_engine.threshold_added",
            metric=metric_name,
            baseline=baseline,
        )
        return record

    def tune_thresholds(self, metric_name: str | None = None) -> list[TuningEvent]:
        """Auto-tune thresholds based on recent values."""
        targets = self._thresholds
        if metric_name:
            targets = [t for t in targets if t.metric_name == metric_name]
        events: list[TuningEvent] = []
        for t in targets:
            if t.status in (ThresholdStatus.DISABLED, ThresholdStatus.LOCKED):
                continue
            diff = t.current_value - t.baseline
            if abs(diff) < self._sensitivity:
                action = TuningAction.HOLD
                new_val = t.upper_bound
            elif diff > 0:
                action = TuningAction.RAISE
                new_val = round(t.upper_bound + diff * 0.1, 2)
            else:
                action = TuningAction.LOWER
                new_val = round(t.upper_bound + diff * 0.1, 2)
            event = TuningEvent(
                metric_name=t.metric_name,
                action=action,
                old_value=t.upper_bound,
                new_value=new_val,
                reason=f"diff={round(diff, 2)}, sensitivity={self._sensitivity}",
            )
            if action != TuningAction.HOLD:
                t.upper_bound = new_val
            events.append(event)
            self._tuning_history.append(event)
        logger.info("self_tuning_threshold_engine.tuned", count=len(events))
        return events

    def analyze_seasonality(self, metric_name: str) -> dict[str, Any]:
        """Analyze seasonality patterns for a metric."""
        records = [t for t in self._thresholds if t.metric_name == metric_name]
        if not records:
            return {"metric": metric_name, "seasonality": "none", "sample_count": 0}
        values = [r.current_value for r in records]
        avg = sum(values) / len(values) if values else 0
        variance = sum((v - avg) ** 2 for v in values) / len(values) if values else 0
        if variance > 500:
            seasonality = SeasonalityType.DAILY
        elif variance > 100:
            seasonality = SeasonalityType.HOURLY
        else:
            seasonality = SeasonalityType.NONE
        for r in records:
            r.seasonality = seasonality
        return {
            "metric": metric_name,
            "seasonality": seasonality.value,
            "sample_count": len(records),
            "avg_value": round(avg, 2),
            "variance": round(variance, 2),
        }

    def calculate_dynamic_baseline(self, metric_name: str) -> dict[str, Any]:
        """Calculate dynamic baseline for a metric."""
        records = [t for t in self._thresholds if t.metric_name == metric_name]
        if not records:
            return {"metric": metric_name, "baseline": 0.0, "samples": 0}
        values = [r.current_value for r in records]
        avg = sum(values) / len(values)
        std_dev = (sum((v - avg) ** 2 for v in values) / len(values)) ** 0.5
        dynamic_upper = round(avg + self._sensitivity * std_dev, 2)
        dynamic_lower = round(avg - self._sensitivity * std_dev, 2)
        return {
            "metric": metric_name,
            "baseline": round(avg, 2),
            "std_dev": round(std_dev, 2),
            "dynamic_upper": dynamic_upper,
            "dynamic_lower": dynamic_lower,
            "samples": len(values),
        }

    def apply_thresholds(self, metric_name: str, value: float) -> dict[str, Any]:
        """Check a value against current thresholds."""
        records = [t for t in self._thresholds if t.metric_name == metric_name]
        if not records:
            return {"metric": metric_name, "status": "no_threshold", "breached": False}
        latest = records[-1]
        breached = value > latest.upper_bound or value < latest.lower_bound
        return {
            "metric": metric_name,
            "value": value,
            "upper_bound": latest.upper_bound,
            "lower_bound": latest.lower_bound,
            "breached": breached,
            "status": "breached" if breached else "ok",
        }

    def get_tuning_history(
        self,
        metric_name: str | None = None,
        limit: int = 50,
    ) -> list[TuningEvent]:
        """Get tuning history, optionally filtered by metric."""
        results = list(self._tuning_history)
        if metric_name:
            results = [e for e in results if e.metric_name == metric_name]
        return results[-limit:]

    def generate_report(self) -> ThresholdReport:
        """Generate threshold tuning report."""
        by_status: dict[str, int] = {}
        by_seas: dict[str, int] = {}
        for t in self._thresholds:
            by_status[t.status.value] = by_status.get(t.status.value, 0) + 1
            by_seas[t.seasonality.value] = by_seas.get(t.seasonality.value, 0) + 1
        baselines = [t.baseline for t in self._thresholds]
        avg_bl = round(sum(baselines) / len(baselines), 2) if baselines else 0.0
        recs: list[str] = []
        locked = sum(1 for t in self._thresholds if t.status == ThresholdStatus.LOCKED)
        if locked > 0:
            recs.append(f"{locked} threshold(s) locked — review for staleness")
        if not recs:
            recs.append("Thresholds are healthy")
        return ThresholdReport(
            total_thresholds=len(self._thresholds),
            total_tuning_events=len(self._tuning_history),
            avg_baseline=avg_bl,
            by_status=by_status,
            by_seasonality=by_seas,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        """Clear all thresholds and tuning history."""
        self._thresholds.clear()
        self._tuning_history.clear()
        logger.info("self_tuning_threshold_engine.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        """Return engine statistics."""
        return {
            "total_thresholds": len(self._thresholds),
            "total_tuning_events": len(self._tuning_history),
            "sensitivity": self._sensitivity,
            "unique_metrics": len({t.metric_name for t in self._thresholds}),
        }
