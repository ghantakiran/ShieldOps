"""Alert Noise Profiler — profile alert noise patterns, track signal-to-noise ratio."""

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
    FALSE_POSITIVE = "false_positive"
    DUPLICATE = "duplicate"
    TRANSIENT = "transient"
    STALE = "stale"
    ACTIONABLE = "actionable"


class NoiseSource(StrEnum):
    THRESHOLD_MISCONFIGURED = "threshold_misconfigured"
    FLAPPING_METRIC = "flapping_metric"
    DEPENDENCY_CASCADE = "dependency_cascade"
    MONITORING_GAP = "monitoring_gap"
    LEGITIMATE = "legitimate"


class NoiseImpact(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    NEGLIGIBLE = "negligible"


# --- Models ---


class NoiseProfileRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    profile_id: str = ""
    noise_category: NoiseCategory = NoiseCategory.ACTIONABLE
    noise_source: NoiseSource = NoiseSource.LEGITIMATE
    noise_impact: NoiseImpact = NoiseImpact.NEGLIGIBLE
    noise_ratio: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class NoiseAssessment(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    profile_id: str = ""
    noise_category: NoiseCategory = NoiseCategory.ACTIONABLE
    assessment_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class AlertNoiseReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_assessments: int = 0
    high_noise_count: int = 0
    avg_noise_ratio: float = 0.0
    by_category: dict[str, int] = Field(default_factory=dict)
    by_source: dict[str, int] = Field(default_factory=dict)
    by_impact: dict[str, int] = Field(default_factory=dict)
    top_noisy_rules: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class AlertNoiseProfiler:
    """Profile alert noise patterns, identify noisy alert rules."""

    def __init__(
        self,
        max_records: int = 200000,
        max_noise_ratio: float = 30.0,
    ) -> None:
        self._max_records = max_records
        self._max_noise_ratio = max_noise_ratio
        self._records: list[NoiseProfileRecord] = []
        self._assessments: list[NoiseAssessment] = []
        logger.info(
            "alert_noise_profiler.initialized",
            max_records=max_records,
            max_noise_ratio=max_noise_ratio,
        )

    # -- record / get / list ------------------------------------------------

    def record_profile(
        self,
        profile_id: str,
        noise_category: NoiseCategory = NoiseCategory.ACTIONABLE,
        noise_source: NoiseSource = NoiseSource.LEGITIMATE,
        noise_impact: NoiseImpact = NoiseImpact.NEGLIGIBLE,
        noise_ratio: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> NoiseProfileRecord:
        record = NoiseProfileRecord(
            profile_id=profile_id,
            noise_category=noise_category,
            noise_source=noise_source,
            noise_impact=noise_impact,
            noise_ratio=noise_ratio,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "alert_noise_profiler.profile_recorded",
            record_id=record.id,
            profile_id=profile_id,
            noise_category=noise_category.value,
            noise_source=noise_source.value,
        )
        return record

    def get_profile(self, record_id: str) -> NoiseProfileRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_profiles(
        self,
        noise_category: NoiseCategory | None = None,
        noise_source: NoiseSource | None = None,
        service: str | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[NoiseProfileRecord]:
        results = list(self._records)
        if noise_category is not None:
            results = [r for r in results if r.noise_category == noise_category]
        if noise_source is not None:
            results = [r for r in results if r.noise_source == noise_source]
        if service is not None:
            results = [r for r in results if r.service == service]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_assessment(
        self,
        profile_id: str,
        noise_category: NoiseCategory = NoiseCategory.ACTIONABLE,
        assessment_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> NoiseAssessment:
        assessment = NoiseAssessment(
            profile_id=profile_id,
            noise_category=noise_category,
            assessment_score=assessment_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._assessments.append(assessment)
        if len(self._assessments) > self._max_records:
            self._assessments = self._assessments[-self._max_records :]
        logger.info(
            "alert_noise_profiler.assessment_added",
            profile_id=profile_id,
            noise_category=noise_category.value,
            assessment_score=assessment_score,
        )
        return assessment

    # -- domain operations --------------------------------------------------

    def analyze_noise_distribution(self) -> dict[str, Any]:
        """Group by noise_category; return count and avg noise_ratio."""
        cat_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.noise_category.value
            cat_data.setdefault(key, []).append(r.noise_ratio)
        result: dict[str, Any] = {}
        for cat, ratios in cat_data.items():
            result[cat] = {
                "count": len(ratios),
                "avg_noise_ratio": round(sum(ratios) / len(ratios), 2),
            }
        return result

    def identify_high_noise(self) -> list[dict[str, Any]]:
        """Return records where noise_ratio > max_noise_ratio."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.noise_ratio > self._max_noise_ratio:
                results.append(
                    {
                        "record_id": r.id,
                        "profile_id": r.profile_id,
                        "noise_category": r.noise_category.value,
                        "noise_ratio": r.noise_ratio,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_noise_ratio(self) -> list[dict[str, Any]]:
        """Group by service, avg noise_ratio, sort descending."""
        svc_ratios: dict[str, list[float]] = {}
        for r in self._records:
            svc_ratios.setdefault(r.service, []).append(r.noise_ratio)
        results: list[dict[str, Any]] = []
        for svc, ratios in svc_ratios.items():
            results.append(
                {
                    "service": svc,
                    "avg_noise_ratio": round(sum(ratios) / len(ratios), 2),
                }
            )
        results.sort(key=lambda x: x["avg_noise_ratio"], reverse=True)
        return results

    def detect_noise_trends(self) -> dict[str, Any]:
        """Split-half comparison on assessment_score; delta threshold 5.0."""
        if len(self._assessments) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [a.assessment_score for a in self._assessments]
        mid = len(vals) // 2
        first_half = vals[:mid]
        second_half = vals[mid:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        delta = round(avg_second - avg_first, 2)
        if abs(delta) < 5.0:
            trend = "stable"
        elif delta > 0:
            trend = "growing"
        else:
            trend = "shrinking"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> AlertNoiseReport:
        by_category: dict[str, int] = {}
        by_source: dict[str, int] = {}
        by_impact: dict[str, int] = {}
        for r in self._records:
            by_category[r.noise_category.value] = by_category.get(r.noise_category.value, 0) + 1
            by_source[r.noise_source.value] = by_source.get(r.noise_source.value, 0) + 1
            by_impact[r.noise_impact.value] = by_impact.get(r.noise_impact.value, 0) + 1
        high_noise_count = sum(1 for r in self._records if r.noise_ratio > self._max_noise_ratio)
        ratios = [r.noise_ratio for r in self._records]
        avg_noise_ratio = round(sum(ratios) / len(ratios), 2) if ratios else 0.0
        noisy_list = self.identify_high_noise()
        top_noisy_rules = [o["profile_id"] for o in noisy_list[:5]]
        recs: list[str] = []
        if self._records and avg_noise_ratio > self._max_noise_ratio:
            recs.append(
                f"Avg noise ratio {avg_noise_ratio}% exceeds threshold ({self._max_noise_ratio}%)"
            )
        if high_noise_count > 0:
            recs.append(f"{high_noise_count} high-noise rule(s) — tune alert thresholds")
        if not recs:
            recs.append("Alert noise levels are healthy")
        return AlertNoiseReport(
            total_records=len(self._records),
            total_assessments=len(self._assessments),
            high_noise_count=high_noise_count,
            avg_noise_ratio=avg_noise_ratio,
            by_category=by_category,
            by_source=by_source,
            by_impact=by_impact,
            top_noisy_rules=top_noisy_rules,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._assessments.clear()
        logger.info("alert_noise_profiler.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        cat_dist: dict[str, int] = {}
        for r in self._records:
            key = r.noise_category.value
            cat_dist[key] = cat_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_assessments": len(self._assessments),
            "max_noise_ratio": self._max_noise_ratio,
            "noise_category_distribution": cat_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
