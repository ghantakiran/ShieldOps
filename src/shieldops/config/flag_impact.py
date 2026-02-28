"""Feature Flag Impact Analyzer — flag impact on reliability."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class FlagCategory(StrEnum):
    RELEASE = "release"
    EXPERIMENT = "experiment"
    OPERATIONAL = "operational"
    PERMISSION = "permission"
    KILL_SWITCH = "kill_switch"


class ImpactLevel(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    NONE_DETECTED = "none_detected"


class ImpactType(StrEnum):
    LATENCY_INCREASE = "latency_increase"
    ERROR_RATE = "error_rate"
    RELIABILITY_DROP = "reliability_drop"
    PERFORMANCE_GAIN = "performance_gain"
    NEUTRAL = "neutral"


# --- Models ---


class FlagImpactRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    flag_category: FlagCategory = FlagCategory.RELEASE
    impact_level: ImpactLevel = ImpactLevel.NONE_DETECTED
    reliability_delta_pct: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class FlagAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    analysis_name: str = ""
    flag_category: FlagCategory = FlagCategory.RELEASE
    impact_type: ImpactType = ImpactType.NEUTRAL
    score: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class FlagImpactReport(BaseModel):
    total_records: int = 0
    total_analyses: int = 0
    avg_reliability_delta_pct: float = 0.0
    by_category: dict[str, int] = Field(default_factory=dict)
    by_impact_level: dict[str, int] = Field(default_factory=dict)
    critical_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class FeatureFlagImpactAnalyzer:
    """Analyze the impact of feature flags on service reliability and performance."""

    def __init__(
        self,
        max_records: int = 200000,
        min_reliability_pct: float = 95.0,
    ) -> None:
        self._max_records = max_records
        self._min_reliability_pct = min_reliability_pct
        self._records: list[FlagImpactRecord] = []
        self._analyses: list[FlagAnalysis] = []
        logger.info(
            "flag_impact.initialized",
            max_records=max_records,
            min_reliability_pct=min_reliability_pct,
        )

    # -- record / get / list ---------------------------------------------

    def record_impact(
        self,
        service_name: str,
        flag_category: FlagCategory = FlagCategory.RELEASE,
        impact_level: ImpactLevel = ImpactLevel.NONE_DETECTED,
        reliability_delta_pct: float = 0.0,
        details: str = "",
    ) -> FlagImpactRecord:
        record = FlagImpactRecord(
            service_name=service_name,
            flag_category=flag_category,
            impact_level=impact_level,
            reliability_delta_pct=reliability_delta_pct,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "flag_impact.impact_recorded",
            record_id=record.id,
            service_name=service_name,
            impact_level=impact_level.value,
        )
        return record

    def get_impact(self, record_id: str) -> FlagImpactRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_impacts(
        self,
        service_name: str | None = None,
        flag_category: FlagCategory | None = None,
        limit: int = 50,
    ) -> list[FlagImpactRecord]:
        results = list(self._records)
        if service_name is not None:
            results = [r for r in results if r.service_name == service_name]
        if flag_category is not None:
            results = [r for r in results if r.flag_category == flag_category]
        return results[-limit:]

    def add_analysis(
        self,
        analysis_name: str,
        flag_category: FlagCategory = FlagCategory.RELEASE,
        impact_type: ImpactType = ImpactType.NEUTRAL,
        score: float = 0.0,
        description: str = "",
    ) -> FlagAnalysis:
        analysis = FlagAnalysis(
            analysis_name=analysis_name,
            flag_category=flag_category,
            impact_type=impact_type,
            score=score,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "flag_impact.analysis_added",
            analysis_name=analysis_name,
            impact_type=impact_type.value,
        )
        return analysis

    # -- domain operations -----------------------------------------------

    def analyze_flag_impact(self, service_name: str) -> dict[str, Any]:
        """Analyze average reliability delta for a service and check threshold."""
        svc_records = [r for r in self._records if r.service_name == service_name]
        if not svc_records:
            return {"service_name": service_name, "status": "no_data"}
        avg_delta = round(
            sum(r.reliability_delta_pct for r in svc_records) / len(svc_records),
            2,
        )
        meets_threshold = avg_delta >= self._min_reliability_pct
        return {
            "service_name": service_name,
            "avg_reliability_delta_pct": avg_delta,
            "record_count": len(svc_records),
            "meets_threshold": meets_threshold,
            "min_reliability_pct": self._min_reliability_pct,
        }

    def identify_critical_flags(self) -> list[dict[str, Any]]:
        """Find services with more than one CRITICAL or HIGH impact."""
        svc_counts: dict[str, int] = {}
        for r in self._records:
            if r.impact_level in (ImpactLevel.CRITICAL, ImpactLevel.HIGH):
                svc_counts[r.service_name] = svc_counts.get(r.service_name, 0) + 1
        results: list[dict[str, Any]] = []
        for svc, count in svc_counts.items():
            if count > 1:
                results.append({"service_name": svc, "critical_high_count": count})
        results.sort(key=lambda x: x["critical_high_count"], reverse=True)
        return results

    def rank_by_reliability_delta(self) -> list[dict[str, Any]]:
        """Rank services by average reliability delta descending."""
        svc_deltas: dict[str, list[float]] = {}
        for r in self._records:
            svc_deltas.setdefault(r.service_name, []).append(r.reliability_delta_pct)
        results: list[dict[str, Any]] = []
        for svc, deltas in svc_deltas.items():
            avg = round(sum(deltas) / len(deltas), 2)
            results.append(
                {
                    "service_name": svc,
                    "avg_reliability_delta_pct": avg,
                    "record_count": len(deltas),
                }
            )
        results.sort(key=lambda x: x["avg_reliability_delta_pct"], reverse=True)
        return results

    def detect_impact_trends(self) -> list[dict[str, Any]]:
        """Detect services with more than 3 impact records."""
        svc_counts: dict[str, int] = {}
        for r in self._records:
            svc_counts[r.service_name] = svc_counts.get(r.service_name, 0) + 1
        results: list[dict[str, Any]] = []
        for svc, count in svc_counts.items():
            if count > 3:
                results.append({"service_name": svc, "record_count": count})
        results.sort(key=lambda x: x["record_count"], reverse=True)
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> FlagImpactReport:
        by_category: dict[str, int] = {}
        by_impact_level: dict[str, int] = {}
        for r in self._records:
            by_category[r.flag_category.value] = by_category.get(r.flag_category.value, 0) + 1
            by_impact_level[r.impact_level.value] = by_impact_level.get(r.impact_level.value, 0) + 1
        avg_delta = (
            round(
                sum(r.reliability_delta_pct for r in self._records) / len(self._records),
                2,
            )
            if self._records
            else 0.0
        )
        critical_count = sum(1 for r in self._records if r.impact_level == ImpactLevel.CRITICAL)
        recs: list[str] = []
        if critical_count > 0:
            recs.append(f"{critical_count} flag(s) with critical impact detected")
        high_count = sum(1 for r in self._records if r.impact_level == ImpactLevel.HIGH)
        if high_count > 0:
            recs.append(f"{high_count} flag(s) with high impact detected")
        if not recs:
            recs.append("Feature flag impact levels are healthy")
        return FlagImpactReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_reliability_delta_pct=avg_delta,
            by_category=by_category,
            by_impact_level=by_impact_level,
            critical_count=critical_count,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("flag_impact.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        category_dist: dict[str, int] = {}
        for r in self._records:
            key = r.flag_category.value
            category_dist[key] = category_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "min_reliability_pct": self._min_reliability_pct,
            "category_distribution": category_dist,
            "unique_services": len({r.service_name for r in self._records}),
        }
