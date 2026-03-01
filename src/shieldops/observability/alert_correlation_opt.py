"""Alert Correlation Optimizer — optimize alert correlations, confidence, and merging."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class CorrelationType(StrEnum):
    TEMPORAL = "temporal"
    CAUSAL = "causal"
    SYMPTOM = "symptom"
    TOPOLOGICAL = "topological"
    STATISTICAL = "statistical"


class CorrelationStrength(StrEnum):
    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"
    TENTATIVE = "tentative"
    NONE = "none"


class OptimizationStatus(StrEnum):
    PENDING = "pending"
    OPTIMIZED = "optimized"
    VALIDATED = "validated"
    REJECTED = "rejected"
    EXPIRED = "expired"


# --- Models ---


class CorrelationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    alert_pair: str = ""
    correlation_type: CorrelationType = CorrelationType.TEMPORAL
    correlation_strength: CorrelationStrength = CorrelationStrength.NONE
    optimization_status: OptimizationStatus = OptimizationStatus.PENDING
    confidence_score: float = 0.0
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class CorrelationRule(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    alert_pattern: str = ""
    correlation_type: CorrelationType = CorrelationType.TEMPORAL
    min_confidence: float = 0.0
    auto_merge: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class CorrelationOptReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_rules: int = 0
    optimized_count: int = 0
    avg_confidence: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_strength: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    weak_correlations: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class AlertCorrelationOptimizer:
    """Optimize alert correlations, identify weak links, track confidence."""

    def __init__(
        self,
        max_records: int = 200000,
        min_correlation_strength: float = 70.0,
    ) -> None:
        self._max_records = max_records
        self._min_correlation_strength = min_correlation_strength
        self._records: list[CorrelationRecord] = []
        self._rules: list[CorrelationRule] = []
        logger.info(
            "alert_correlation_opt.initialized",
            max_records=max_records,
            min_correlation_strength=min_correlation_strength,
        )

    # -- record / get / list ------------------------------------------------

    def record_correlation(
        self,
        alert_pair: str,
        correlation_type: CorrelationType = CorrelationType.TEMPORAL,
        correlation_strength: CorrelationStrength = CorrelationStrength.NONE,
        optimization_status: OptimizationStatus = OptimizationStatus.PENDING,
        confidence_score: float = 0.0,
        team: str = "",
    ) -> CorrelationRecord:
        record = CorrelationRecord(
            alert_pair=alert_pair,
            correlation_type=correlation_type,
            correlation_strength=correlation_strength,
            optimization_status=optimization_status,
            confidence_score=confidence_score,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "alert_correlation_opt.correlation_recorded",
            record_id=record.id,
            alert_pair=alert_pair,
            correlation_type=correlation_type.value,
            correlation_strength=correlation_strength.value,
        )
        return record

    def get_correlation(self, record_id: str) -> CorrelationRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_correlations(
        self,
        correlation_type: CorrelationType | None = None,
        strength: CorrelationStrength | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[CorrelationRecord]:
        results = list(self._records)
        if correlation_type is not None:
            results = [r for r in results if r.correlation_type == correlation_type]
        if strength is not None:
            results = [r for r in results if r.correlation_strength == strength]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_rule(
        self,
        alert_pattern: str,
        correlation_type: CorrelationType = CorrelationType.TEMPORAL,
        min_confidence: float = 0.0,
        auto_merge: bool = False,
        description: str = "",
    ) -> CorrelationRule:
        rule = CorrelationRule(
            alert_pattern=alert_pattern,
            correlation_type=correlation_type,
            min_confidence=min_confidence,
            auto_merge=auto_merge,
            description=description,
        )
        self._rules.append(rule)
        if len(self._rules) > self._max_records:
            self._rules = self._rules[-self._max_records :]
        logger.info(
            "alert_correlation_opt.rule_added",
            alert_pattern=alert_pattern,
            correlation_type=correlation_type.value,
            min_confidence=min_confidence,
        )
        return rule

    # -- domain operations --------------------------------------------------

    def analyze_correlation_patterns(self) -> dict[str, Any]:
        """Group by correlation_type; return count and avg confidence per type."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.correlation_type.value
            type_data.setdefault(key, []).append(r.confidence_score)
        result: dict[str, Any] = {}
        for ctype, scores in type_data.items():
            result[ctype] = {
                "count": len(scores),
                "avg_confidence": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_weak_correlations(self) -> list[dict[str, Any]]:
        """Return records where strength is WEAK, TENTATIVE, or NONE."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.correlation_strength in (
                CorrelationStrength.WEAK,
                CorrelationStrength.TENTATIVE,
                CorrelationStrength.NONE,
            ):
                results.append(
                    {
                        "record_id": r.id,
                        "alert_pair": r.alert_pair,
                        "correlation_type": r.correlation_type.value,
                        "confidence_score": r.confidence_score,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_confidence(self) -> list[dict[str, Any]]:
        """Group by team, avg confidence_score, sort descending."""
        team_scores: dict[str, list[float]] = {}
        for r in self._records:
            team_scores.setdefault(r.team, []).append(r.confidence_score)
        results: list[dict[str, Any]] = []
        for team, scores in team_scores.items():
            results.append(
                {
                    "team": team,
                    "avg_confidence": round(sum(scores) / len(scores), 2),
                    "count": len(scores),
                }
            )
        results.sort(key=lambda x: x["avg_confidence"], reverse=True)
        return results

    def detect_correlation_trends(self) -> dict[str, Any]:
        """Split-half on min_confidence; delta threshold 5.0."""
        if len(self._rules) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        confs = [ru.min_confidence for ru in self._rules]
        mid = len(confs) // 2
        first_half = confs[:mid]
        second_half = confs[mid:]
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

    def generate_report(self) -> CorrelationOptReport:
        by_type: dict[str, int] = {}
        by_strength: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for r in self._records:
            by_type[r.correlation_type.value] = by_type.get(r.correlation_type.value, 0) + 1
            by_strength[r.correlation_strength.value] = (
                by_strength.get(r.correlation_strength.value, 0) + 1
            )
            by_status[r.optimization_status.value] = (
                by_status.get(r.optimization_status.value, 0) + 1
            )
        optimized_count = sum(
            1 for r in self._records if r.optimization_status == OptimizationStatus.OPTIMIZED
        )
        avg_conf = (
            round(sum(r.confidence_score for r in self._records) / len(self._records), 2)
            if self._records
            else 0.0
        )
        weak_items = self.identify_weak_correlations()
        weak_correlations = [w["alert_pair"] for w in weak_items[:5]]
        recs: list[str] = []
        if self._records and avg_conf < self._min_correlation_strength:
            recs.append(
                f"Avg confidence {avg_conf} below threshold ({self._min_correlation_strength})"
            )
        if len(weak_items) > 0:
            recs.append(f"{len(weak_items)} weak correlation(s) detected — review alert rules")
        if not recs:
            recs.append("Correlation quality is within acceptable limits")
        return CorrelationOptReport(
            total_records=len(self._records),
            total_rules=len(self._rules),
            optimized_count=optimized_count,
            avg_confidence=avg_conf,
            by_type=by_type,
            by_strength=by_strength,
            by_status=by_status,
            weak_correlations=weak_correlations,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._rules.clear()
        logger.info("alert_correlation_opt.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.correlation_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_rules": len(self._rules),
            "min_correlation_strength": self._min_correlation_strength,
            "type_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_alert_pairs": len({r.alert_pair for r in self._records}),
        }
