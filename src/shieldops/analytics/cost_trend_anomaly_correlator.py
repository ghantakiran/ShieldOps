"""Cost Trend Anomaly Correlator
correlate cost with deployments, attribute trends
to business events, forecast continuation."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class TrendDirection(StrEnum):
    INCREASING = "increasing"
    STABLE = "stable"
    DECREASING = "decreasing"
    VOLATILE = "volatile"


class CorrelationType(StrEnum):
    DEPLOYMENT = "deployment"
    TRAFFIC = "traffic"
    SEASONAL = "seasonal"
    CONFIG = "config"


class ForecastConfidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNCERTAIN = "uncertain"


# --- Models ---


class CostTrendRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    trend_direction: TrendDirection = TrendDirection.STABLE
    correlation_type: CorrelationType = CorrelationType.DEPLOYMENT
    forecast_confidence: ForecastConfidence = ForecastConfidence.MEDIUM
    current_cost: float = 0.0
    previous_cost: float = 0.0
    event_id: str = ""
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class CostTrendAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    trend_direction: TrendDirection = TrendDirection.STABLE
    change_pct: float = 0.0
    correlation_strength: float = 0.0
    forecast_confidence: ForecastConfidence = ForecastConfidence.MEDIUM
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class CostTrendReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_change_pct: float = 0.0
    by_trend_direction: dict[str, int] = Field(default_factory=dict)
    by_correlation_type: dict[str, int] = Field(default_factory=dict)
    by_forecast_confidence: dict[str, int] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class CostTrendAnomalyCorrelator:
    """Correlate cost with deployments, attribute
    trends, forecast continuation."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[CostTrendRecord] = []
        self._analyses: dict[str, CostTrendAnalysis] = {}
        logger.info(
            "cost_trend_anomaly_correlator.init",
            max_records=max_records,
        )

    def add_record(
        self,
        service_name: str = "",
        trend_direction: TrendDirection = (TrendDirection.STABLE),
        correlation_type: CorrelationType = (CorrelationType.DEPLOYMENT),
        forecast_confidence: ForecastConfidence = (ForecastConfidence.MEDIUM),
        current_cost: float = 0.0,
        previous_cost: float = 0.0,
        event_id: str = "",
        description: str = "",
    ) -> CostTrendRecord:
        record = CostTrendRecord(
            service_name=service_name,
            trend_direction=trend_direction,
            correlation_type=correlation_type,
            forecast_confidence=forecast_confidence,
            current_cost=current_cost,
            previous_cost=previous_cost,
            event_id=event_id,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "cost_trend_correlator.record_added",
            record_id=record.id,
            service_name=service_name,
        )
        return record

    def process(self, key: str) -> CostTrendAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        change = 0.0
        if rec.previous_cost > 0:
            change = round(
                (rec.current_cost - rec.previous_cost) / rec.previous_cost * 100,
                2,
            )
        strength = min(abs(change) / 100, 1.0)
        analysis = CostTrendAnalysis(
            service_name=rec.service_name,
            trend_direction=rec.trend_direction,
            change_pct=change,
            correlation_strength=round(strength, 2),
            forecast_confidence=(rec.forecast_confidence),
            description=(f"Trend {rec.service_name} change {change}%"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> CostTrendReport:
        by_td: dict[str, int] = {}
        by_ct: dict[str, int] = {}
        by_fc: dict[str, int] = {}
        changes: list[float] = []
        for r in self._records:
            k = r.trend_direction.value
            by_td[k] = by_td.get(k, 0) + 1
            k2 = r.correlation_type.value
            by_ct[k2] = by_ct.get(k2, 0) + 1
            k3 = r.forecast_confidence.value
            by_fc[k3] = by_fc.get(k3, 0) + 1
            if r.previous_cost > 0:
                chg = (r.current_cost - r.previous_cost) / r.previous_cost * 100
                changes.append(chg)
        avg_chg = round(sum(changes) / len(changes), 2) if changes else 0.0
        recs: list[str] = []
        increasing = [r for r in self._records if r.trend_direction == TrendDirection.INCREASING]
        if increasing:
            recs.append(f"{len(increasing)} services with increasing cost trend")
        if not recs:
            recs.append("Cost trends stable")
        return CostTrendReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_change_pct=avg_chg,
            by_trend_direction=by_td,
            by_correlation_type=by_ct,
            by_forecast_confidence=by_fc,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        td_dist: dict[str, int] = {}
        for r in self._records:
            k = r.trend_direction.value
            td_dist[k] = td_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "trend_direction_dist": td_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("cost_trend_anomaly_correlator.cleared")
        return {"status": "cleared"}

    # -- domain methods ---

    def correlate_cost_with_deployments(
        self,
    ) -> list[dict[str, Any]]:
        """Correlate cost changes with deploys."""
        deploy_recs = [r for r in self._records if r.correlation_type == CorrelationType.DEPLOYMENT]
        svc_map: dict[str, list[float]] = {}
        for r in deploy_recs:
            change = 0.0
            if r.previous_cost > 0:
                change = r.current_cost - r.previous_cost
            svc_map.setdefault(r.service_name, []).append(change)
        results: list[dict[str, Any]] = []
        for svc, changes in svc_map.items():
            total = round(sum(changes), 2)
            results.append(
                {
                    "service_name": svc,
                    "deploy_count": len(changes),
                    "total_cost_impact": total,
                    "avg_impact": round(total / len(changes), 2),
                }
            )
        results.sort(
            key=lambda x: abs(x["total_cost_impact"]),
            reverse=True,
        )
        return results

    def attribute_trend_to_business_events(
        self,
    ) -> list[dict[str, Any]]:
        """Attribute trends to business events."""
        event_map: dict[str, list[float]] = {}
        for r in self._records:
            if r.event_id:
                change = 0.0
                if r.previous_cost > 0:
                    change = r.current_cost - r.previous_cost
                event_map.setdefault(r.event_id, []).append(change)
        results: list[dict[str, Any]] = []
        for eid, changes in event_map.items():
            total = round(sum(changes), 2)
            results.append(
                {
                    "event_id": eid,
                    "impact_count": len(changes),
                    "total_impact": total,
                }
            )
        results.sort(
            key=lambda x: abs(x["total_impact"]),
            reverse=True,
        )
        return results

    def forecast_trend_continuation(
        self,
    ) -> list[dict[str, Any]]:
        """Forecast if trends will continue."""
        svc_trends: dict[str, list[float]] = {}
        svc_conf: dict[str, str] = {}
        for r in self._records:
            change = 0.0
            if r.previous_cost > 0:
                change = (r.current_cost - r.previous_cost) / r.previous_cost * 100
            svc_trends.setdefault(r.service_name, []).append(change)
            svc_conf[r.service_name] = r.forecast_confidence.value
        results: list[dict[str, Any]] = []
        for svc, changes in svc_trends.items():
            avg = round(sum(changes) / len(changes), 2)
            direction = "stable"
            if avg > 5:
                direction = "increasing"
            elif avg < -5:
                direction = "decreasing"
            results.append(
                {
                    "service_name": svc,
                    "avg_change_pct": avg,
                    "forecast_direction": (direction),
                    "confidence": svc_conf[svc],
                }
            )
        return results
