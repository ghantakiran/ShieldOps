"""Latency Distribution Analyzer
compute percentile shifts, detect tail latency spikes,
rank endpoints by latency risk."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class PercentileBucket(StrEnum):
    P50 = "p50"
    P95 = "p95"
    P99 = "p99"
    P999 = "p999"


class LatencyTrend(StrEnum):
    IMPROVING = "improving"
    STABLE = "stable"
    DEGRADING = "degrading"
    VOLATILE = "volatile"


class AnalysisWindow(StrEnum):
    MINUTE = "minute"
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"


# --- Models ---


class LatencyDistributionRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    endpoint_id: str = ""
    percentile_bucket: PercentileBucket = PercentileBucket.P50
    latency_trend: LatencyTrend = LatencyTrend.STABLE
    analysis_window: AnalysisWindow = AnalysisWindow.HOUR
    value_ms: float = 0.0
    baseline_ms: float = 0.0
    threshold_ms: float = 500.0
    service: str = ""
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class LatencyDistributionAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    endpoint_id: str = ""
    percentile_shift: float = 0.0
    latency_trend: LatencyTrend = LatencyTrend.STABLE
    spike_detected: bool = False
    data_points: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class LatencyDistributionReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_latency_ms: float = 0.0
    by_percentile: dict[str, int] = Field(default_factory=dict)
    by_trend: dict[str, int] = Field(default_factory=dict)
    by_window: dict[str, int] = Field(default_factory=dict)
    high_latency_endpoints: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class LatencyDistributionAnalyzer:
    """Compute percentile shifts, detect tail latency
    spikes, rank endpoints by latency risk."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[LatencyDistributionRecord] = []
        self._analyses: dict[str, LatencyDistributionAnalysis] = {}
        logger.info(
            "latency_distribution_analyzer.init",
            max_records=max_records,
        )

    def add_record(
        self,
        endpoint_id: str = "",
        percentile_bucket: PercentileBucket = PercentileBucket.P50,
        latency_trend: LatencyTrend = LatencyTrend.STABLE,
        analysis_window: AnalysisWindow = AnalysisWindow.HOUR,
        value_ms: float = 0.0,
        baseline_ms: float = 0.0,
        threshold_ms: float = 500.0,
        service: str = "",
        description: str = "",
    ) -> LatencyDistributionRecord:
        record = LatencyDistributionRecord(
            endpoint_id=endpoint_id,
            percentile_bucket=percentile_bucket,
            latency_trend=latency_trend,
            analysis_window=analysis_window,
            value_ms=value_ms,
            baseline_ms=baseline_ms,
            threshold_ms=threshold_ms,
            service=service,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "latency_distribution_analyzer.record_added",
            record_id=record.id,
            endpoint_id=endpoint_id,
        )
        return record

    def process(self, key: str) -> LatencyDistributionAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        points = sum(1 for r in self._records if r.endpoint_id == rec.endpoint_id)
        shift = round(rec.value_ms - rec.baseline_ms, 2)
        spike = rec.value_ms > rec.threshold_ms
        analysis = LatencyDistributionAnalysis(
            endpoint_id=rec.endpoint_id,
            percentile_shift=shift,
            latency_trend=rec.latency_trend,
            spike_detected=spike,
            data_points=points,
            description=f"Endpoint {rec.endpoint_id} latency {rec.value_ms}ms",
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> LatencyDistributionReport:
        by_p: dict[str, int] = {}
        by_t: dict[str, int] = {}
        by_w: dict[str, int] = {}
        latencies: list[float] = []
        for r in self._records:
            k = r.percentile_bucket.value
            by_p[k] = by_p.get(k, 0) + 1
            k2 = r.latency_trend.value
            by_t[k2] = by_t.get(k2, 0) + 1
            k3 = r.analysis_window.value
            by_w[k3] = by_w.get(k3, 0) + 1
            latencies.append(r.value_ms)
        avg = round(sum(latencies) / len(latencies), 2) if latencies else 0.0
        high = list({r.endpoint_id for r in self._records if r.value_ms > r.threshold_ms})[:10]
        recs: list[str] = []
        if high:
            recs.append(f"{len(high)} endpoints with high tail latency")
        if not recs:
            recs.append("All endpoint latencies within acceptable range")
        return LatencyDistributionReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_latency_ms=avg,
            by_percentile=by_p,
            by_trend=by_t,
            by_window=by_w,
            high_latency_endpoints=high,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        p_dist: dict[str, int] = {}
        for r in self._records:
            k = r.percentile_bucket.value
            p_dist[k] = p_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "percentile_distribution": p_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("latency_distribution_analyzer.cleared")
        return {"status": "cleared"}

    # -- domain methods ---

    def compute_percentile_shifts(
        self,
    ) -> list[dict[str, Any]]:
        """Compute percentile shifts per endpoint."""
        ep_data: dict[str, list[float]] = {}
        ep_baselines: dict[str, float] = {}
        for r in self._records:
            shift = r.value_ms - r.baseline_ms
            ep_data.setdefault(r.endpoint_id, []).append(shift)
            ep_baselines[r.endpoint_id] = r.baseline_ms
        results: list[dict[str, Any]] = []
        for eid, shifts in ep_data.items():
            avg_shift = round(sum(shifts) / len(shifts), 2)
            results.append(
                {
                    "endpoint_id": eid,
                    "avg_shift_ms": avg_shift,
                    "baseline_ms": ep_baselines[eid],
                    "data_points": len(shifts),
                }
            )
        results.sort(key=lambda x: x["avg_shift_ms"], reverse=True)
        return results

    def detect_tail_latency_spikes(
        self,
    ) -> list[dict[str, Any]]:
        """Detect endpoints with tail latency spikes."""
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for r in self._records:
            if r.value_ms > r.threshold_ms and r.endpoint_id not in seen:
                seen.add(r.endpoint_id)
                results.append(
                    {
                        "endpoint_id": r.endpoint_id,
                        "percentile": r.percentile_bucket.value,
                        "value_ms": r.value_ms,
                        "threshold_ms": r.threshold_ms,
                        "excess_ms": round(r.value_ms - r.threshold_ms, 2),
                    }
                )
        results.sort(key=lambda x: x["excess_ms"], reverse=True)
        return results

    def rank_endpoints_by_latency_risk(
        self,
    ) -> list[dict[str, Any]]:
        """Rank all endpoints by latency risk."""
        ep_data: dict[str, list[float]] = {}
        for r in self._records:
            ep_data.setdefault(r.endpoint_id, []).append(r.value_ms)
        results: list[dict[str, Any]] = []
        for eid, values in ep_data.items():
            avg = round(sum(values) / len(values), 2)
            results.append(
                {
                    "endpoint_id": eid,
                    "avg_latency_ms": avg,
                    "rank": 0,
                }
            )
        results.sort(key=lambda x: x["avg_latency_ms"], reverse=True)
        for i, entry in enumerate(results, 1):
            entry["rank"] = i
        return results
