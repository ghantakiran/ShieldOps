"""Change Correlation Engine — correlate changes with incidents."""

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
    CAUSAL = "causal"
    TEMPORAL = "temporal"
    SPATIAL = "spatial"
    BEHAVIORAL = "behavioral"
    COINCIDENTAL = "coincidental"


class CorrelationStrength(StrEnum):
    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"
    NEGLIGIBLE = "negligible"
    UNKNOWN = "unknown"


class ChangeOutcome(StrEnum):
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILURE = "failure"
    ROLLBACK = "rollback"
    PENDING = "pending"


# --- Models ---


class CorrelationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    change_id: str = ""
    incident_id: str = ""
    correlation_type: CorrelationType = CorrelationType.CAUSAL
    strength: CorrelationStrength = CorrelationStrength.UNKNOWN
    outcome: ChangeOutcome = ChangeOutcome.PENDING
    team: str = ""
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class CorrelationPattern(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    pattern_name: str = ""
    correlation_type: CorrelationType = CorrelationType.CAUSAL
    occurrence_count: int = 0
    avg_strength_score: float = 0.0
    created_at: float = Field(default_factory=time.time)


class ChangeCorrelationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_patterns: int = 0
    strong_correlations: int = 0
    causal_pct: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_strength: dict[str, int] = Field(default_factory=dict)
    by_outcome: dict[str, int] = Field(default_factory=dict)
    high_risk_changes: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class ChangeCorrelationEngine:
    """Correlate changes with incidents and identify high-risk combinations."""

    def __init__(
        self,
        max_records: int = 200000,
        min_correlation_strength_pct: float = 60.0,
    ) -> None:
        self._max_records = max_records
        self._min_correlation_strength_pct = min_correlation_strength_pct
        self._records: list[CorrelationRecord] = []
        self._patterns: list[CorrelationPattern] = []
        logger.info(
            "change_correlator.initialized",
            max_records=max_records,
            min_correlation_strength_pct=min_correlation_strength_pct,
        )

    # -- record / get / list ------------------------------------------------

    def record_correlation(
        self,
        change_id: str,
        incident_id: str = "",
        correlation_type: CorrelationType = CorrelationType.CAUSAL,
        strength: CorrelationStrength = CorrelationStrength.UNKNOWN,
        outcome: ChangeOutcome = ChangeOutcome.PENDING,
        team: str = "",
        details: str = "",
    ) -> CorrelationRecord:
        record = CorrelationRecord(
            change_id=change_id,
            incident_id=incident_id,
            correlation_type=correlation_type,
            strength=strength,
            outcome=outcome,
            team=team,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "change_correlator.correlation_recorded",
            record_id=record.id,
            change_id=change_id,
            correlation_type=correlation_type.value,
            strength=strength.value,
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
            results = [r for r in results if r.strength == strength]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_pattern(
        self,
        pattern_name: str,
        correlation_type: CorrelationType = CorrelationType.CAUSAL,
        occurrence_count: int = 0,
        avg_strength_score: float = 0.0,
    ) -> CorrelationPattern:
        pattern = CorrelationPattern(
            pattern_name=pattern_name,
            correlation_type=correlation_type,
            occurrence_count=occurrence_count,
            avg_strength_score=avg_strength_score,
        )
        self._patterns.append(pattern)
        if len(self._patterns) > self._max_records:
            self._patterns = self._patterns[-self._max_records :]
        logger.info(
            "change_correlator.pattern_added",
            pattern_name=pattern_name,
            correlation_type=correlation_type.value,
            occurrence_count=occurrence_count,
        )
        return pattern

    # -- domain operations --------------------------------------------------

    def analyze_correlation_distribution(self) -> dict[str, Any]:
        """Group by correlation type; return count and avg strength."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.correlation_type.value
            score = (
                1.0
                if r.strength == CorrelationStrength.STRONG
                else 0.75
                if r.strength == CorrelationStrength.MODERATE
                else 0.5
                if r.strength == CorrelationStrength.WEAK
                else 0.25
                if r.strength == CorrelationStrength.NEGLIGIBLE
                else 0.0
            )
            type_data.setdefault(key, []).append(score)
        result: dict[str, Any] = {}
        for ctype, scores in type_data.items():
            result[ctype] = {
                "count": len(scores),
                "avg_strength": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_strong_correlations(self) -> list[dict[str, Any]]:
        """Return correlations where strength is STRONG."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.strength == CorrelationStrength.STRONG:
                results.append(
                    {
                        "record_id": r.id,
                        "change_id": r.change_id,
                        "incident_id": r.incident_id,
                        "correlation_type": r.correlation_type.value,
                        "outcome": r.outcome.value,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_incident_impact(self) -> list[dict[str, Any]]:
        """Group by change_id, count incidents, sort descending."""
        change_incidents: dict[str, set[str]] = {}
        for r in self._records:
            change_incidents.setdefault(r.change_id, set()).add(r.incident_id)
        results: list[dict[str, Any]] = []
        for change_id, incidents in change_incidents.items():
            results.append(
                {
                    "change_id": change_id,
                    "incident_count": len(incidents),
                }
            )
        results.sort(key=lambda x: x["incident_count"], reverse=True)
        return results

    def detect_correlation_trends(self) -> dict[str, Any]:
        """Split-half comparison on strength scores; delta 0.1."""
        if len(self._records) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}

        def _score(r: CorrelationRecord) -> float:
            if r.strength == CorrelationStrength.STRONG:
                return 1.0
            if r.strength == CorrelationStrength.MODERATE:
                return 0.75
            if r.strength == CorrelationStrength.WEAK:
                return 0.5
            if r.strength == CorrelationStrength.NEGLIGIBLE:
                return 0.25
            return 0.0

        scores = [_score(r) for r in self._records]
        mid = len(scores) // 2
        first_half = scores[:mid]
        second_half = scores[mid:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        delta = round(avg_second - avg_first, 2)
        if abs(delta) < 0.1:
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

    def generate_report(self) -> ChangeCorrelationReport:
        by_type: dict[str, int] = {}
        by_strength: dict[str, int] = {}
        by_outcome: dict[str, int] = {}
        for r in self._records:
            by_type[r.correlation_type.value] = by_type.get(r.correlation_type.value, 0) + 1
            by_strength[r.strength.value] = by_strength.get(r.strength.value, 0) + 1
            by_outcome[r.outcome.value] = by_outcome.get(r.outcome.value, 0) + 1
        strong_correlations = sum(
            1 for r in self._records if r.strength == CorrelationStrength.STRONG
        )
        causal_count = sum(1 for r in self._records if r.correlation_type == CorrelationType.CAUSAL)
        causal_pct = round(causal_count / len(self._records) * 100, 2) if self._records else 0.0
        strong_list = self.identify_strong_correlations()
        high_risk_changes = [s["change_id"] for s in strong_list]
        recs: list[str] = []
        if strong_correlations > 0:
            recs.append(
                f"{strong_correlations} strong correlation(s) detected — review high-risk changes"
            )
        low_str = sum(
            1
            for r in self._records
            if r.strength
            in {
                CorrelationStrength.NEGLIGIBLE,
                CorrelationStrength.UNKNOWN,
            }
        )
        if low_str > 0:
            recs.append(
                f"{low_str} correlation(s) with negligible/unknown strength — investigate further"
            )
        if not recs:
            recs.append("Correlation levels are acceptable")
        return ChangeCorrelationReport(
            total_records=len(self._records),
            total_patterns=len(self._patterns),
            strong_correlations=strong_correlations,
            causal_pct=causal_pct,
            by_type=by_type,
            by_strength=by_strength,
            by_outcome=by_outcome,
            high_risk_changes=high_risk_changes,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._patterns.clear()
        logger.info("change_correlator.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.correlation_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_patterns": len(self._patterns),
            "min_correlation_strength_pct": (self._min_correlation_strength_pct),
            "type_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_changes": len({r.change_id for r in self._records}),
        }
