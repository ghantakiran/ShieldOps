"""Change Risk Predictor — predict and analyze risk for infrastructure changes."""

from __future__ import annotations

import time
from enum import StrEnum
from typing import Any
from uuid import uuid4

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class RiskLevel(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NEGLIGIBLE = "negligible"


class RiskFactor(StrEnum):
    CODE_COMPLEXITY = "code_complexity"
    BLAST_RADIUS = "blast_radius"
    DEPLOYMENT_HISTORY = "deployment_history"
    TEST_COVERAGE = "test_coverage"
    TEAM_EXPERIENCE = "team_experience"


class PredictionAccuracy(StrEnum):
    EXACT = "exact"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    INACCURATE = "inaccurate"


# --- Models ---


class RiskPredictionRecord(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    change_id: str = ""
    risk_level: RiskLevel = RiskLevel.MEDIUM
    risk_factor: RiskFactor = RiskFactor.CODE_COMPLEXITY
    accuracy: PredictionAccuracy = PredictionAccuracy.MODERATE
    risk_score: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class RiskFactorDetail(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    change_id: str = ""
    risk_factor: RiskFactor = RiskFactor.CODE_COMPLEXITY
    factor_score: float = 0.0
    weight: float = 1.0
    notes: str = ""
    created_at: float = Field(default_factory=time.time)


class RiskPredictorReport(BaseModel):
    total_predictions: int = 0
    total_factors: int = 0
    avg_risk_score: float = 0.0
    by_risk_level: dict[str, int] = Field(default_factory=dict)
    by_risk_factor: dict[str, int] = Field(default_factory=dict)
    high_risk_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class ChangeRiskPredictor:
    """Predict and analyze risk for infrastructure changes."""

    def __init__(
        self,
        max_records: int = 200000,
        max_risk_threshold: float = 75.0,
    ) -> None:
        self._max_records = max_records
        self._max_risk_threshold = max_risk_threshold
        self._records: list[RiskPredictionRecord] = []
        self._factors: list[RiskFactorDetail] = []
        logger.info(
            "risk_predictor.initialized",
            max_records=max_records,
            max_risk_threshold=max_risk_threshold,
        )

    # -- record / get / list ---------------------------------------------

    def record_prediction(
        self,
        change_id: str = "",
        risk_level: RiskLevel = RiskLevel.MEDIUM,
        risk_factor: RiskFactor = RiskFactor.CODE_COMPLEXITY,
        accuracy: PredictionAccuracy = PredictionAccuracy.MODERATE,
        risk_score: float = 0.0,
        details: str = "",
    ) -> RiskPredictionRecord:
        record = RiskPredictionRecord(
            change_id=change_id,
            risk_level=risk_level,
            risk_factor=risk_factor,
            accuracy=accuracy,
            risk_score=risk_score,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "risk_predictor.prediction_recorded",
            record_id=record.id,
            change_id=change_id,
            risk_level=risk_level.value,
        )
        return record

    def get_prediction(self, record_id: str) -> RiskPredictionRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_predictions(
        self,
        risk_level: RiskLevel | None = None,
        risk_factor: RiskFactor | None = None,
        limit: int = 50,
    ) -> list[RiskPredictionRecord]:
        results = list(self._records)
        if risk_level is not None:
            results = [r for r in results if r.risk_level == risk_level]
        if risk_factor is not None:
            results = [r for r in results if r.risk_factor == risk_factor]
        return results[-limit:]

    def add_factor(
        self,
        change_id: str = "",
        risk_factor: RiskFactor = RiskFactor.CODE_COMPLEXITY,
        factor_score: float = 0.0,
        weight: float = 1.0,
        notes: str = "",
    ) -> RiskFactorDetail:
        detail = RiskFactorDetail(
            change_id=change_id,
            risk_factor=risk_factor,
            factor_score=factor_score,
            weight=weight,
            notes=notes,
        )
        self._factors.append(detail)
        if len(self._factors) > self._max_records:
            self._factors = self._factors[-self._max_records :]
        logger.info(
            "risk_predictor.factor_added",
            change_id=change_id,
            risk_factor=risk_factor.value,
        )
        return detail

    # -- domain operations -----------------------------------------------

    def analyze_prediction_accuracy(self, accuracy: PredictionAccuracy) -> dict[str, Any]:
        """Analyze predictions for a specific accuracy level."""
        records = [r for r in self._records if r.accuracy == accuracy]
        if not records:
            return {"accuracy": accuracy.value, "status": "no_data"}
        avg_risk = round(sum(r.risk_score for r in records) / len(records), 2)
        high_risk = sum(1 for r in records if r.risk_level in {RiskLevel.CRITICAL, RiskLevel.HIGH})
        return {
            "accuracy": accuracy.value,
            "total": len(records),
            "avg_risk_score": avg_risk,
            "high_risk_count": high_risk,
            "exceeds_threshold": avg_risk > self._max_risk_threshold,
        }

    def identify_high_risk_changes(self) -> list[dict[str, Any]]:
        """Find changes with critical or high risk levels."""
        high_levels = {RiskLevel.CRITICAL, RiskLevel.HIGH}
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.risk_level in high_levels:
                results.append(
                    {
                        "change_id": r.change_id,
                        "risk_level": r.risk_level.value,
                        "risk_factor": r.risk_factor.value,
                        "risk_score": r.risk_score,
                        "accuracy": r.accuracy.value,
                    }
                )
        results.sort(key=lambda x: x["risk_score"], reverse=True)
        return results

    def rank_by_risk_score(self) -> list[dict[str, Any]]:
        """Rank predictions by risk score descending."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            results.append(
                {
                    "change_id": r.change_id,
                    "risk_score": r.risk_score,
                    "risk_level": r.risk_level.value,
                    "risk_factor": r.risk_factor.value,
                }
            )
        results.sort(key=lambda x: x["risk_score"], reverse=True)
        return results

    def detect_risk_patterns(self) -> list[dict[str, Any]]:
        """Detect risk score patterns per change using sufficient historical data."""
        change_records: dict[str, list[RiskPredictionRecord]] = {}
        for r in self._records:
            change_records.setdefault(r.change_id, []).append(r)
        results: list[dict[str, Any]] = []
        for cid, recs in change_records.items():
            if len(recs) > 3:
                scores = [r.risk_score for r in recs]
                pattern = "escalating" if scores[-1] > scores[0] else "improving"
                results.append(
                    {
                        "change_id": cid,
                        "record_count": len(recs),
                        "risk_pattern": pattern,
                    }
                )
        return results

    # -- report / stats --------------------------------------------------

    def generate_report(self) -> RiskPredictorReport:
        by_level: dict[str, int] = {}
        by_factor: dict[str, int] = {}
        for r in self._records:
            by_level[r.risk_level.value] = by_level.get(r.risk_level.value, 0) + 1
            by_factor[r.risk_factor.value] = by_factor.get(r.risk_factor.value, 0) + 1
        avg_risk = (
            round(sum(r.risk_score for r in self._records) / len(self._records), 2)
            if self._records
            else 0.0
        )
        high_levels = {RiskLevel.CRITICAL, RiskLevel.HIGH}
        high_risk_count = sum(1 for r in self._records if r.risk_level in high_levels)
        recs: list[str] = []
        if avg_risk > self._max_risk_threshold:
            recs.append(
                f"Average risk score {avg_risk} exceeds threshold of {self._max_risk_threshold}"
            )
        if high_risk_count > 0:
            recs.append(f"{high_risk_count} critical/high risk change(s) detected")
        if not recs:
            recs.append("Change risk levels within acceptable threshold")
        return RiskPredictorReport(
            total_predictions=len(self._records),
            total_factors=len(self._factors),
            avg_risk_score=avg_risk,
            by_risk_level=by_level,
            by_risk_factor=by_factor,
            high_risk_count=high_risk_count,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._factors.clear()
        logger.info("risk_predictor.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        factor_dist: dict[str, int] = {}
        for r in self._records:
            key = r.risk_factor.value
            factor_dist[key] = factor_dist.get(key, 0) + 1
        return {
            "total_predictions": len(self._records),
            "total_factors": len(self._factors),
            "max_risk_threshold": self._max_risk_threshold,
            "risk_factor_distribution": factor_dist,
            "unique_changes": len({r.change_id for r in self._records}),
        }
