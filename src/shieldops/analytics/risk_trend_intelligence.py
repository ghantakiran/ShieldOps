"""Risk Trend Intelligence
compute risk trajectory, detect risk anomalies,
forecast risk levels across domains."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class TrendWindow(StrEnum):
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class TrendDirection(StrEnum):
    ESCALATING = "escalating"
    STABLE = "stable"
    DECLINING = "declining"
    VOLATILE = "volatile"


class RiskDomain(StrEnum):
    IDENTITY = "identity"
    NETWORK = "network"
    ENDPOINT = "endpoint"
    CLOUD = "cloud"


# --- Models ---


class RiskTrendRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    trend_id: str = ""
    window: TrendWindow = TrendWindow.DAILY
    direction: TrendDirection = TrendDirection.STABLE
    domain: RiskDomain = RiskDomain.NETWORK
    risk_score: float = 0.0
    previous_score: float = 0.0
    entity_id: str = ""
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class RiskTrendAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    trend_id: str = ""
    domain: RiskDomain = RiskDomain.NETWORK
    trajectory: float = 0.0
    is_anomalous: bool = False
    forecast_score: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class RiskTrendReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_risk_score: float = 0.0
    by_window: dict[str, int] = Field(default_factory=dict)
    by_direction: dict[str, int] = Field(default_factory=dict)
    by_domain: dict[str, int] = Field(default_factory=dict)
    escalating_domains: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class RiskTrendIntelligence:
    """Compute risk trajectory, detect anomalies,
    forecast risk levels."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[RiskTrendRecord] = []
        self._analyses: dict[str, RiskTrendAnalysis] = {}
        logger.info(
            "risk_trend_intelligence.init",
            max_records=max_records,
        )

    def add_record(
        self,
        trend_id: str = "",
        window: TrendWindow = TrendWindow.DAILY,
        direction: TrendDirection = (TrendDirection.STABLE),
        domain: RiskDomain = RiskDomain.NETWORK,
        risk_score: float = 0.0,
        previous_score: float = 0.0,
        entity_id: str = "",
        description: str = "",
    ) -> RiskTrendRecord:
        record = RiskTrendRecord(
            trend_id=trend_id,
            window=window,
            direction=direction,
            domain=domain,
            risk_score=risk_score,
            previous_score=previous_score,
            entity_id=entity_id,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "risk_trend_intelligence.record_added",
            record_id=record.id,
            trend_id=trend_id,
        )
        return record

    def process(self, key: str) -> RiskTrendAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        trajectory = round(rec.risk_score - rec.previous_score, 2)
        is_anomalous = abs(trajectory) > 20.0
        forecast = round(rec.risk_score + trajectory * 0.5, 2)
        analysis = RiskTrendAnalysis(
            trend_id=rec.trend_id,
            domain=rec.domain,
            trajectory=trajectory,
            is_anomalous=is_anomalous,
            forecast_score=forecast,
            description=(f"Trend {rec.trend_id} trajectory={trajectory}"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> RiskTrendReport:
        by_w: dict[str, int] = {}
        by_d: dict[str, int] = {}
        by_dm: dict[str, int] = {}
        scores: list[float] = []
        for r in self._records:
            k = r.window.value
            by_w[k] = by_w.get(k, 0) + 1
            k2 = r.direction.value
            by_d[k2] = by_d.get(k2, 0) + 1
            k3 = r.domain.value
            by_dm[k3] = by_dm.get(k3, 0) + 1
            scores.append(r.risk_score)
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        escalating = sorted(
            {r.domain.value for r in self._records if r.direction == TrendDirection.ESCALATING}
        )
        recs: list[str] = []
        if escalating:
            recs.append(f"{len(escalating)} domains escalating")
        if not recs:
            recs.append("Risk trends are stable")
        return RiskTrendReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_risk_score=avg,
            by_window=by_w,
            by_direction=by_d,
            by_domain=by_dm,
            escalating_domains=escalating,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        dom_dist: dict[str, int] = {}
        for r in self._records:
            k = r.domain.value
            dom_dist[k] = dom_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "domain_distribution": dom_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("risk_trend_intelligence.cleared")
        return {"status": "cleared"}

    # -- domain methods ---

    def compute_risk_trajectory(
        self,
    ) -> list[dict[str, Any]]:
        """Compute trajectory per domain."""
        dom_data: dict[str, list[float]] = {}
        for r in self._records:
            k = r.domain.value
            delta = r.risk_score - r.previous_score
            dom_data.setdefault(k, []).append(delta)
        results: list[dict[str, Any]] = []
        for dom, deltas in dom_data.items():
            avg_delta = round(sum(deltas) / len(deltas), 2)
            results.append(
                {
                    "domain": dom,
                    "avg_trajectory": avg_delta,
                    "sample_count": len(deltas),
                }
            )
        results.sort(
            key=lambda x: x["avg_trajectory"],
            reverse=True,
        )
        return results

    def detect_risk_anomalies(
        self,
    ) -> list[dict[str, Any]]:
        """Detect anomalous risk changes."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            delta = abs(r.risk_score - r.previous_score)
            if delta > 20.0:
                results.append(
                    {
                        "trend_id": r.trend_id,
                        "domain": r.domain.value,
                        "risk_score": r.risk_score,
                        "previous_score": (r.previous_score),
                        "delta": round(delta, 2),
                    }
                )
        results.sort(key=lambda x: x["delta"], reverse=True)
        return results

    def forecast_risk_levels(
        self,
    ) -> list[dict[str, Any]]:
        """Forecast risk levels per domain."""
        dom_scores: dict[str, list[tuple[float, float]]] = {}
        for r in self._records:
            k = r.domain.value
            dom_scores.setdefault(k, []).append((r.previous_score, r.risk_score))
        results: list[dict[str, Any]] = []
        for dom, pairs in dom_scores.items():
            latest = pairs[-1][1]
            avg_delta = round(
                sum(b - a for a, b in pairs) / len(pairs),
                2,
            )
            forecast = round(latest + avg_delta * 0.5, 2)
            results.append(
                {
                    "domain": dom,
                    "current_score": latest,
                    "avg_delta": avg_delta,
                    "forecast_score": forecast,
                }
            )
        return results
