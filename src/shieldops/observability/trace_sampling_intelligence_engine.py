"""Trace Sampling Intelligence Engine —
evaluate intelligent trace sampling decisions,
detect sampling bias, optimize sampling rates."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class SamplingStrategy(StrEnum):
    HEAD_BASED = "head_based"
    TAIL_BASED = "tail_based"
    PRIORITY = "priority"
    ADAPTIVE = "adaptive"


class SampleDecision(StrEnum):
    KEEP = "keep"
    DROP = "drop"
    DEFER = "defer"
    ESCALATE = "escalate"


class SamplingQuality(StrEnum):
    REPRESENTATIVE = "representative"
    BIASED = "biased"
    SPARSE = "sparse"
    COMPREHENSIVE = "comprehensive"


# --- Models ---


class TraceSamplingRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    trace_id: str = ""
    sampling_strategy: SamplingStrategy = SamplingStrategy.HEAD_BASED
    sample_decision: SampleDecision = SampleDecision.KEEP
    sampling_quality: SamplingQuality = SamplingQuality.REPRESENTATIVE
    sampling_rate: float = 0.0
    trace_volume: int = 0
    kept_traces: int = 0
    bias_score: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class TraceSamplingAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    sampling_strategy: SamplingStrategy = SamplingStrategy.HEAD_BASED
    effective_rate: float = 0.0
    bias_detected: bool = False
    quality: SamplingQuality = SamplingQuality.REPRESENTATIVE
    recommended_rate: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class TraceSamplingReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_sampling_rate: float = 0.0
    by_sampling_strategy: dict[str, int] = Field(default_factory=dict)
    by_sample_decision: dict[str, int] = Field(default_factory=dict)
    by_sampling_quality: dict[str, int] = Field(default_factory=dict)
    biased_services: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class TraceSamplingIntelligenceEngine:
    """Evaluate intelligent trace sampling decisions,
    detect sampling bias, optimize sampling rates."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[TraceSamplingRecord] = []
        self._analyses: dict[str, TraceSamplingAnalysis] = {}
        logger.info("trace_sampling_intelligence_engine.init", max_records=max_records)

    def add_record(
        self,
        service_name: str = "",
        trace_id: str = "",
        sampling_strategy: SamplingStrategy = SamplingStrategy.HEAD_BASED,
        sample_decision: SampleDecision = SampleDecision.KEEP,
        sampling_quality: SamplingQuality = SamplingQuality.REPRESENTATIVE,
        sampling_rate: float = 0.0,
        trace_volume: int = 0,
        kept_traces: int = 0,
        bias_score: float = 0.0,
        description: str = "",
    ) -> TraceSamplingRecord:
        record = TraceSamplingRecord(
            service_name=service_name,
            trace_id=trace_id,
            sampling_strategy=sampling_strategy,
            sample_decision=sample_decision,
            sampling_quality=sampling_quality,
            sampling_rate=sampling_rate,
            trace_volume=trace_volume,
            kept_traces=kept_traces,
            bias_score=bias_score,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "trace_sampling.record_added",
            record_id=record.id,
            service_name=service_name,
        )
        return record

    def process(self, key: str) -> TraceSamplingAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        effective = 0.0
        if rec.trace_volume > 0:
            effective = round(rec.kept_traces / rec.trace_volume * 100, 2)
        recommended = min(100.0, effective * 1.1) if rec.bias_score > 0.5 else effective
        analysis = TraceSamplingAnalysis(
            service_name=rec.service_name,
            sampling_strategy=rec.sampling_strategy,
            effective_rate=effective,
            bias_detected=rec.bias_score > 0.5,
            quality=rec.sampling_quality,
            recommended_rate=round(recommended, 2),
            description=(f"{rec.service_name} effective rate {effective}% bias {rec.bias_score}"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> TraceSamplingReport:
        by_strat: dict[str, int] = {}
        by_dec: dict[str, int] = {}
        by_qual: dict[str, int] = {}
        rates: list[float] = []
        for r in self._records:
            s = r.sampling_strategy.value
            by_strat[s] = by_strat.get(s, 0) + 1
            d = r.sample_decision.value
            by_dec[d] = by_dec.get(d, 0) + 1
            q = r.sampling_quality.value
            by_qual[q] = by_qual.get(q, 0) + 1
            rates.append(r.sampling_rate)
        avg = round(sum(rates) / len(rates), 2) if rates else 0.0
        biased = list({r.service_name for r in self._records if r.bias_score > 0.5})[:10]
        recs: list[str] = []
        if biased:
            recs.append(f"{len(biased)} services with sampling bias detected")
        if not recs:
            recs.append("Sampling quality within acceptable limits")
        return TraceSamplingReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_sampling_rate=avg,
            by_sampling_strategy=by_strat,
            by_sample_decision=by_dec,
            by_sampling_quality=by_qual,
            biased_services=biased,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        strat_dist: dict[str, int] = {}
        for r in self._records:
            k = r.sampling_strategy.value
            strat_dist[k] = strat_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "strategy_distribution": strat_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("trace_sampling_intelligence_engine.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def evaluate_sampling_strategies(self) -> list[dict[str, Any]]:
        """Evaluate effectiveness of each sampling strategy."""
        strat_data: dict[str, dict[str, Any]] = {}
        for r in self._records:
            sv = r.sampling_strategy.value
            if sv not in strat_data:
                strat_data[sv] = {
                    "count": 0,
                    "total_rate": 0.0,
                    "total_bias": 0.0,
                    "kept": 0,
                    "volume": 0,
                }
            strat_data[sv]["count"] += 1
            strat_data[sv]["total_rate"] += r.sampling_rate
            strat_data[sv]["total_bias"] += r.bias_score
            strat_data[sv]["kept"] += r.kept_traces
            strat_data[sv]["volume"] += r.trace_volume
        results: list[dict[str, Any]] = []
        for sv, data in strat_data.items():
            cnt = data["count"]
            vol = data["volume"]
            effective = round(data["kept"] / vol * 100, 2) if vol > 0 else 0.0
            results.append(
                {
                    "sampling_strategy": sv,
                    "record_count": cnt,
                    "avg_sampling_rate": round(data["total_rate"] / cnt, 2),
                    "avg_bias_score": round(data["total_bias"] / cnt, 2),
                    "effective_rate_pct": effective,
                }
            )
        results.sort(key=lambda x: x["effective_rate_pct"], reverse=True)
        return results

    def detect_sampling_bias(self) -> list[dict[str, Any]]:
        """Detect services with significant sampling bias."""
        svc_bias: dict[str, list[float]] = {}
        for r in self._records:
            svc_bias.setdefault(r.service_name, []).append(r.bias_score)
        results: list[dict[str, Any]] = []
        for svc, bias_vals in svc_bias.items():
            avg_bias = sum(bias_vals) / len(bias_vals)
            max_bias = max(bias_vals)
            results.append(
                {
                    "service_name": svc,
                    "avg_bias_score": round(avg_bias, 2),
                    "max_bias_score": round(max_bias, 2),
                    "sample_count": len(bias_vals),
                    "bias_detected": avg_bias > 0.5,
                }
            )
        results.sort(key=lambda x: x["avg_bias_score"], reverse=True)
        return results

    def optimize_sampling_rates(self) -> list[dict[str, Any]]:
        """Recommend optimal sampling rates per service."""
        svc_data: dict[str, list[dict[str, Any]]] = {}
        for r in self._records:
            svc_data.setdefault(r.service_name, []).append(
                {
                    "rate": r.sampling_rate,
                    "bias": r.bias_score,
                    "quality": r.sampling_quality.value,
                }
            )
        results: list[dict[str, Any]] = []
        for svc, items in svc_data.items():
            avg_rate = sum(i["rate"] for i in items) / len(items)
            avg_bias = sum(i["bias"] for i in items) / len(items)
            recommended = min(100.0, avg_rate * (1 + avg_bias))
            results.append(
                {
                    "service_name": svc,
                    "current_avg_rate": round(avg_rate, 2),
                    "avg_bias_score": round(avg_bias, 2),
                    "recommended_rate": round(recommended, 2),
                    "adjustment_pct": round(recommended - avg_rate, 2),
                }
            )
        results.sort(key=lambda x: x["adjustment_pct"], reverse=True)
        return results
