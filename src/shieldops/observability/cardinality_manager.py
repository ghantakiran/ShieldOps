"""Metric Cardinality Manager — detect and manage high-cardinality metric explosion."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class CardinalityLevel(StrEnum):
    NORMAL = "normal"
    ELEVATED = "elevated"
    HIGH = "high"
    CRITICAL = "critical"
    EXPLOSIVE = "explosive"


class LabelAction(StrEnum):
    KEEP = "keep"
    AGGREGATE = "aggregate"
    DROP = "drop"
    SAMPLE = "sample"
    RELABEL = "relabel"


class MetricType(StrEnum):
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"
    UNTYPED = "untyped"


# --- Models ---


class CardinalityRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    metric_name: str = ""
    metric_type: MetricType = MetricType.COUNTER
    cardinality: int = 0
    label_count: int = 0
    level: CardinalityLevel = CardinalityLevel.NORMAL
    labels: list[str] = Field(default_factory=list)
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class CardinalityRule(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    metric_pattern: str = ""
    label_name: str = ""
    action: LabelAction = LabelAction.KEEP
    reason: str = ""
    created_at: float = Field(default_factory=time.time)


class CardinalityReport(BaseModel):
    total_metrics: int = 0
    total_rules: int = 0
    avg_cardinality: float = 0.0
    by_level: dict[str, int] = Field(default_factory=dict)
    by_type: dict[str, int] = Field(default_factory=dict)
    high_cardinality_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class MetricCardinalityManager:
    """Detect and manage high-cardinality metric explosion."""

    def __init__(
        self,
        max_records: int = 200000,
        max_cardinality_threshold: int = 10000,
    ) -> None:
        self._max_records = max_records
        self._max_cardinality_threshold = max_cardinality_threshold
        self._records: list[CardinalityRecord] = []
        self._rules: list[CardinalityRule] = []
        logger.info(
            "cardinality_manager.initialized",
            max_records=max_records,
            max_cardinality_threshold=max_cardinality_threshold,
        )

    # -- internal helpers ------------------------------------------------

    def _cardinality_to_level(self, cardinality: int) -> CardinalityLevel:
        if cardinality >= self._max_cardinality_threshold * 10:
            return CardinalityLevel.EXPLOSIVE
        if cardinality >= self._max_cardinality_threshold * 5:
            return CardinalityLevel.CRITICAL
        if cardinality >= self._max_cardinality_threshold:
            return CardinalityLevel.HIGH
        if cardinality >= self._max_cardinality_threshold // 2:
            return CardinalityLevel.ELEVATED
        return CardinalityLevel.NORMAL

    # -- record / get / list ---------------------------------------------

    def record_metric(
        self,
        metric_name: str,
        metric_type: MetricType = MetricType.COUNTER,
        cardinality: int = 0,
        label_count: int = 0,
        level: CardinalityLevel | None = None,
        labels: list[str] | None = None,
        details: str = "",
    ) -> CardinalityRecord:
        if level is None:
            level = self._cardinality_to_level(cardinality)
        record = CardinalityRecord(
            metric_name=metric_name,
            metric_type=metric_type,
            cardinality=cardinality,
            label_count=label_count,
            level=level,
            labels=labels or [],
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "cardinality_manager.metric_recorded",
            record_id=record.id,
            metric_name=metric_name,
            cardinality=cardinality,
            level=level.value,
        )
        return record

    def get_metric(self, record_id: str) -> CardinalityRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_metrics(
        self,
        metric_name: str | None = None,
        level: CardinalityLevel | None = None,
        limit: int = 50,
    ) -> list[CardinalityRecord]:
        results = list(self._records)
        if metric_name is not None:
            results = [r for r in results if r.metric_name == metric_name]
        if level is not None:
            results = [r for r in results if r.level == level]
        return results[-limit:]

    def add_rule(
        self,
        metric_pattern: str,
        label_name: str,
        action: LabelAction = LabelAction.KEEP,
        reason: str = "",
    ) -> CardinalityRule:
        rule = CardinalityRule(
            metric_pattern=metric_pattern,
            label_name=label_name,
            action=action,
            reason=reason,
        )
        self._rules.append(rule)
        if len(self._rules) > self._max_records:
            self._rules = self._rules[-self._max_records :]
        logger.info(
            "cardinality_manager.rule_added",
            rule_id=rule.id,
            metric_pattern=metric_pattern,
            action=action.value,
        )
        return rule

    # -- domain operations -----------------------------------------------

    def detect_high_cardinality(self) -> list[dict[str, Any]]:
        """Find metrics exceeding cardinality thresholds."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.cardinality >= self._max_cardinality_threshold:
                results.append(
                    {
                        "metric_name": r.metric_name,
                        "cardinality": r.cardinality,
                        "level": r.level.value,
                        "label_count": r.label_count,
                        "labels": r.labels,
                    }
                )
        results.sort(key=lambda x: x["cardinality"], reverse=True)
        return results

    def recommend_label_actions(self, metric_name: str) -> list[dict[str, Any]]:
        """Recommend label actions for a high-cardinality metric."""
        metric_records = [r for r in self._records if r.metric_name == metric_name]
        if not metric_records:
            return []
        latest = metric_records[-1]
        recommendations: list[dict[str, Any]] = []
        for label in latest.labels:
            action = LabelAction.KEEP
            reason = "Low impact label"
            if latest.cardinality >= self._max_cardinality_threshold * 5:
                action = LabelAction.DROP
                reason = "Explosive cardinality — drop high-entropy label"
            elif latest.cardinality >= self._max_cardinality_threshold:
                action = LabelAction.AGGREGATE
                reason = "High cardinality — aggregate label values"
            recommendations.append(
                {
                    "label": label,
                    "recommended_action": action.value,
                    "reason": reason,
                }
            )
        return recommendations

    def analyze_growth_trend(self) -> list[dict[str, Any]]:
        """Analyze cardinality growth trends per metric."""
        metric_history: dict[str, list[int]] = {}
        for r in self._records:
            metric_history.setdefault(r.metric_name, []).append(r.cardinality)
        results: list[dict[str, Any]] = []
        for name, values in metric_history.items():
            if len(values) < 2:
                growth_rate = 0.0
            else:
                growth_rate = round(((values[-1] - values[0]) / max(values[0], 1)) * 100, 2)
            results.append(
                {
                    "metric_name": name,
                    "current_cardinality": values[-1],
                    "initial_cardinality": values[0],
                    "growth_rate_pct": growth_rate,
                    "samples": len(values),
                }
            )
        results.sort(key=lambda x: x["growth_rate_pct"], reverse=True)
        return results

    def identify_label_culprits(self) -> list[dict[str, Any]]:
        """Identify labels contributing most to cardinality explosion."""
        label_freq: dict[str, int] = {}
        label_high: dict[str, int] = {}
        for r in self._records:
            for label in r.labels:
                label_freq[label] = label_freq.get(label, 0) + 1
                if r.cardinality >= self._max_cardinality_threshold:
                    label_high[label] = label_high.get(label, 0) + 1
        results: list[dict[str, Any]] = []
        for label, freq in label_freq.items():
            high_count = label_high.get(label, 0)
            results.append(
                {
                    "label": label,
                    "total_occurrences": freq,
                    "high_cardinality_occurrences": high_count,
                    "risk_ratio": round(high_count / max(freq, 1), 2),
                }
            )
        results.sort(key=lambda x: x["risk_ratio"], reverse=True)
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> CardinalityReport:
        by_level: dict[str, int] = {}
        by_type: dict[str, int] = {}
        for r in self._records:
            by_level[r.level.value] = by_level.get(r.level.value, 0) + 1
            by_type[r.metric_type.value] = by_type.get(r.metric_type.value, 0) + 1
        avg_card = (
            round(sum(r.cardinality for r in self._records) / len(self._records), 2)
            if self._records
            else 0.0
        )
        high_count = sum(
            1 for r in self._records if r.cardinality >= self._max_cardinality_threshold
        )
        recs: list[str] = []
        if high_count > 0:
            recs.append(
                f"{high_count} metric(s) exceed cardinality threshold "
                f"of {self._max_cardinality_threshold}"
            )
        explosive = sum(1 for r in self._records if r.level == CardinalityLevel.EXPLOSIVE)
        if explosive > 0:
            recs.append(f"{explosive} metric(s) at explosive cardinality level")
        if not recs:
            recs.append("Metric cardinality within acceptable limits")
        return CardinalityReport(
            total_metrics=len(self._records),
            total_rules=len(self._rules),
            avg_cardinality=avg_card,
            by_level=by_level,
            by_type=by_type,
            high_cardinality_count=high_count,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._rules.clear()
        logger.info("cardinality_manager.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        level_dist: dict[str, int] = {}
        for r in self._records:
            key = r.level.value
            level_dist[key] = level_dist.get(key, 0) + 1
        return {
            "total_metrics": len(self._records),
            "total_rules": len(self._rules),
            "max_cardinality_threshold": self._max_cardinality_threshold,
            "level_distribution": level_dist,
            "unique_metric_names": len({r.metric_name for r in self._records}),
        }
