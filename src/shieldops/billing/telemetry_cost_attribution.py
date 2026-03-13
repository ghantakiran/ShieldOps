"""TelemetryCostAttribution — telemetry cost attribution."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class CostDriver(StrEnum):
    INGESTION_VOLUME = "ingestion_volume"
    CARDINALITY = "cardinality"
    QUERY_RATE = "query_rate"
    RETENTION = "retention"


class AttributionMethod(StrEnum):
    PROPORTIONAL = "proportional"
    DIRECT = "direct"
    ACTIVITY_BASED = "activity_based"
    HYBRID = "hybrid"


class CostTrend(StrEnum):
    INCREASING = "increasing"
    STABLE = "stable"
    DECREASING = "decreasing"
    SPIKE = "spike"


# --- Models ---


class TelemetryCostAttributionRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    cost_driver: CostDriver = CostDriver.INGESTION_VOLUME
    attribution_method: AttributionMethod = AttributionMethod.PROPORTIONAL
    cost_trend: CostTrend = CostTrend.STABLE
    score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class TelemetryCostAttributionAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    cost_driver: CostDriver = CostDriver.INGESTION_VOLUME
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class TelemetryCostAttributionReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_score: float = 0.0
    by_cost_driver: dict[str, int] = Field(default_factory=dict)
    by_attribution_method: dict[str, int] = Field(default_factory=dict)
    by_cost_trend: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class TelemetryCostAttribution:
    """Telemetry cost attribution engine."""

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[TelemetryCostAttributionRecord] = []
        self._analyses: list[TelemetryCostAttributionAnalysis] = []
        logger.info(
            "telemetry.cost.attribution.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    def add_record(
        self,
        name: str,
        cost_driver: CostDriver = (CostDriver.INGESTION_VOLUME),
        attribution_method: AttributionMethod = (AttributionMethod.PROPORTIONAL),
        cost_trend: CostTrend = CostTrend.STABLE,
        score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> TelemetryCostAttributionRecord:
        record = TelemetryCostAttributionRecord(
            name=name,
            cost_driver=cost_driver,
            attribution_method=attribution_method,
            cost_trend=cost_trend,
            score=score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "telemetry.cost.attribution.record_added",
            record_id=record.id,
            name=name,
        )
        return record

    def process(self, key: str) -> dict[str, Any]:
        """Find record by id, create analysis."""
        for r in self._records:
            if r.id == key:
                analysis = TelemetryCostAttributionAnalysis(
                    name=r.name,
                    cost_driver=r.cost_driver,
                    analysis_score=r.score,
                    threshold=self._threshold,
                    breached=(r.score < self._threshold),
                    description=(f"Processed {r.name}"),
                )
                self._analyses.append(analysis)
                return {
                    "status": "processed",
                    "analysis_id": analysis.id,
                    "breached": analysis.breached,
                }
        return {"status": "not_found", "key": key}

    # -- domain methods ---

    def attribute_telemetry_costs(
        self,
    ) -> dict[str, Any]:
        """Attribute costs by cost driver."""
        driver_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.cost_driver.value
            driver_data.setdefault(key, []).append(r.score)
        result: dict[str, Any] = {}
        for k, scores in driver_data.items():
            result[k] = {
                "count": len(scores),
                "avg_cost": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_cost_hotspots(
        self,
    ) -> list[dict[str, Any]]:
        """Identify services with high costs."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.score < self._threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "name": r.name,
                        "cost_driver": (r.cost_driver.value),
                        "score": r.score,
                        "service": r.service,
                    }
                )
        return sorted(results, key=lambda x: x["score"])

    def recommend_cost_reduction(
        self,
    ) -> list[dict[str, Any]]:
        """Recommend cost reduction actions."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            avg = round(sum(scores) / len(scores), 2)
            results.append(
                {
                    "service": svc,
                    "avg_cost": avg,
                    "action": ("reduce_cardinality" if avg < self._threshold else "monitor"),
                }
            )
        results.sort(key=lambda x: x["avg_cost"])
        return results

    # -- report / stats ---

    def generate_report(
        self,
    ) -> TelemetryCostAttributionReport:
        by_e1: dict[str, int] = {}
        by_e2: dict[str, int] = {}
        by_e3: dict[str, int] = {}
        for r in self._records:
            v1 = r.cost_driver.value
            by_e1[v1] = by_e1.get(v1, 0) + 1
            v2 = r.attribution_method.value
            by_e2[v2] = by_e2.get(v2, 0) + 1
            v3 = r.cost_trend.value
            by_e3[v3] = by_e3.get(v3, 0) + 1
        gap_count = sum(1 for r in self._records if r.score < self._threshold)
        scores = [r.score for r in self._records]
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} item(s) below threshold ({self._threshold})")
        if self._records and avg < self._threshold:
            recs.append(f"Avg score {avg} below threshold ({self._threshold})")
        if not recs:
            recs.append("Telemetry Cost Attribution is healthy")
        return TelemetryCostAttributionReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_score=avg,
            by_cost_driver=by_e1,
            by_attribution_method=by_e2,
            by_cost_trend=by_e3,
            top_gaps=[r.name for r in self._records if r.score < self._threshold][:5],
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("telemetry.cost.attribution.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        e1_dist: dict[str, int] = {}
        for r in self._records:
            key = r.cost_driver.value
            e1_dist[key] = e1_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "cost_driver_distribution": e1_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
