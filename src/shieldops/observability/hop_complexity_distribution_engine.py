"""Hop Complexity Distribution Engine —
analyze investigation complexity distribution (4:3:2:1 ratio),
detect distribution shifts, compare to optimal ratio."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ComplexityBucket(StrEnum):
    ONE_HOP = "one_hop"
    TWO_HOP = "two_hop"
    THREE_HOP = "three_hop"
    FOUR_PLUS_HOP = "four_plus_hop"


class DistributionTrend(StrEnum):
    SHIFTING_COMPLEX = "shifting_complex"
    STABLE = "stable"
    SHIFTING_SIMPLE = "shifting_simple"
    BIMODAL = "bimodal"


class AnalysisPeriod(StrEnum):
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


# --- Models ---


class HopComplexityDistributionRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    investigation_id: str = ""
    complexity_bucket: ComplexityBucket = ComplexityBucket.ONE_HOP
    distribution_trend: DistributionTrend = DistributionTrend.STABLE
    analysis_period: AnalysisPeriod = AnalysisPeriod.DAILY
    hop_count: int = 1
    period_label: str = ""
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class HopComplexityDistributionAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    investigation_id: str = ""
    complexity_bucket: ComplexityBucket = ComplexityBucket.ONE_HOP
    distribution_trend: DistributionTrend = DistributionTrend.STABLE
    analysis_period: AnalysisPeriod = AnalysisPeriod.DAILY
    shift_detected: bool = False
    hop_count: int = 1
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class HopComplexityDistributionReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_hop_count: float = 0.0
    by_complexity_bucket: dict[str, int] = Field(default_factory=dict)
    by_distribution_trend: dict[str, int] = Field(default_factory=dict)
    by_analysis_period: dict[str, int] = Field(default_factory=dict)
    optimal_ratio_delta: dict[str, float] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class HopComplexityDistributionEngine:
    """Analyze investigation complexity distribution (4:3:2:1 ratio),
    detect distribution shifts, compare to optimal ratio."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[HopComplexityDistributionRecord] = []
        self._analyses: dict[str, HopComplexityDistributionAnalysis] = {}
        logger.info("hop_complexity_distribution_engine.init", max_records=max_records)

    def add_record(
        self,
        investigation_id: str = "",
        complexity_bucket: ComplexityBucket = ComplexityBucket.ONE_HOP,
        distribution_trend: DistributionTrend = DistributionTrend.STABLE,
        analysis_period: AnalysisPeriod = AnalysisPeriod.DAILY,
        hop_count: int = 1,
        period_label: str = "",
        description: str = "",
    ) -> HopComplexityDistributionRecord:
        record = HopComplexityDistributionRecord(
            investigation_id=investigation_id,
            complexity_bucket=complexity_bucket,
            distribution_trend=distribution_trend,
            analysis_period=analysis_period,
            hop_count=hop_count,
            period_label=period_label,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "hop_complexity_distribution.record_added",
            record_id=record.id,
            investigation_id=investigation_id,
        )
        return record

    def process(self, key: str) -> HopComplexityDistributionAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        shift = rec.distribution_trend in (
            DistributionTrend.SHIFTING_COMPLEX,
            DistributionTrend.BIMODAL,
        )
        analysis = HopComplexityDistributionAnalysis(
            investigation_id=rec.investigation_id,
            complexity_bucket=rec.complexity_bucket,
            distribution_trend=rec.distribution_trend,
            analysis_period=rec.analysis_period,
            shift_detected=shift,
            hop_count=rec.hop_count,
            description=(
                f"Investigation {rec.investigation_id} "
                f"bucket={rec.complexity_bucket.value} "
                f"hops={rec.hop_count}"
            ),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> HopComplexityDistributionReport:
        by_cb: dict[str, int] = {}
        by_dt: dict[str, int] = {}
        by_ap: dict[str, int] = {}
        hops: list[int] = []
        for r in self._records:
            k = r.complexity_bucket.value
            by_cb[k] = by_cb.get(k, 0) + 1
            k2 = r.distribution_trend.value
            by_dt[k2] = by_dt.get(k2, 0) + 1
            k3 = r.analysis_period.value
            by_ap[k3] = by_ap.get(k3, 0) + 1
            hops.append(r.hop_count)
        avg_hops = round(sum(hops) / len(hops), 4) if hops else 0.0
        # Optimal 4:3:2:1 ratio (one:two:three:four_plus)
        optimal_ratio = {
            "one_hop": 0.4,
            "two_hop": 0.3,
            "three_hop": 0.2,
            "four_plus_hop": 0.1,
        }
        total = max(len(self._records), 1)
        delta: dict[str, float] = {
            bv: round((by_cb.get(bv, 0) / total) - optimal_ratio.get(bv, 0.0), 4)
            for bv in optimal_ratio
        }
        recs: list[str] = []
        shifting_complex = by_dt.get("shifting_complex", 0)
        if shifting_complex:
            recs.append(f"{shifting_complex} periods shifting toward higher complexity")
        bimodal = by_dt.get("bimodal", 0)
        if bimodal:
            recs.append(f"{bimodal} bimodal distributions indicate workload fragmentation")
        if not recs:
            recs.append("Hop complexity distribution is within optimal 4:3:2:1 ratio")
        return HopComplexityDistributionReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_hop_count=avg_hops,
            by_complexity_bucket=by_cb,
            by_distribution_trend=by_dt,
            by_analysis_period=by_ap,
            optimal_ratio_delta=delta,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        dist: dict[str, int] = {}
        for r in self._records:
            k = r.complexity_bucket.value
            dist[k] = dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "complexity_bucket_distribution": dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("hop_complexity_distribution_engine.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def compute_hop_distribution(self) -> list[dict[str, Any]]:
        """Compute hop distribution across complexity buckets per period."""
        period_bucket: dict[str, dict[str, int]] = {}
        for r in self._records:
            pl = r.period_label or r.analysis_period.value
            period_bucket.setdefault(pl, {})
            bv = r.complexity_bucket.value
            period_bucket[pl][bv] = period_bucket[pl].get(bv, 0) + 1
        results: list[dict[str, Any]] = []
        for pl, bucket_counts in period_bucket.items():
            total_p = sum(bucket_counts.values())
            ratios = {bv: round(cnt / total_p, 4) for bv, cnt in bucket_counts.items()}
            results.append(
                {
                    "period_label": pl,
                    "bucket_counts": bucket_counts,
                    "bucket_ratios": ratios,
                    "total": total_p,
                }
            )
        results.sort(key=lambda x: x["total"], reverse=True)
        return results

    def detect_distribution_shift(self) -> list[dict[str, Any]]:
        """Detect periods with distribution trend shifts."""
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for r in self._records:
            if r.distribution_trend in (
                DistributionTrend.SHIFTING_COMPLEX,
                DistributionTrend.BIMODAL,
            ):
                key = f"{r.period_label}:{r.distribution_trend.value}"
                if key not in seen:
                    seen.add(key)
                    results.append(
                        {
                            "period_label": r.period_label,
                            "distribution_trend": r.distribution_trend.value,
                            "analysis_period": r.analysis_period.value,
                            "complexity_bucket": r.complexity_bucket.value,
                            "hop_count": r.hop_count,
                        }
                    )
        results.sort(key=lambda x: x["hop_count"], reverse=True)
        return results

    def compare_to_optimal_ratio(self) -> list[dict[str, Any]]:
        """Compare actual bucket distribution to optimal 4:3:2:1 ratio."""
        optimal_ratio = {
            "one_hop": 0.4,
            "two_hop": 0.3,
            "three_hop": 0.2,
            "four_plus_hop": 0.1,
        }
        bucket_counts: dict[str, int] = {}
        for r in self._records:
            bv = r.complexity_bucket.value
            bucket_counts[bv] = bucket_counts.get(bv, 0) + 1
        total = max(len(self._records), 1)
        results: list[dict[str, Any]] = []
        for bv, opt_ratio in optimal_ratio.items():
            actual_ratio = bucket_counts.get(bv, 0) / total
            delta = round(actual_ratio - opt_ratio, 4)
            results.append(
                {
                    "complexity_bucket": bv,
                    "actual_ratio": round(actual_ratio, 4),
                    "optimal_ratio": opt_ratio,
                    "delta": delta,
                    "deviation": abs(delta),
                    "status": "over" if delta > 0 else ("under" if delta < 0 else "on_target"),
                }
            )
        results.sort(key=lambda x: x["deviation"], reverse=True)
        return results
