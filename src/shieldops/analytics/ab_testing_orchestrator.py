"""A/B Testing Orchestrator — orchestrate A/B tests for ML model experimentation."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class TestVariant(StrEnum):
    CONTROL = "control"
    TREATMENT_A = "treatment_a"
    TREATMENT_B = "treatment_b"
    TREATMENT_C = "treatment_c"
    HOLDOUT = "holdout"


class TestStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    STOPPED = "stopped"
    FAILED = "failed"
    PENDING = "pending"


class SignificanceLevel(StrEnum):
    P_001 = "p_001"
    P_005 = "p_005"
    P_01 = "p_01"
    P_05 = "p_05"
    NOT_SIGNIFICANT = "not_significant"


# --- Models ---


class ABTestRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    test_id: str = ""
    model_id: str = ""
    test_variant: TestVariant = TestVariant.CONTROL
    test_status: TestStatus = TestStatus.PENDING
    significance_level: SignificanceLevel = SignificanceLevel.NOT_SIGNIFICANT
    effect_size: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class ABTestAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    test_id: str = ""
    test_variant: TestVariant = TestVariant.CONTROL
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ABTestReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    significant_count: int = 0
    avg_effect_size: float = 0.0
    by_variant: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    by_significance: dict[str, int] = Field(default_factory=dict)
    top_winners: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class ABTestingOrchestrator:
    """Orchestrate A/B tests for ML model experimentation."""

    def __init__(
        self,
        max_records: int = 200000,
        min_effect_size: float = 0.05,
    ) -> None:
        self._max_records = max_records
        self._min_effect_size = min_effect_size
        self._records: list[ABTestRecord] = []
        self._analyses: list[ABTestAnalysis] = []
        logger.info(
            "ab_testing_orchestrator.initialized",
            max_records=max_records,
            min_effect_size=min_effect_size,
        )

    # -- record / get / list ------------------------------------------------

    def record_test(
        self,
        test_id: str,
        model_id: str = "",
        test_variant: TestVariant = TestVariant.CONTROL,
        test_status: TestStatus = TestStatus.PENDING,
        significance_level: SignificanceLevel = SignificanceLevel.NOT_SIGNIFICANT,
        effect_size: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> ABTestRecord:
        record = ABTestRecord(
            test_id=test_id,
            model_id=model_id,
            test_variant=test_variant,
            test_status=test_status,
            significance_level=significance_level,
            effect_size=effect_size,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "ab_testing_orchestrator.test_recorded",
            record_id=record.id,
            test_id=test_id,
            test_variant=test_variant.value,
        )
        return record

    def get_test(self, record_id: str) -> ABTestRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_tests(
        self,
        test_variant: TestVariant | None = None,
        test_status: TestStatus | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[ABTestRecord]:
        results = list(self._records)
        if test_variant is not None:
            results = [r for r in results if r.test_variant == test_variant]
        if test_status is not None:
            results = [r for r in results if r.test_status == test_status]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        test_id: str,
        test_variant: TestVariant = TestVariant.CONTROL,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> ABTestAnalysis:
        analysis = ABTestAnalysis(
            test_id=test_id,
            test_variant=test_variant,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "ab_testing_orchestrator.analysis_added",
            test_id=test_id,
            test_variant=test_variant.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_distribution(self) -> dict[str, Any]:
        """Group by test_variant; return count and avg effect_size."""
        variant_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.test_variant.value
            variant_data.setdefault(key, []).append(r.effect_size)
        result: dict[str, Any] = {}
        for variant, sizes in variant_data.items():
            result[variant] = {
                "count": len(sizes),
                "avg_effect_size": round(sum(sizes) / len(sizes), 4),
            }
        return result

    def identify_severe_drifts(self) -> list[dict[str, Any]]:
        """Return records where effect_size > min_effect_size (significant tests)."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.effect_size > self._min_effect_size:
                results.append(
                    {
                        "record_id": r.id,
                        "test_id": r.test_id,
                        "test_variant": r.test_variant.value,
                        "effect_size": r.effect_size,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["effect_size"], reverse=True)

    def rank_by_severity(self) -> list[dict[str, Any]]:
        """Group by test_id, avg effect_size, sort descending."""
        test_sizes: dict[str, list[float]] = {}
        for r in self._records:
            test_sizes.setdefault(r.test_id, []).append(r.effect_size)
        results: list[dict[str, Any]] = []
        for test_id, sizes in test_sizes.items():
            results.append(
                {
                    "test_id": test_id,
                    "avg_effect_size": round(sum(sizes) / len(sizes), 4),
                }
            )
        results.sort(key=lambda x: x["avg_effect_size"], reverse=True)
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

    def generate_report(self) -> ABTestReport:
        by_variant: dict[str, int] = {}
        by_status: dict[str, int] = {}
        by_significance: dict[str, int] = {}
        for r in self._records:
            by_variant[r.test_variant.value] = by_variant.get(r.test_variant.value, 0) + 1
            by_status[r.test_status.value] = by_status.get(r.test_status.value, 0) + 1
            by_significance[r.significance_level.value] = (
                by_significance.get(r.significance_level.value, 0) + 1
            )
        significant_count = sum(1 for r in self._records if r.effect_size > self._min_effect_size)
        sizes = [r.effect_size for r in self._records]
        avg_effect_size = round(sum(sizes) / len(sizes), 4) if sizes else 0.0
        winners_list = self.identify_severe_drifts()
        top_winners = [o["test_id"] for o in winners_list[:5]]
        recs: list[str] = []
        if self._records and significant_count > 0:
            recs.append(
                f"{significant_count} test(s) showing significant effect (>{self._min_effect_size})"
            )
        if self._records and avg_effect_size <= self._min_effect_size:
            recs.append(
                f"Avg effect size {avg_effect_size} below minimum threshold "
                f"({self._min_effect_size})"
            )
        if not recs:
            recs.append("A/B testing results are within expected parameters")
        return ABTestReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            significant_count=significant_count,
            avg_effect_size=avg_effect_size,
            by_variant=by_variant,
            by_status=by_status,
            by_significance=by_significance,
            top_winners=top_winners,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("ab_testing_orchestrator.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        variant_dist: dict[str, int] = {}
        for r in self._records:
            key = r.test_variant.value
            variant_dist[key] = variant_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "min_effect_size": self._min_effect_size,
            "variant_distribution": variant_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_tests": len({r.test_id for r in self._records}),
        }
