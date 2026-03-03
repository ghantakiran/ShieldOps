"""Technical Debt Predictor — predict and prioritize technical debt payoff."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class DebtCategory(StrEnum):
    CODE_QUALITY = "code_quality"
    ARCHITECTURE = "architecture"
    TESTING = "testing"
    DOCUMENTATION = "documentation"
    DEPENDENCY = "dependency"


class DebtSeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    TRIVIAL = "trivial"


class PayoffStrategy(StrEnum):
    IMMEDIATE = "immediate"
    INCREMENTAL = "incremental"
    PLANNED = "planned"
    DEFERRED = "deferred"
    ACCEPTED = "accepted"


# --- Models ---


class DebtRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service: str = ""
    team: str = ""
    debt_category: DebtCategory = DebtCategory.CODE_QUALITY
    debt_severity: DebtSeverity = DebtSeverity.LOW
    payoff_strategy: PayoffStrategy = PayoffStrategy.PLANNED
    debt_score: float = 0.0
    estimated_hours: float = 0.0
    created_at: float = Field(default_factory=time.time)


class DebtAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service: str = ""
    debt_category: DebtCategory = DebtCategory.CODE_QUALITY
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class DebtReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_debt_score: float = 0.0
    by_category: dict[str, int] = Field(default_factory=dict)
    by_severity: dict[str, int] = Field(default_factory=dict)
    by_strategy: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class TechnicalDebtPredictor:
    """Predict technical debt accumulation and recommend payoff strategies."""

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[DebtRecord] = []
        self._analyses: list[DebtAnalysis] = []
        logger.info(
            "technical_debt_predictor.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_debt(
        self,
        service: str,
        team: str = "",
        debt_category: DebtCategory = DebtCategory.CODE_QUALITY,
        debt_severity: DebtSeverity = DebtSeverity.LOW,
        payoff_strategy: PayoffStrategy = PayoffStrategy.PLANNED,
        debt_score: float = 0.0,
        estimated_hours: float = 0.0,
    ) -> DebtRecord:
        record = DebtRecord(
            service=service,
            team=team,
            debt_category=debt_category,
            debt_severity=debt_severity,
            payoff_strategy=payoff_strategy,
            debt_score=debt_score,
            estimated_hours=estimated_hours,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "technical_debt_predictor.debt_recorded",
            record_id=record.id,
            service=service,
            debt_category=debt_category.value,
            debt_severity=debt_severity.value,
        )
        return record

    def get_debt(self, record_id: str) -> DebtRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_debts(
        self,
        debt_category: DebtCategory | None = None,
        debt_severity: DebtSeverity | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[DebtRecord]:
        results = list(self._records)
        if debt_category is not None:
            results = [r for r in results if r.debt_category == debt_category]
        if debt_severity is not None:
            results = [r for r in results if r.debt_severity == debt_severity]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        service: str,
        debt_category: DebtCategory = DebtCategory.CODE_QUALITY,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> DebtAnalysis:
        analysis = DebtAnalysis(
            service=service,
            debt_category=debt_category,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "technical_debt_predictor.analysis_added",
            service=service,
            debt_category=debt_category.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_distribution(self) -> dict[str, Any]:
        """Group by debt_category; return count and avg debt_score."""
        cat_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.debt_category.value
            cat_data.setdefault(key, []).append(r.debt_score)
        result: dict[str, Any] = {}
        for cat, scores in cat_data.items():
            result[cat] = {
                "count": len(scores),
                "avg_debt_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_debt_gaps(self) -> list[dict[str, Any]]:
        """Return records where debt_score >= threshold (high debt)."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.debt_score >= self._threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "service": r.service,
                        "debt_category": r.debt_category.value,
                        "debt_score": r.debt_score,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["debt_score"], reverse=True)

    def rank_by_debt(self) -> list[dict[str, Any]]:
        """Group by service, avg debt_score, sort descending."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.debt_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_debt_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_debt_score"], reverse=True)
        return results

    def detect_debt_trends(self) -> dict[str, Any]:
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
            trend = "worsening"
        else:
            trend = "improving"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> DebtReport:
        by_category: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        by_strategy: dict[str, int] = {}
        for r in self._records:
            by_category[r.debt_category.value] = by_category.get(r.debt_category.value, 0) + 1
            by_severity[r.debt_severity.value] = by_severity.get(r.debt_severity.value, 0) + 1
            by_strategy[r.payoff_strategy.value] = by_strategy.get(r.payoff_strategy.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.debt_score >= self._threshold)
        scores = [r.debt_score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_debt_gaps()
        top_gaps = [o["service"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} service(s) above debt threshold ({self._threshold})")
        if self._records and avg_score >= self._threshold:
            recs.append(f"Avg debt score {avg_score} at or above threshold ({self._threshold})")
        if not recs:
            recs.append("Technical debt is at healthy levels")
        return DebtReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_debt_score=avg_score,
            by_category=by_category,
            by_severity=by_severity,
            by_strategy=by_strategy,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("technical_debt_predictor.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        cat_dist: dict[str, int] = {}
        for r in self._records:
            key = r.debt_category.value
            cat_dist[key] = cat_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "category_distribution": cat_dist,
            "unique_services": len({r.service for r in self._records}),
            "unique_teams": len({r.team for r in self._records}),
        }
