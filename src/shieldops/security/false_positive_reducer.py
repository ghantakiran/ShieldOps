"""False Positive Reducer — identify and suppress false positive alerts systematically."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class FPCategory(StrEnum):
    MISCONFIGURATION = "misconfiguration"
    BENIGN_ACTIVITY = "benign_activity"
    KNOWN_BEHAVIOR = "known_behavior"
    TEST_TRAFFIC = "test_traffic"
    POLICY_EXCEPTION = "policy_exception"


class ReductionMethod(StrEnum):
    WHITELIST = "whitelist"
    THRESHOLD_ADJUST = "threshold_adjust"
    PATTERN_EXCLUDE = "pattern_exclude"
    CONTEXT_FILTER = "context_filter"
    ML_SUPPRESS = "ml_suppress"


class ReductionStatus(StrEnum):
    IDENTIFIED = "identified"
    ANALYZED = "analyzed"
    SUPPRESSED = "suppressed"
    VERIFIED = "verified"
    REVERTED = "reverted"


# --- Models ---


class FPRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    rule_name: str = ""
    fp_category: FPCategory = FPCategory.MISCONFIGURATION
    reduction_method: ReductionMethod = ReductionMethod.WHITELIST
    reduction_status: ReductionStatus = ReductionStatus.IDENTIFIED
    fp_rate: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class FPAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    rule_name: str = ""
    fp_category: FPCategory = FPCategory.MISCONFIGURATION
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class FPReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_score: float = 0.0
    by_category: dict[str, int] = Field(default_factory=dict)
    by_method: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class FalsePositiveReducer:
    """Identify and suppress false positive alerts systematically to reduce noise."""

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[FPRecord] = []
        self._analyses: list[FPAnalysis] = []
        logger.info(
            "false_positive_reducer.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_fp(
        self,
        rule_name: str,
        fp_category: FPCategory = FPCategory.MISCONFIGURATION,
        reduction_method: ReductionMethod = ReductionMethod.WHITELIST,
        reduction_status: ReductionStatus = ReductionStatus.IDENTIFIED,
        fp_rate: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> FPRecord:
        record = FPRecord(
            rule_name=rule_name,
            fp_category=fp_category,
            reduction_method=reduction_method,
            reduction_status=reduction_status,
            fp_rate=fp_rate,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "false_positive_reducer.fp_recorded",
            record_id=record.id,
            rule_name=rule_name,
            fp_category=fp_category.value,
            reduction_method=reduction_method.value,
        )
        return record

    def get_record(self, record_id: str) -> FPRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        fp_category: FPCategory | None = None,
        reduction_method: ReductionMethod | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[FPRecord]:
        results = list(self._records)
        if fp_category is not None:
            results = [r for r in results if r.fp_category == fp_category]
        if reduction_method is not None:
            results = [r for r in results if r.reduction_method == reduction_method]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        rule_name: str,
        fp_category: FPCategory = FPCategory.MISCONFIGURATION,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> FPAnalysis:
        analysis = FPAnalysis(
            rule_name=rule_name,
            fp_category=fp_category,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "false_positive_reducer.analysis_added",
            rule_name=rule_name,
            fp_category=fp_category.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_distribution(self) -> dict[str, Any]:
        """Group by fp_category; return count and avg fp_rate."""
        category_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.fp_category.value
            category_data.setdefault(key, []).append(r.fp_rate)
        result: dict[str, Any] = {}
        for category, scores in category_data.items():
            result[category] = {
                "count": len(scores),
                "avg_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_gaps(self) -> list[dict[str, Any]]:
        """Return records where fp_rate < threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.fp_rate < self._threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "rule_name": r.rule_name,
                        "fp_category": r.fp_category.value,
                        "fp_rate": r.fp_rate,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["fp_rate"])

    def rank_by_score(self) -> list[dict[str, Any]]:
        """Group by service, avg fp_rate, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.fp_rate)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_score"])
        return results

    def detect_trends(self) -> dict[str, Any]:
        """Split-half comparison on analysis_score; delta threshold 5.0."""
        if len(self._analyses) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [a.analysis_score for a in self._analyses]
        mid = len(vals) // 2
        first_half = vals[:mid]
        second_half = vals[mid:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        delta = round(avg_second - avg_first, 2)
        if abs(delta) < 5.0:
            trend = "stable"
        elif delta > 0:
            trend = "improving"
        else:
            trend = "degrading"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> FPReport:
        by_category: dict[str, int] = {}
        by_method: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for r in self._records:
            by_category[r.fp_category.value] = by_category.get(r.fp_category.value, 0) + 1
            by_method[r.reduction_method.value] = by_method.get(r.reduction_method.value, 0) + 1
            by_status[r.reduction_status.value] = by_status.get(r.reduction_status.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.fp_rate < self._threshold)
        scores = [r.fp_rate for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_gaps()
        top_gaps = [o["rule_name"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} rule(s) below FP reduction threshold ({self._threshold})")
        if self._records and avg_score < self._threshold:
            recs.append(f"Avg FP rate {avg_score} below threshold ({self._threshold})")
        if not recs:
            recs.append("False positive reduction is healthy")
        return FPReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_score=avg_score,
            by_category=by_category,
            by_method=by_method,
            by_status=by_status,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("false_positive_reducer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        category_dist: dict[str, int] = {}
        for r in self._records:
            key = r.fp_category.value
            category_dist[key] = category_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "category_distribution": category_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
