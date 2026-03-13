"""Event Sourcing Pattern Engine —
analyze event store growth, detect projection lag,
rank aggregates by complexity."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class EventType(StrEnum):
    DOMAIN = "domain"
    INTEGRATION = "integration"
    SYSTEM = "system"
    SNAPSHOT = "snapshot"


class ProjectionStatus(StrEnum):
    CURRENT = "current"
    LAGGING = "lagging"
    STALE = "stale"
    REBUILDING = "rebuilding"


class StoreGrowth(StrEnum):
    RAPID = "rapid"
    STEADY = "steady"
    SLOW = "slow"
    STABLE = "stable"


# --- Models ---


class EventSourcingRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    aggregate_id: str = ""
    event_type: EventType = EventType.DOMAIN
    projection_status: ProjectionStatus = ProjectionStatus.CURRENT
    store_growth: StoreGrowth = StoreGrowth.STEADY
    event_count: int = 0
    projection_lag_ms: float = 0.0
    store_size_mb: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class EventSourcingAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    aggregate_id: str = ""
    event_type: EventType = EventType.DOMAIN
    growth_rate: float = 0.0
    lag_severity: float = 0.0
    complexity_score: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class EventSourcingReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_event_count: float = 0.0
    by_event_type: dict[str, int] = Field(default_factory=dict)
    by_projection_status: dict[str, int] = Field(default_factory=dict)
    by_store_growth: dict[str, int] = Field(default_factory=dict)
    lagging_aggregates: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class EventSourcingPatternEngine:
    """Analyze event store growth, detect projection
    lag, rank aggregates by complexity."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[EventSourcingRecord] = []
        self._analyses: dict[str, EventSourcingAnalysis] = {}
        logger.info(
            "event_sourcing_pattern_engine.init",
            max_records=max_records,
        )

    def add_record(
        self,
        aggregate_id: str = "",
        event_type: EventType = EventType.DOMAIN,
        projection_status: ProjectionStatus = (ProjectionStatus.CURRENT),
        store_growth: StoreGrowth = StoreGrowth.STEADY,
        event_count: int = 0,
        projection_lag_ms: float = 0.0,
        store_size_mb: float = 0.0,
        description: str = "",
    ) -> EventSourcingRecord:
        record = EventSourcingRecord(
            aggregate_id=aggregate_id,
            event_type=event_type,
            projection_status=projection_status,
            store_growth=store_growth,
            event_count=event_count,
            projection_lag_ms=projection_lag_ms,
            store_size_mb=store_size_mb,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "event_sourcing.record_added",
            record_id=record.id,
            aggregate_id=aggregate_id,
        )
        return record

    def process(self, key: str) -> EventSourcingAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        growth_rate = round(
            rec.store_size_mb / max(rec.event_count, 1),
            4,
        )
        lag_sev = round(rec.projection_lag_ms / 1000, 2)
        complexity = round(
            rec.event_count * 0.1 + rec.store_size_mb * 0.5,
            2,
        )
        analysis = EventSourcingAnalysis(
            aggregate_id=rec.aggregate_id,
            event_type=rec.event_type,
            growth_rate=growth_rate,
            lag_severity=lag_sev,
            complexity_score=complexity,
            description=(f"Aggregate {rec.aggregate_id} complexity {complexity}"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> EventSourcingReport:
        by_et: dict[str, int] = {}
        by_ps: dict[str, int] = {}
        by_sg: dict[str, int] = {}
        counts: list[int] = []
        for r in self._records:
            k = r.event_type.value
            by_et[k] = by_et.get(k, 0) + 1
            k2 = r.projection_status.value
            by_ps[k2] = by_ps.get(k2, 0) + 1
            k3 = r.store_growth.value
            by_sg[k3] = by_sg.get(k3, 0) + 1
            counts.append(r.event_count)
        avg = round(sum(counts) / len(counts), 2) if counts else 0.0
        lagging = list(
            {
                r.aggregate_id
                for r in self._records
                if r.projection_status
                in (
                    ProjectionStatus.LAGGING,
                    ProjectionStatus.STALE,
                )
            }
        )[:10]
        recs: list[str] = []
        if lagging:
            recs.append(f"{len(lagging)} lagging aggregates")
        if not recs:
            recs.append("All projections current")
        return EventSourcingReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_event_count=avg,
            by_event_type=by_et,
            by_projection_status=by_ps,
            by_store_growth=by_sg,
            lagging_aggregates=lagging,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        et_dist: dict[str, int] = {}
        for r in self._records:
            k = r.event_type.value
            et_dist[k] = et_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "event_type_distribution": et_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("event_sourcing_pattern_engine.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def analyze_event_store_growth(
        self,
    ) -> list[dict[str, Any]]:
        """Analyze event store growth per aggregate."""
        agg_data: dict[str, list[float]] = {}
        agg_counts: dict[str, int] = {}
        for r in self._records:
            agg_data.setdefault(r.aggregate_id, []).append(r.store_size_mb)
            agg_counts[r.aggregate_id] = agg_counts.get(r.aggregate_id, 0) + r.event_count
        results: list[dict[str, Any]] = []
        for aid, sizes in agg_data.items():
            total = round(sum(sizes), 2)
            results.append(
                {
                    "aggregate_id": aid,
                    "total_size_mb": total,
                    "event_count": agg_counts[aid],
                    "avg_size_mb": round(total / len(sizes), 2),
                    "samples": len(sizes),
                }
            )
        results.sort(
            key=lambda x: x["total_size_mb"],
            reverse=True,
        )
        return results

    def detect_projection_lag(
        self,
    ) -> list[dict[str, Any]]:
        """Detect aggregates with projection lag."""
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for r in self._records:
            if (
                r.projection_status
                in (
                    ProjectionStatus.LAGGING,
                    ProjectionStatus.STALE,
                )
                and r.aggregate_id not in seen
            ):
                seen.add(r.aggregate_id)
                results.append(
                    {
                        "aggregate_id": (r.aggregate_id),
                        "status": (r.projection_status.value),
                        "lag_ms": r.projection_lag_ms,
                        "event_count": r.event_count,
                    }
                )
        results.sort(
            key=lambda x: x["lag_ms"],
            reverse=True,
        )
        return results

    def rank_aggregates_by_complexity(
        self,
    ) -> list[dict[str, Any]]:
        """Rank aggregates by complexity score."""
        agg_complex: dict[str, float] = {}
        for r in self._records:
            score = r.event_count * 0.1 + r.store_size_mb * 0.5
            agg_complex[r.aggregate_id] = agg_complex.get(r.aggregate_id, 0.0) + score
        results: list[dict[str, Any]] = []
        for aid, score in agg_complex.items():
            results.append(
                {
                    "aggregate_id": aid,
                    "complexity_score": round(score, 2),
                    "rank": 0,
                }
            )
        results.sort(
            key=lambda x: x["complexity_score"],
            reverse=True,
        )
        for i, entry in enumerate(results, 1):
            entry["rank"] = i
        return results
