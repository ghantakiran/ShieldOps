"""Automated Threshold Tuner — dynamically adjust alert thresholds based on historical outcomes."""

from __future__ import annotations

import statistics
import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ThresholdDirection(StrEnum):
    UPPER = "upper"
    LOWER = "lower"
    BOTH = "both"


class TuningAction(StrEnum):
    INCREASE = "increase"
    DECREASE = "decrease"
    NO_CHANGE = "no_change"
    DISABLE = "disable"


class TuningStatus(StrEnum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    APPLIED = "applied"
    REJECTED = "rejected"


# --- Models ---


class ThresholdConfig(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    metric_name: str
    service: str = ""
    direction: ThresholdDirection = ThresholdDirection.UPPER
    current_value: float = 0.0
    min_value: float = 0.0
    max_value: float = 100.0
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)


class MetricSample(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    threshold_id: str
    value: float
    triggered_alert: bool = False
    was_actionable: bool = False
    recorded_at: float = Field(default_factory=time.time)


class TuningRecommendation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    threshold_id: str
    action: TuningAction
    current_value: float = 0.0
    recommended_value: float = 0.0
    reason: str = ""
    status: TuningStatus = TuningStatus.PROPOSED
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class ThresholdTuningEngine:
    """Dynamically adjusts alert thresholds based on historical outcomes."""

    def __init__(
        self,
        max_thresholds: int = 2000,
        max_samples: int = 100000,
    ) -> None:
        self._max_thresholds = max_thresholds
        self._max_samples = max_samples
        self._thresholds: dict[str, ThresholdConfig] = {}
        self._samples: list[MetricSample] = []
        self._recommendations: dict[str, TuningRecommendation] = {}
        logger.info(
            "threshold_tuner.initialized",
            max_thresholds=max_thresholds,
            max_samples=max_samples,
        )

    def register_threshold(
        self,
        metric_name: str,
        current_value: float,
        direction: ThresholdDirection = ThresholdDirection.UPPER,
        **kw: Any,
    ) -> ThresholdConfig:
        """Register a new threshold configuration."""
        config = ThresholdConfig(
            metric_name=metric_name,
            current_value=current_value,
            direction=direction,
            **kw,
        )
        self._thresholds[config.id] = config
        if len(self._thresholds) > self._max_thresholds:
            oldest = next(iter(self._thresholds))
            del self._thresholds[oldest]
        logger.info(
            "threshold_tuner.threshold_registered",
            threshold_id=config.id,
            metric_name=metric_name,
            current_value=current_value,
        )
        return config

    def record_sample(
        self,
        threshold_id: str,
        value: float,
        triggered_alert: bool = False,
        was_actionable: bool = False,
    ) -> MetricSample | None:
        """Record a metric sample for a threshold."""
        if threshold_id not in self._thresholds:
            return None
        sample = MetricSample(
            threshold_id=threshold_id,
            value=value,
            triggered_alert=triggered_alert,
            was_actionable=was_actionable,
        )
        self._samples.append(sample)
        if len(self._samples) > self._max_samples:
            self._samples = self._samples[-self._max_samples :]
        return sample

    def generate_recommendations(self) -> list[TuningRecommendation]:
        """Generate tuning recommendations for all thresholds."""
        new_recs: list[TuningRecommendation] = []
        for tid, config in self._thresholds.items():
            samples = [s for s in self._samples if s.threshold_id == tid]
            if len(samples) < 5:
                continue
            triggered = [s for s in samples if s.triggered_alert]
            actionable = [s for s in triggered if s.was_actionable]
            values = [s.value for s in samples]
            mean_val = statistics.mean(values)
            if len(triggered) == 0:
                action = TuningAction.NO_CHANGE
                rec_val = config.current_value
                reason = "No alerts triggered; threshold may be too lenient"
            elif len(actionable) == 0:
                action = TuningAction.INCREASE
                rec_val = min(config.current_value * 1.2, config.max_value)
                reason = "All triggered alerts were non-actionable; increase threshold"
            elif len(actionable) / len(triggered) < 0.3:
                action = TuningAction.INCREASE
                rec_val = min(config.current_value * 1.1, config.max_value)
                a, t = len(actionable), len(triggered)
                reason = f"Low actionability ({a}/{t}); increase threshold"
            elif len(actionable) / len(triggered) > 0.8:
                action = TuningAction.DECREASE
                stddev = statistics.stdev(values) if len(values) > 1 else 0.0
                rec_val = max(mean_val + stddev, config.min_value)
                a, t = len(actionable), len(triggered)
                reason = f"High actionability ({a}/{t}); tighten threshold"
            else:
                action = TuningAction.NO_CHANGE
                rec_val = config.current_value
                reason = "Actionability within acceptable range"
            rec = TuningRecommendation(
                threshold_id=tid,
                action=action,
                current_value=config.current_value,
                recommended_value=round(rec_val, 4),
                reason=reason,
            )
            self._recommendations[rec.id] = rec
            new_recs.append(rec)
        return new_recs

    def apply_recommendation(self, recommendation_id: str) -> TuningRecommendation | None:
        """Apply a tuning recommendation."""
        rec = self._recommendations.get(recommendation_id)
        if rec is None:
            return None
        config = self._thresholds.get(rec.threshold_id)
        if config is not None:
            config.current_value = rec.recommended_value
            config.updated_at = time.time()
        rec.status = TuningStatus.APPLIED
        logger.info(
            "threshold_tuner.recommendation_applied",
            recommendation_id=recommendation_id,
            threshold_id=rec.threshold_id,
        )
        return rec

    def reject_recommendation(self, recommendation_id: str) -> TuningRecommendation | None:
        """Reject a tuning recommendation."""
        rec = self._recommendations.get(recommendation_id)
        if rec is None:
            return None
        rec.status = TuningStatus.REJECTED
        return rec

    def get_threshold(self, threshold_id: str) -> ThresholdConfig | None:
        """Retrieve a threshold by ID."""
        return self._thresholds.get(threshold_id)

    def list_thresholds(
        self,
        direction: ThresholdDirection | None = None,
    ) -> list[ThresholdConfig]:
        """List thresholds with optional filter."""
        results = list(self._thresholds.values())
        if direction is not None:
            results = [t for t in results if t.direction == direction]
        return results

    def list_recommendations(
        self,
        status: TuningStatus | None = None,
    ) -> list[TuningRecommendation]:
        """List recommendations with optional status filter."""
        results = list(self._recommendations.values())
        if status is not None:
            results = [r for r in results if r.status == status]
        return results

    def delete_threshold(self, threshold_id: str) -> bool:
        """Delete a threshold."""
        if threshold_id in self._thresholds:
            del self._thresholds[threshold_id]
            logger.info("threshold_tuner.threshold_deleted", threshold_id=threshold_id)
            return True
        return False

    def get_stats(self) -> dict[str, Any]:
        """Return summary statistics."""
        direction_counts: dict[str, int] = {}
        for t in self._thresholds.values():
            direction_counts[t.direction] = direction_counts.get(t.direction, 0) + 1
        status_counts: dict[str, int] = {}
        for r in self._recommendations.values():
            status_counts[r.status] = status_counts.get(r.status, 0) + 1
        return {
            "total_thresholds": len(self._thresholds),
            "total_samples": len(self._samples),
            "total_recommendations": len(self._recommendations),
            "direction_distribution": direction_counts,
            "recommendation_status_distribution": status_counts,
        }
