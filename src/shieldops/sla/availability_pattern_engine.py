"""Availability Pattern Engine
compute temporal availability patterns, detect recurring
unavailability, rank time windows by outage risk."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class TimeWindow(StrEnum):
    PEAK_HOURS = "peak_hours"
    OFF_HOURS = "off_hours"
    WEEKEND = "weekend"
    MAINTENANCE = "maintenance"


class AvailabilityTrend(StrEnum):
    IMPROVING = "improving"
    STABLE = "stable"
    DEGRADING = "degrading"
    VOLATILE = "volatile"


class PatternType(StrEnum):
    PERIODIC = "periodic"
    SPORADIC = "sporadic"
    CORRELATED = "correlated"
    RANDOM = "random"


# --- Models ---


class AvailabilityPatternRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_id: str = ""
    time_window: TimeWindow = TimeWindow.PEAK_HOURS
    availability_trend: AvailabilityTrend = AvailabilityTrend.STABLE
    pattern_type: PatternType = PatternType.RANDOM
    availability_pct: float = 99.9
    outage_minutes: float = 0.0
    occurrences: int = 0
    region: str = ""
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class AvailabilityPatternAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_id: str = ""
    pattern_score: float = 0.0
    availability_trend: AvailabilityTrend = AvailabilityTrend.STABLE
    recurring: bool = False
    data_points: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class AvailabilityPatternReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_availability: float = 0.0
    by_time_window: dict[str, int] = Field(default_factory=dict)
    by_trend: dict[str, int] = Field(default_factory=dict)
    by_pattern_type: dict[str, int] = Field(default_factory=dict)
    low_availability_services: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class AvailabilityPatternEngine:
    """Compute temporal availability patterns, detect
    recurring unavailability, rank by outage risk."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[AvailabilityPatternRecord] = []
        self._analyses: dict[str, AvailabilityPatternAnalysis] = {}
        logger.info(
            "availability_pattern_engine.init",
            max_records=max_records,
        )

    def add_record(
        self,
        service_id: str = "",
        time_window: TimeWindow = TimeWindow.PEAK_HOURS,
        availability_trend: AvailabilityTrend = AvailabilityTrend.STABLE,
        pattern_type: PatternType = PatternType.RANDOM,
        availability_pct: float = 99.9,
        outage_minutes: float = 0.0,
        occurrences: int = 0,
        region: str = "",
        description: str = "",
    ) -> AvailabilityPatternRecord:
        record = AvailabilityPatternRecord(
            service_id=service_id,
            time_window=time_window,
            availability_trend=availability_trend,
            pattern_type=pattern_type,
            availability_pct=availability_pct,
            outage_minutes=outage_minutes,
            occurrences=occurrences,
            region=region,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "availability_pattern_engine.record_added",
            record_id=record.id,
            service_id=service_id,
        )
        return record

    def process(self, key: str) -> AvailabilityPatternAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        points = sum(1 for r in self._records if r.service_id == rec.service_id)
        pattern_score = round(rec.outage_minutes * rec.occurrences, 2)
        recurring = rec.pattern_type in (PatternType.PERIODIC, PatternType.CORRELATED)
        analysis = AvailabilityPatternAnalysis(
            service_id=rec.service_id,
            pattern_score=pattern_score,
            availability_trend=rec.availability_trend,
            recurring=recurring,
            data_points=points,
            description=f"Service {rec.service_id} availability {rec.availability_pct}%",
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> AvailabilityPatternReport:
        by_tw: dict[str, int] = {}
        by_t: dict[str, int] = {}
        by_pt: dict[str, int] = {}
        avails: list[float] = []
        for r in self._records:
            k = r.time_window.value
            by_tw[k] = by_tw.get(k, 0) + 1
            k2 = r.availability_trend.value
            by_t[k2] = by_t.get(k2, 0) + 1
            k3 = r.pattern_type.value
            by_pt[k3] = by_pt.get(k3, 0) + 1
            avails.append(r.availability_pct)
        avg = round(sum(avails) / len(avails), 2) if avails else 0.0
        low = list({r.service_id for r in self._records if r.availability_pct < 99.0})[:10]
        recs: list[str] = []
        if low:
            recs.append(f"{len(low)} services with low availability")
        if not recs:
            recs.append("All services meeting availability targets")
        return AvailabilityPatternReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_availability=avg,
            by_time_window=by_tw,
            by_trend=by_t,
            by_pattern_type=by_pt,
            low_availability_services=low,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        tw_dist: dict[str, int] = {}
        for r in self._records:
            k = r.time_window.value
            tw_dist[k] = tw_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "time_window_distribution": tw_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("availability_pattern_engine.cleared")
        return {"status": "cleared"}

    # -- domain methods ---

    def compute_temporal_availability_patterns(
        self,
    ) -> list[dict[str, Any]]:
        """Compute temporal availability patterns per service."""
        svc_data: dict[str, list[float]] = {}
        svc_outages: dict[str, float] = {}
        for r in self._records:
            svc_data.setdefault(r.service_id, []).append(r.availability_pct)
            svc_outages[r.service_id] = svc_outages.get(r.service_id, 0.0) + r.outage_minutes
        results: list[dict[str, Any]] = []
        for sid, avails in svc_data.items():
            avg = round(sum(avails) / len(avails), 2)
            results.append(
                {
                    "service_id": sid,
                    "avg_availability_pct": avg,
                    "total_outage_minutes": round(svc_outages[sid], 2),
                    "data_points": len(avails),
                }
            )
        results.sort(key=lambda x: x["avg_availability_pct"])
        return results

    def detect_recurring_unavailability(
        self,
    ) -> list[dict[str, Any]]:
        """Detect services with recurring unavailability."""
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for r in self._records:
            if (
                r.pattern_type in (PatternType.PERIODIC, PatternType.CORRELATED)
                and r.service_id not in seen
            ):
                seen.add(r.service_id)
                results.append(
                    {
                        "service_id": r.service_id,
                        "pattern_type": r.pattern_type.value,
                        "time_window": r.time_window.value,
                        "outage_minutes": r.outage_minutes,
                        "occurrences": r.occurrences,
                    }
                )
        results.sort(key=lambda x: x["outage_minutes"], reverse=True)
        return results

    def rank_time_windows_by_outage_risk(
        self,
    ) -> list[dict[str, Any]]:
        """Rank time windows by outage risk."""
        tw_data: dict[str, float] = {}
        tw_counts: dict[str, int] = {}
        for r in self._records:
            tw = r.time_window.value
            tw_data[tw] = tw_data.get(tw, 0.0) + r.outage_minutes
            tw_counts[tw] = tw_counts.get(tw, 0) + 1
        results: list[dict[str, Any]] = []
        for tw, total in tw_data.items():
            results.append(
                {
                    "time_window": tw,
                    "total_outage_minutes": round(total, 2),
                    "record_count": tw_counts[tw],
                    "rank": 0,
                }
            )
        results.sort(key=lambda x: x["total_outage_minutes"], reverse=True)
        for i, entry in enumerate(results, 1):
            entry["rank"] = i
        return results
