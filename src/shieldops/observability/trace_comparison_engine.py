"""Trace Comparison Engine —
compare traces across time periods or versions,
detect behavioral changes, rank differences by significance."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ComparisonType(StrEnum):
    TEMPORAL = "temporal"
    VERSION = "version"
    CANARY = "canary"
    BASELINE = "baseline"


class DifferenceType(StrEnum):
    STRUCTURAL = "structural"
    PERFORMANCE = "performance"
    ERROR_RATE = "error_rate"
    VOLUME = "volume"


class ComparisonResult(StrEnum):
    IMPROVED = "improved"
    UNCHANGED = "unchanged"
    DEGRADED = "degraded"
    INCOMPARABLE = "incomparable"


# --- Models ---


class TraceComparisonRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    baseline_trace_id: str = ""
    candidate_trace_id: str = ""
    comparison_type: ComparisonType = ComparisonType.TEMPORAL
    difference_type: DifferenceType = DifferenceType.PERFORMANCE
    comparison_result: ComparisonResult = ComparisonResult.UNCHANGED
    baseline_latency_ms: float = 0.0
    candidate_latency_ms: float = 0.0
    baseline_error_rate: float = 0.0
    candidate_error_rate: float = 0.0
    difference_score: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class TraceComparisonAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    comparison_type: ComparisonType = ComparisonType.TEMPORAL
    latency_delta_ms: float = 0.0
    error_rate_delta: float = 0.0
    comparison_result: ComparisonResult = ComparisonResult.UNCHANGED
    significance_score: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class TraceComparisonReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_difference_score: float = 0.0
    by_comparison_type: dict[str, int] = Field(default_factory=dict)
    by_difference_type: dict[str, int] = Field(default_factory=dict)
    by_comparison_result: dict[str, int] = Field(default_factory=dict)
    degraded_services: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class TraceComparisonEngine:
    """Compare traces across time periods or versions,
    detect behavioral changes, rank differences by significance."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[TraceComparisonRecord] = []
        self._analyses: dict[str, TraceComparisonAnalysis] = {}
        logger.info("trace_comparison_engine.init", max_records=max_records)

    def add_record(
        self,
        service_name: str = "",
        baseline_trace_id: str = "",
        candidate_trace_id: str = "",
        comparison_type: ComparisonType = ComparisonType.TEMPORAL,
        difference_type: DifferenceType = DifferenceType.PERFORMANCE,
        comparison_result: ComparisonResult = ComparisonResult.UNCHANGED,
        baseline_latency_ms: float = 0.0,
        candidate_latency_ms: float = 0.0,
        baseline_error_rate: float = 0.0,
        candidate_error_rate: float = 0.0,
        difference_score: float = 0.0,
        description: str = "",
    ) -> TraceComparisonRecord:
        record = TraceComparisonRecord(
            service_name=service_name,
            baseline_trace_id=baseline_trace_id,
            candidate_trace_id=candidate_trace_id,
            comparison_type=comparison_type,
            difference_type=difference_type,
            comparison_result=comparison_result,
            baseline_latency_ms=baseline_latency_ms,
            candidate_latency_ms=candidate_latency_ms,
            baseline_error_rate=baseline_error_rate,
            candidate_error_rate=candidate_error_rate,
            difference_score=difference_score,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "trace_comparison.record_added",
            record_id=record.id,
            service_name=service_name,
        )
        return record

    def process(self, key: str) -> TraceComparisonAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        lat_delta = round(rec.candidate_latency_ms - rec.baseline_latency_ms, 2)
        err_delta = round(rec.candidate_error_rate - rec.baseline_error_rate, 4)
        significance = round(abs(lat_delta) * 0.01 + abs(err_delta) * 100, 2)
        analysis = TraceComparisonAnalysis(
            service_name=rec.service_name,
            comparison_type=rec.comparison_type,
            latency_delta_ms=lat_delta,
            error_rate_delta=err_delta,
            comparison_result=rec.comparison_result,
            significance_score=significance,
            description=(
                f"{rec.service_name} latency delta {lat_delta}ms "
                f"result {rec.comparison_result.value}"
            ),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(self) -> TraceComparisonReport:
        by_ctype: dict[str, int] = {}
        by_dtype: dict[str, int] = {}
        by_result: dict[str, int] = {}
        diff_scores: list[float] = []
        for r in self._records:
            ct = r.comparison_type.value
            by_ctype[ct] = by_ctype.get(ct, 0) + 1
            dt = r.difference_type.value
            by_dtype[dt] = by_dtype.get(dt, 0) + 1
            res = r.comparison_result.value
            by_result[res] = by_result.get(res, 0) + 1
            diff_scores.append(r.difference_score)
        avg = round(sum(diff_scores) / len(diff_scores), 2) if diff_scores else 0.0
        degraded = list(
            {
                r.service_name
                for r in self._records
                if r.comparison_result == ComparisonResult.DEGRADED
            }
        )[:10]
        recs: list[str] = []
        if degraded:
            recs.append(f"{len(degraded)} services show degraded behavior")
        if not recs:
            recs.append("No significant behavioral regressions detected")
        return TraceComparisonReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_difference_score=avg,
            by_comparison_type=by_ctype,
            by_difference_type=by_dtype,
            by_comparison_result=by_result,
            degraded_services=degraded,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        result_dist: dict[str, int] = {}
        for r in self._records:
            k = r.comparison_result.value
            result_dist[k] = result_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "result_distribution": result_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("trace_comparison_engine.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def compare_trace_profiles(self) -> list[dict[str, Any]]:
        """Compare trace profiles per service across all comparison types."""
        svc_data: dict[str, list[dict[str, Any]]] = {}
        for r in self._records:
            svc_data.setdefault(r.service_name, []).append(
                {
                    "lat_baseline": r.baseline_latency_ms,
                    "lat_candidate": r.candidate_latency_ms,
                    "err_baseline": r.baseline_error_rate,
                    "err_candidate": r.candidate_error_rate,
                    "result": r.comparison_result.value,
                }
            )
        results: list[dict[str, Any]] = []
        for svc, items in svc_data.items():
            avg_lat_delta = sum(i["lat_candidate"] - i["lat_baseline"] for i in items) / len(items)
            avg_err_delta = sum(i["err_candidate"] - i["err_baseline"] for i in items) / len(items)
            results.append(
                {
                    "service_name": svc,
                    "comparison_count": len(items),
                    "avg_latency_delta_ms": round(avg_lat_delta, 2),
                    "avg_error_rate_delta": round(avg_err_delta, 4),
                    "degraded_pct": round(
                        sum(1 for i in items if i["result"] == "degraded") / len(items) * 100,
                        2,
                    ),
                }
            )
        results.sort(key=lambda x: x["avg_latency_delta_ms"], reverse=True)
        return results

    def detect_behavioral_changes(self) -> list[dict[str, Any]]:
        """Detect significant behavioral changes in trace comparisons."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.comparison_result in (
                ComparisonResult.DEGRADED,
                ComparisonResult.IMPROVED,
            ):
                lat_delta = round(r.candidate_latency_ms - r.baseline_latency_ms, 2)
                err_delta = round(r.candidate_error_rate - r.baseline_error_rate, 4)
                results.append(
                    {
                        "service_name": r.service_name,
                        "comparison_type": r.comparison_type.value,
                        "difference_type": r.difference_type.value,
                        "comparison_result": r.comparison_result.value,
                        "latency_delta_ms": lat_delta,
                        "error_rate_delta": err_delta,
                        "difference_score": r.difference_score,
                    }
                )
        results.sort(key=lambda x: x["difference_score"], reverse=True)
        return results

    def rank_differences_by_significance(self) -> list[dict[str, Any]]:
        """Rank all trace comparison differences by computed significance."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            lat_delta = abs(r.candidate_latency_ms - r.baseline_latency_ms)
            err_delta = abs(r.candidate_error_rate - r.baseline_error_rate)
            significance = round(lat_delta * 0.01 + err_delta * 100 + r.difference_score, 2)
            results.append(
                {
                    "service_name": r.service_name,
                    "comparison_type": r.comparison_type.value,
                    "comparison_result": r.comparison_result.value,
                    "significance_score": significance,
                    "rank": 0,
                }
            )
        results.sort(key=lambda x: x["significance_score"], reverse=True)
        for idx, entry in enumerate(results, 1):
            entry["rank"] = idx
        return results
