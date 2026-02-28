"""Alert Noise Classifier — classify and track alert noise across monitoring sources."""

from __future__ import annotations

import time
from enum import StrEnum
from typing import Any
from uuid import uuid4

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class NoiseCategory(StrEnum):
    FALSE_POSITIVE = "false_positive"
    TRANSIENT = "transient"
    DUPLICATE = "duplicate"
    LOW_PRIORITY = "low_priority"
    INFORMATIONAL = "informational"


class SignalStrength(StrEnum):
    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"
    NOISE = "noise"
    UNKNOWN = "unknown"


class ClassificationMethod(StrEnum):
    RULE_BASED = "rule_based"
    ML_MODEL = "ml_model"
    HEURISTIC = "heuristic"
    MANUAL = "manual"
    HYBRID = "hybrid"


# --- Models ---


class NoiseRecord(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    alert_name: str = ""
    source: str = ""
    category: NoiseCategory = NoiseCategory.INFORMATIONAL
    signal_strength: SignalStrength = SignalStrength.UNKNOWN
    method: ClassificationMethod = ClassificationMethod.RULE_BASED
    noise_score: float = 0.0
    suppressed: bool = False
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class NoiseRule(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    rule_name: str = ""
    category: NoiseCategory = NoiseCategory.INFORMATIONAL
    method: ClassificationMethod = ClassificationMethod.RULE_BASED
    pattern: str = ""
    threshold: float = 0.5
    enabled: bool = True
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class NoiseClassifierReport(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    total_records: int = 0
    total_rules: int = 0
    noise_count: int = 0
    signal_count: int = 0
    noise_ratio_pct: float = 0.0
    by_category: dict[str, int] = Field(default_factory=dict)
    by_signal_strength: dict[str, int] = Field(default_factory=dict)
    by_method: dict[str, int] = Field(default_factory=dict)
    top_noisy_sources: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class AlertNoiseClassifier:
    """Classify alert noise and surface signal-rich alerts for operator attention."""

    def __init__(
        self,
        max_records: int = 200000,
        max_noise_ratio_pct: float = 30.0,
    ) -> None:
        self._max_records = max_records
        self._max_noise_ratio_pct = max_noise_ratio_pct
        self._records: list[NoiseRecord] = []
        self._rules: list[NoiseRule] = []
        logger.info(
            "noise_classifier.initialized",
            max_records=max_records,
            max_noise_ratio_pct=max_noise_ratio_pct,
        )

    # -- CRUD --

    def record_noise(
        self,
        alert_name: str,
        source: str = "",
        category: NoiseCategory = NoiseCategory.INFORMATIONAL,
        signal_strength: SignalStrength = SignalStrength.UNKNOWN,
        method: ClassificationMethod = ClassificationMethod.RULE_BASED,
        noise_score: float = 0.0,
        suppressed: bool = False,
        details: str = "",
    ) -> NoiseRecord:
        record = NoiseRecord(
            alert_name=alert_name,
            source=source,
            category=category,
            signal_strength=signal_strength,
            method=method,
            noise_score=noise_score,
            suppressed=suppressed,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "noise_classifier.recorded",
            record_id=record.id,
            alert_name=alert_name,
            category=category.value,
        )
        return record

    def get_noise(self, record_id: str) -> NoiseRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_noises(
        self,
        category: NoiseCategory | None = None,
        signal_strength: SignalStrength | None = None,
        method: ClassificationMethod | None = None,
        limit: int = 50,
    ) -> list[NoiseRecord]:
        results = list(self._records)
        if category is not None:
            results = [r for r in results if r.category == category]
        if signal_strength is not None:
            results = [r for r in results if r.signal_strength == signal_strength]
        if method is not None:
            results = [r for r in results if r.method == method]
        return results[-limit:]

    def add_rule(
        self,
        rule_name: str,
        category: NoiseCategory = NoiseCategory.INFORMATIONAL,
        method: ClassificationMethod = ClassificationMethod.RULE_BASED,
        pattern: str = "",
        threshold: float = 0.5,
        enabled: bool = True,
        description: str = "",
    ) -> NoiseRule:
        rule = NoiseRule(
            rule_name=rule_name,
            category=category,
            method=method,
            pattern=pattern,
            threshold=threshold,
            enabled=enabled,
            description=description,
        )
        self._rules.append(rule)
        if len(self._rules) > self._max_records:
            self._rules = self._rules[-self._max_records :]
        logger.info(
            "noise_classifier.rule_added",
            rule_id=rule.id,
            rule_name=rule_name,
            category=category.value,
        )
        return rule

    # -- Domain operations --

    def analyze_noise_by_source(self) -> dict[str, Any]:
        """Compute noise ratio grouped by alert source."""
        source_noise: dict[str, int] = {}
        source_total: dict[str, int] = {}
        for r in self._records:
            if not r.source:
                continue
            source_total[r.source] = source_total.get(r.source, 0) + 1
            if r.signal_strength == SignalStrength.NOISE:
                source_noise[r.source] = source_noise.get(r.source, 0) + 1
        breakdown: list[dict[str, Any]] = []
        for source, total in source_total.items():
            noise_count = source_noise.get(source, 0)
            ratio = round(noise_count / total * 100, 2) if total else 0.0
            breakdown.append(
                {
                    "source": source,
                    "total_alerts": total,
                    "noise_count": noise_count,
                    "noise_ratio_pct": ratio,
                }
            )
        breakdown.sort(key=lambda x: x["noise_ratio_pct"], reverse=True)
        return {
            "total_sources": len(source_total),
            "breakdown": breakdown,
        }

    def identify_noisy_alerts(self) -> list[dict[str, Any]]:
        """Find alert names with the highest noise scores."""
        name_scores: dict[str, list[float]] = {}
        for r in self._records:
            if not r.alert_name:
                continue
            name_scores.setdefault(r.alert_name, []).append(r.noise_score)
        results: list[dict[str, Any]] = []
        for name, scores in name_scores.items():
            avg_score = round(sum(scores) / len(scores), 4) if scores else 0.0
            results.append(
                {
                    "alert_name": name,
                    "avg_noise_score": avg_score,
                    "occurrence_count": len(scores),
                }
            )
        results.sort(key=lambda x: x["avg_noise_score"], reverse=True)
        return results

    def rank_by_noise_ratio(self) -> list[dict[str, Any]]:
        """Rank alert names by their noise-to-total ratio."""
        name_noise: dict[str, int] = {}
        name_total: dict[str, int] = {}
        for r in self._records:
            if not r.alert_name:
                continue
            name_total[r.alert_name] = name_total.get(r.alert_name, 0) + 1
            if r.signal_strength in (SignalStrength.NOISE, SignalStrength.WEAK):
                name_noise[r.alert_name] = name_noise.get(r.alert_name, 0) + 1
        results: list[dict[str, Any]] = []
        for name, total in name_total.items():
            noise = name_noise.get(name, 0)
            ratio = round(noise / total * 100, 2) if total else 0.0
            results.append(
                {
                    "alert_name": name,
                    "total": total,
                    "noise_count": noise,
                    "noise_ratio_pct": ratio,
                }
            )
        results.sort(key=lambda x: x["noise_ratio_pct"], reverse=True)
        return results

    def detect_noise_trends(self) -> dict[str, Any]:
        """Detect whether noise rates are improving or worsening over time."""
        if len(self._records) < 4:
            return {"trend": "insufficient_data", "sample_count": len(self._records)}
        mid = len(self._records) // 2
        first_half = self._records[:mid]
        second_half = self._records[mid:]

        def _ratio(records: list[NoiseRecord]) -> float:
            if not records:
                return 0.0
            noise = sum(1 for r in records if r.signal_strength == SignalStrength.NOISE)
            return round(noise / len(records) * 100, 2)

        first_ratio = _ratio(first_half)
        second_ratio = _ratio(second_half)
        delta = round(second_ratio - first_ratio, 2)
        if delta > 5.0:
            trend = "worsening"
        elif delta < -5.0:
            trend = "improving"
        else:
            trend = "stable"
        return {
            "trend": trend,
            "first_half_noise_pct": first_ratio,
            "second_half_noise_pct": second_ratio,
            "delta_pct": delta,
            "total_records": len(self._records),
        }

    # -- Report --

    def generate_report(self) -> NoiseClassifierReport:
        by_category: dict[str, int] = {}
        by_signal_strength: dict[str, int] = {}
        by_method: dict[str, int] = {}
        for r in self._records:
            by_category[r.category.value] = by_category.get(r.category.value, 0) + 1
            by_signal_strength[r.signal_strength.value] = (
                by_signal_strength.get(r.signal_strength.value, 0) + 1
            )
            by_method[r.method.value] = by_method.get(r.method.value, 0) + 1
        total = len(self._records)
        noise_count = by_signal_strength.get(SignalStrength.NOISE.value, 0)
        strong = by_signal_strength.get(SignalStrength.STRONG.value, 0)
        moderate = by_signal_strength.get(SignalStrength.MODERATE.value, 0)
        signal_count = strong + moderate
        noise_ratio = round(noise_count / total * 100, 2) if total else 0.0
        noisy = self.identify_noisy_alerts()
        top_sources_data = self.analyze_noise_by_source()
        top_sources = [b["source"] for b in top_sources_data.get("breakdown", [])[:5]]
        recs: list[str] = []
        if noise_ratio > self._max_noise_ratio_pct:
            recs.append(
                f"Noise ratio {noise_ratio}% exceeds max {self._max_noise_ratio_pct}%"
                " — review classification rules"
            )
        if noisy:
            recs.append(
                f"High-noise alert: '{noisy[0]['alert_name']}'"
                f" (avg score {noisy[0]['avg_noise_score']}) — consider suppression"
            )
        if not self._rules:
            recs.append("No classification rules configured — add rules to improve accuracy")
        if not recs:
            recs.append("Noise classification is within acceptable thresholds")
        return NoiseClassifierReport(
            total_records=total,
            total_rules=len(self._rules),
            noise_count=noise_count,
            signal_count=signal_count,
            noise_ratio_pct=noise_ratio,
            by_category=by_category,
            by_signal_strength=by_signal_strength,
            by_method=by_method,
            top_noisy_sources=top_sources,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._rules.clear()
        logger.info("noise_classifier.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        category_dist: dict[str, int] = {}
        for r in self._records:
            category_dist[r.category.value] = category_dist.get(r.category.value, 0) + 1
        suppressed = sum(1 for r in self._records if r.suppressed)
        avg_score = (
            round(sum(r.noise_score for r in self._records) / len(self._records), 4)
            if self._records
            else 0.0
        )
        return {
            "total_records": len(self._records),
            "total_rules": len(self._rules),
            "suppressed_count": suppressed,
            "max_noise_ratio_pct": self._max_noise_ratio_pct,
            "avg_noise_score": avg_score,
            "category_distribution": category_dist,
            "unique_sources": len({r.source for r in self._records if r.source}),
        }
