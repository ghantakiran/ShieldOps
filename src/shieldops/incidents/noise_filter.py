"""Incident Noise Filter — filter noise, false alarms, and noise reduction."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class NoiseCategory(StrEnum):
    FALSE_ALARM = "false_alarm"
    DUPLICATE = "duplicate"
    INFORMATIONAL = "informational"
    TRANSIENT = "transient"
    LEGITIMATE = "legitimate"


class NoiseConfidence(StrEnum):
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    UNCERTAIN = "uncertain"
    UNCLASSIFIED = "unclassified"


class FilterAction(StrEnum):
    SUPPRESS = "suppress"
    MERGE = "merge"
    DOWNGRADE = "downgrade"
    ESCALATE = "escalate"
    PASS_THROUGH = "pass_through"  # noqa: S105


# --- Models ---


class NoiseRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str = ""
    noise_category: NoiseCategory = NoiseCategory.FALSE_ALARM
    confidence: NoiseConfidence = NoiseConfidence.UNCLASSIFIED
    filter_action: FilterAction = FilterAction.PASS_THROUGH
    team: str = ""
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class NoisePattern(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    pattern_name: str = ""
    noise_category: NoiseCategory = NoiseCategory.FALSE_ALARM
    occurrence_count: int = 0
    created_at: float = Field(default_factory=time.time)


class NoiseFilterReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_patterns: int = 0
    false_alarm_rate_pct: float = 0.0
    by_category: dict[str, int] = Field(default_factory=dict)
    by_confidence: dict[str, int] = Field(default_factory=dict)
    by_action: dict[str, int] = Field(default_factory=dict)
    top_noisy_sources: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class IncidentNoiseFilter:
    """Filter incident noise, identify false alarms, track noise reduction."""

    def __init__(
        self,
        max_records: int = 200000,
        max_false_alarm_rate_pct: float = 20.0,
    ) -> None:
        self._max_records = max_records
        self._max_false_alarm_rate_pct = max_false_alarm_rate_pct
        self._records: list[NoiseRecord] = []
        self._patterns: list[NoisePattern] = []
        logger.info(
            "noise_filter.initialized",
            max_records=max_records,
            max_false_alarm_rate_pct=max_false_alarm_rate_pct,
        )

    # -- record / get / list ------------------------------------------------

    def record_noise(
        self,
        incident_id: str,
        noise_category: NoiseCategory = NoiseCategory.FALSE_ALARM,
        confidence: NoiseConfidence = NoiseConfidence.UNCLASSIFIED,
        filter_action: FilterAction = FilterAction.PASS_THROUGH,
        team: str = "",
        details: str = "",
    ) -> NoiseRecord:
        record = NoiseRecord(
            incident_id=incident_id,
            noise_category=noise_category,
            confidence=confidence,
            filter_action=filter_action,
            team=team,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "noise_filter.noise_recorded",
            record_id=record.id,
            incident_id=incident_id,
            noise_category=noise_category.value,
            confidence=confidence.value,
        )
        return record

    def get_noise(self, record_id: str) -> NoiseRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_noise(
        self,
        category: NoiseCategory | None = None,
        confidence: NoiseConfidence | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[NoiseRecord]:
        results = list(self._records)
        if category is not None:
            results = [r for r in results if r.noise_category == category]
        if confidence is not None:
            results = [r for r in results if r.confidence == confidence]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_pattern(
        self,
        pattern_name: str,
        noise_category: NoiseCategory = NoiseCategory.FALSE_ALARM,
        occurrence_count: int = 0,
    ) -> NoisePattern:
        pattern = NoisePattern(
            pattern_name=pattern_name,
            noise_category=noise_category,
            occurrence_count=occurrence_count,
        )
        self._patterns.append(pattern)
        if len(self._patterns) > self._max_records:
            self._patterns = self._patterns[-self._max_records :]
        logger.info(
            "noise_filter.pattern_added",
            pattern_name=pattern_name,
            noise_category=noise_category.value,
            occurrence_count=occurrence_count,
        )
        return pattern

    # -- domain operations --------------------------------------------------

    def analyze_noise_distribution(self) -> dict[str, Any]:
        """Group by category; return count and avg confidence per category."""
        conf_map = {
            NoiseConfidence.HIGH: 5,
            NoiseConfidence.MODERATE: 4,
            NoiseConfidence.LOW: 3,
            NoiseConfidence.UNCERTAIN: 2,
            NoiseConfidence.UNCLASSIFIED: 1,
        }
        cat_data: dict[str, list[int]] = {}
        for r in self._records:
            key = r.noise_category.value
            cat_data.setdefault(key, []).append(conf_map.get(r.confidence, 1))
        result: dict[str, Any] = {}
        for cat, scores in cat_data.items():
            result[cat] = {
                "count": len(scores),
                "avg_confidence": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_false_alarms(self) -> list[dict[str, Any]]:
        """Return records where category == FALSE_ALARM."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.noise_category == NoiseCategory.FALSE_ALARM:
                results.append(
                    {
                        "record_id": r.id,
                        "incident_id": r.incident_id,
                        "confidence": r.confidence.value,
                        "filter_action": r.filter_action.value,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_noise_volume(self) -> list[dict[str, Any]]:
        """Group by team, total records, sort descending."""
        team_counts: dict[str, int] = {}
        for r in self._records:
            team_counts[r.team] = team_counts.get(r.team, 0) + 1
        results: list[dict[str, Any]] = []
        for team, count in team_counts.items():
            results.append(
                {
                    "team": team,
                    "noise_count": count,
                }
            )
        results.sort(key=lambda x: x["noise_count"], reverse=True)
        return results

    def detect_noise_trends(self) -> dict[str, Any]:
        """Split-half on occurrence_count; delta threshold 5.0."""
        if len(self._patterns) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        counts = [p.occurrence_count for p in self._patterns]
        mid = len(counts) // 2
        first_half = counts[:mid]
        second_half = counts[mid:]
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

    def generate_report(self) -> NoiseFilterReport:
        by_category: dict[str, int] = {}
        by_confidence: dict[str, int] = {}
        by_action: dict[str, int] = {}
        for r in self._records:
            by_category[r.noise_category.value] = by_category.get(r.noise_category.value, 0) + 1
            by_confidence[r.confidence.value] = by_confidence.get(r.confidence.value, 0) + 1
            by_action[r.filter_action.value] = by_action.get(r.filter_action.value, 0) + 1
        false_alarm_count = sum(
            1 for r in self._records if r.noise_category == NoiseCategory.FALSE_ALARM
        )
        false_alarm_rate = (
            round(false_alarm_count / len(self._records) * 100, 2) if self._records else 0.0
        )
        rankings = self.rank_by_noise_volume()
        top_noisy = [rk["team"] for rk in rankings[:5]]
        recs: list[str] = []
        if false_alarm_rate > self._max_false_alarm_rate_pct:
            recs.append(
                f"False alarm rate {false_alarm_rate}% exceeds "
                f"threshold ({self._max_false_alarm_rate_pct}%)"
            )
        if false_alarm_count > 0:
            recs.append(f"{false_alarm_count} false alarm(s) detected — review noise filters")
        if not recs:
            recs.append("Noise levels are acceptable")
        return NoiseFilterReport(
            total_records=len(self._records),
            total_patterns=len(self._patterns),
            false_alarm_rate_pct=false_alarm_rate,
            by_category=by_category,
            by_confidence=by_confidence,
            by_action=by_action,
            top_noisy_sources=top_noisy,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._patterns.clear()
        logger.info("noise_filter.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        cat_dist: dict[str, int] = {}
        for r in self._records:
            key = r.noise_category.value
            cat_dist[key] = cat_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_patterns": len(self._patterns),
            "max_false_alarm_rate_pct": self._max_false_alarm_rate_pct,
            "category_distribution": cat_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_incidents": len({r.incident_id for r in self._records}),
        }
