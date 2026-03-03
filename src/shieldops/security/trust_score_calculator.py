"""Trust Score Calculator — calculate and manage zero trust scores across factors."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class TrustFactor(StrEnum):
    IDENTITY = "identity"
    DEVICE = "device"
    NETWORK = "network"
    BEHAVIOR = "behavior"
    CONTEXT = "context"


class ScoreCategory(StrEnum):
    FULL_TRUST = "full_trust"
    HIGH_TRUST = "high_trust"
    CONDITIONAL = "conditional"
    LOW_TRUST = "low_trust"
    ZERO_TRUST = "zero_trust"


class CalculationMethod(StrEnum):
    WEIGHTED = "weighted"
    ML_BASED = "ml_based"
    RULE_BASED = "rule_based"
    HYBRID = "hybrid"
    ADAPTIVE = "adaptive"


# --- Models ---


class TrustRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    trust_id: str = ""
    trust_factor: TrustFactor = TrustFactor.IDENTITY
    score_category: ScoreCategory = ScoreCategory.FULL_TRUST
    calculation_method: CalculationMethod = CalculationMethod.WEIGHTED
    trust_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class TrustAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    trust_id: str = ""
    trust_factor: TrustFactor = TrustFactor.IDENTITY
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class TrustScoreReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_trust_score: float = 0.0
    by_trust_factor: dict[str, int] = Field(default_factory=dict)
    by_score_category: dict[str, int] = Field(default_factory=dict)
    by_calculation_method: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class TrustScoreCalculator:
    """Calculate zero trust scores, track trust factors, and analyze trust posture."""

    def __init__(
        self,
        max_records: int = 200000,
        trust_gap_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._trust_gap_threshold = trust_gap_threshold
        self._records: list[TrustRecord] = []
        self._analyses: list[TrustAnalysis] = []
        logger.info(
            "trust_score_calculator.initialized",
            max_records=max_records,
            trust_gap_threshold=trust_gap_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_trust(
        self,
        trust_id: str,
        trust_factor: TrustFactor = TrustFactor.IDENTITY,
        score_category: ScoreCategory = ScoreCategory.FULL_TRUST,
        calculation_method: CalculationMethod = CalculationMethod.WEIGHTED,
        trust_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> TrustRecord:
        record = TrustRecord(
            trust_id=trust_id,
            trust_factor=trust_factor,
            score_category=score_category,
            calculation_method=calculation_method,
            trust_score=trust_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "trust_score_calculator.trust_recorded",
            record_id=record.id,
            trust_id=trust_id,
            trust_factor=trust_factor.value,
            score_category=score_category.value,
        )
        return record

    def get_trust(self, record_id: str) -> TrustRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_trusts(
        self,
        trust_factor: TrustFactor | None = None,
        score_category: ScoreCategory | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[TrustRecord]:
        results = list(self._records)
        if trust_factor is not None:
            results = [r for r in results if r.trust_factor == trust_factor]
        if score_category is not None:
            results = [r for r in results if r.score_category == score_category]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        trust_id: str,
        trust_factor: TrustFactor = TrustFactor.IDENTITY,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> TrustAnalysis:
        analysis = TrustAnalysis(
            trust_id=trust_id,
            trust_factor=trust_factor,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "trust_score_calculator.analysis_added",
            trust_id=trust_id,
            trust_factor=trust_factor.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_trust_distribution(self) -> dict[str, Any]:
        """Group by trust_factor; return count and avg trust_score."""
        factor_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.trust_factor.value
            factor_data.setdefault(key, []).append(r.trust_score)
        result: dict[str, Any] = {}
        for factor, scores in factor_data.items():
            result[factor] = {
                "count": len(scores),
                "avg_trust_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_trust_gaps(self) -> list[dict[str, Any]]:
        """Return records where trust_score < trust_gap_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.trust_score < self._trust_gap_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "trust_id": r.trust_id,
                        "trust_factor": r.trust_factor.value,
                        "trust_score": r.trust_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["trust_score"])

    def rank_by_trust(self) -> list[dict[str, Any]]:
        """Group by service, avg trust_score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.trust_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_trust_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_trust_score"])
        return results

    def detect_trust_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> TrustScoreReport:
        by_trust_factor: dict[str, int] = {}
        by_score_category: dict[str, int] = {}
        by_calculation_method: dict[str, int] = {}
        for r in self._records:
            by_trust_factor[r.trust_factor.value] = by_trust_factor.get(r.trust_factor.value, 0) + 1
            by_score_category[r.score_category.value] = (
                by_score_category.get(r.score_category.value, 0) + 1
            )
            by_calculation_method[r.calculation_method.value] = (
                by_calculation_method.get(r.calculation_method.value, 0) + 1
            )
        gap_count = sum(1 for r in self._records if r.trust_score < self._trust_gap_threshold)
        scores = [r.trust_score for r in self._records]
        avg_trust_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_trust_gaps()
        top_gaps = [o["trust_id"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(
                f"{gap_count} trust record(s) below trust threshold ({self._trust_gap_threshold})"
            )
        if self._records and avg_trust_score < self._trust_gap_threshold:
            recs.append(
                f"Avg trust score {avg_trust_score} below threshold ({self._trust_gap_threshold})"
            )
        if not recs:
            recs.append("Trust score posture is healthy")
        return TrustScoreReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_trust_score=avg_trust_score,
            by_trust_factor=by_trust_factor,
            by_score_category=by_score_category,
            by_calculation_method=by_calculation_method,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("trust_score_calculator.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        factor_dist: dict[str, int] = {}
        for r in self._records:
            key = r.trust_factor.value
            factor_dist[key] = factor_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "trust_gap_threshold": self._trust_gap_threshold,
            "trust_factor_distribution": factor_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
