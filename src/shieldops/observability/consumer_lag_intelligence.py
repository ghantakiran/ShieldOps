"""Consumer Lag Intelligence —
forecast lag growth, detect consumer stalls,
rank consumer groups by lag severity."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class LagTrend(StrEnum):
    GROWING = "growing"
    STABLE = "stable"
    SHRINKING = "shrinking"
    VOLATILE = "volatile"


class StallReason(StrEnum):
    PROCESSING_ERROR = "processing_error"
    RESOURCE_LIMIT = "resource_limit"
    BACKPRESSURE = "backpressure"
    CONFIGURATION = "configuration"


class LagSeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# --- Models ---


class ConsumerLagRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    consumer_group: str = ""
    lag_trend: LagTrend = LagTrend.STABLE
    stall_reason: StallReason = StallReason.PROCESSING_ERROR
    lag_severity: LagSeverity = LagSeverity.LOW
    current_lag: int = 0
    lag_rate: float = 0.0
    topic: str = ""
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ConsumerLagAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    consumer_group: str = ""
    lag_trend: LagTrend = LagTrend.STABLE
    forecast_lag: int = 0
    stall_detected: bool = False
    severity_score: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ConsumerLagReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_current_lag: float = 0.0
    by_trend: dict[str, int] = Field(default_factory=dict)
    by_stall_reason: dict[str, int] = Field(default_factory=dict)
    by_severity: dict[str, int] = Field(default_factory=dict)
    critical_groups: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class ConsumerLagIntelligence:
    """Forecast lag growth, detect consumer stalls,
    rank consumer groups by lag severity."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[ConsumerLagRecord] = []
        self._analyses: dict[str, ConsumerLagAnalysis] = {}
        logger.info(
            "consumer_lag_intelligence.init",
            max_records=max_records,
        )

    def add_record(
        self,
        consumer_group: str = "",
        lag_trend: LagTrend = LagTrend.STABLE,
        stall_reason: StallReason = (StallReason.PROCESSING_ERROR),
        lag_severity: LagSeverity = LagSeverity.LOW,
        current_lag: int = 0,
        lag_rate: float = 0.0,
        topic: str = "",
        description: str = "",
    ) -> ConsumerLagRecord:
        record = ConsumerLagRecord(
            consumer_group=consumer_group,
            lag_trend=lag_trend,
            stall_reason=stall_reason,
            lag_severity=lag_severity,
            current_lag=current_lag,
            lag_rate=lag_rate,
            topic=topic,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "consumer_lag.record_added",
            record_id=record.id,
            consumer_group=consumer_group,
        )
        return record

    def process(self, key: str) -> ConsumerLagAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        forecast = int(rec.current_lag + rec.lag_rate * 60)
        stalled = rec.lag_trend == LagTrend.GROWING
        sev_weights = {
            "critical": 4,
            "high": 3,
            "medium": 2,
            "low": 1,
        }
        sev_score = round(
            sev_weights.get(rec.lag_severity.value, 1) * 25.0,
            2,
        )
        analysis = ConsumerLagAnalysis(
            consumer_group=rec.consumer_group,
            lag_trend=rec.lag_trend,
            forecast_lag=forecast,
            stall_detected=stalled,
            severity_score=sev_score,
            description=(f"Group {rec.consumer_group} lag {rec.current_lag}"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> ConsumerLagReport:
        by_t: dict[str, int] = {}
        by_sr: dict[str, int] = {}
        by_sv: dict[str, int] = {}
        lags: list[int] = []
        for r in self._records:
            k = r.lag_trend.value
            by_t[k] = by_t.get(k, 0) + 1
            k2 = r.stall_reason.value
            by_sr[k2] = by_sr.get(k2, 0) + 1
            k3 = r.lag_severity.value
            by_sv[k3] = by_sv.get(k3, 0) + 1
            lags.append(r.current_lag)
        avg = round(sum(lags) / len(lags), 2) if lags else 0.0
        crit = list(
            {
                r.consumer_group
                for r in self._records
                if r.lag_severity
                in (
                    LagSeverity.CRITICAL,
                    LagSeverity.HIGH,
                )
            }
        )[:10]
        recs: list[str] = []
        if crit:
            recs.append(f"{len(crit)} critical consumer groups")
        if not recs:
            recs.append("Consumer lag within limits")
        return ConsumerLagReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_current_lag=avg,
            by_trend=by_t,
            by_stall_reason=by_sr,
            by_severity=by_sv,
            critical_groups=crit,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        t_dist: dict[str, int] = {}
        for r in self._records:
            k = r.lag_trend.value
            t_dist[k] = t_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "trend_distribution": t_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("consumer_lag_intelligence.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def forecast_lag_growth(
        self,
    ) -> list[dict[str, Any]]:
        """Forecast lag growth per consumer group."""
        group_data: dict[str, list[dict[str, Any]]] = {}
        for r in self._records:
            group_data.setdefault(r.consumer_group, []).append(
                {
                    "lag": r.current_lag,
                    "rate": r.lag_rate,
                }
            )
        results: list[dict[str, Any]] = []
        for cg, data in group_data.items():
            avg_rate = sum(d["rate"] for d in data) / len(data)
            curr = data[-1]["lag"]
            forecast = int(curr + avg_rate * 60)
            results.append(
                {
                    "consumer_group": cg,
                    "current_lag": curr,
                    "avg_rate": round(avg_rate, 2),
                    "forecast_1h": forecast,
                    "samples": len(data),
                }
            )
        results.sort(
            key=lambda x: x["forecast_1h"],
            reverse=True,
        )
        return results

    def detect_consumer_stalls(
        self,
    ) -> list[dict[str, Any]]:
        """Detect stalled consumer groups."""
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for r in self._records:
            if r.lag_trend == LagTrend.GROWING and r.consumer_group not in seen:
                seen.add(r.consumer_group)
                results.append(
                    {
                        "consumer_group": (r.consumer_group),
                        "stall_reason": (r.stall_reason.value),
                        "current_lag": r.current_lag,
                        "lag_rate": r.lag_rate,
                        "topic": r.topic,
                    }
                )
        results.sort(
            key=lambda x: x["current_lag"],
            reverse=True,
        )
        return results

    def rank_consumer_groups_by_lag_severity(
        self,
    ) -> list[dict[str, Any]]:
        """Rank consumer groups by lag severity."""
        sev_weights = {
            "critical": 4,
            "high": 3,
            "medium": 2,
            "low": 1,
        }
        group_scores: dict[str, float] = {}
        for r in self._records:
            w = sev_weights.get(r.lag_severity.value, 1)
            score = w * r.current_lag
            group_scores[r.consumer_group] = group_scores.get(r.consumer_group, 0.0) + score
        results: list[dict[str, Any]] = []
        for cg, total_score in group_scores.items():
            results.append(
                {
                    "consumer_group": cg,
                    "severity_score": round(total_score, 2),
                    "rank": 0,
                }
            )
        results.sort(
            key=lambda x: x["severity_score"],
            reverse=True,
        )
        for i, entry in enumerate(results, 1):
            entry["rank"] = i
        return results
