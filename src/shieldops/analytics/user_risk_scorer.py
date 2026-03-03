"""User Risk Scorer — score and track user risk based on multiple factors."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class RiskFactor(StrEnum):
    ACCESS_PATTERN = "access_pattern"
    DATA_HANDLING = "data_handling"
    AUTHENTICATION_ANOMALY = "authentication_anomaly"
    POLICY_VIOLATION = "policy_violation"
    BEHAVIORAL_CHANGE = "behavioral_change"


class RiskLevel(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    MINIMAL = "minimal"


class ScoringModel(StrEnum):
    RULE_BASED = "rule_based"
    ML_BASED = "ml_based"
    HYBRID = "hybrid"
    PEER_COMPARISON = "peer_comparison"
    CONTEXTUAL = "contextual"


# --- Models ---


class UserRiskRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_name: str = ""
    risk_factor: RiskFactor = RiskFactor.ACCESS_PATTERN
    risk_level: RiskLevel = RiskLevel.MINIMAL
    scoring_model: ScoringModel = ScoringModel.RULE_BASED
    risk_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class UserRiskAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_name: str = ""
    risk_factor: RiskFactor = RiskFactor.ACCESS_PATTERN
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class UserRiskReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_risk_score: float = 0.0
    by_risk_factor: dict[str, int] = Field(default_factory=dict)
    by_risk_level: dict[str, int] = Field(default_factory=dict)
    by_scoring_model: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class UserRiskScorer:
    """Score and track user risk based on multiple factors and scoring models."""

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[UserRiskRecord] = []
        self._analyses: list[UserRiskAnalysis] = []
        logger.info(
            "user_risk_scorer.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_risk(
        self,
        user_name: str,
        risk_factor: RiskFactor = RiskFactor.ACCESS_PATTERN,
        risk_level: RiskLevel = RiskLevel.MINIMAL,
        scoring_model: ScoringModel = ScoringModel.RULE_BASED,
        risk_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> UserRiskRecord:
        record = UserRiskRecord(
            user_name=user_name,
            risk_factor=risk_factor,
            risk_level=risk_level,
            scoring_model=scoring_model,
            risk_score=risk_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "user_risk_scorer.risk_recorded",
            record_id=record.id,
            user_name=user_name,
            risk_factor=risk_factor.value,
            risk_level=risk_level.value,
        )
        return record

    def get_record(self, record_id: str) -> UserRiskRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        risk_factor: RiskFactor | None = None,
        risk_level: RiskLevel | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[UserRiskRecord]:
        results = list(self._records)
        if risk_factor is not None:
            results = [r for r in results if r.risk_factor == risk_factor]
        if risk_level is not None:
            results = [r for r in results if r.risk_level == risk_level]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        user_name: str,
        risk_factor: RiskFactor = RiskFactor.ACCESS_PATTERN,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> UserRiskAnalysis:
        analysis = UserRiskAnalysis(
            user_name=user_name,
            risk_factor=risk_factor,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "user_risk_scorer.analysis_added",
            user_name=user_name,
            risk_factor=risk_factor.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_distribution(self) -> dict[str, Any]:
        """Group by risk_factor; return count and avg risk_score."""
        factor_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.risk_factor.value
            factor_data.setdefault(key, []).append(r.risk_score)
        result: dict[str, Any] = {}
        for factor, scores in factor_data.items():
            result[factor] = {
                "count": len(scores),
                "avg_risk_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_gaps(self) -> list[dict[str, Any]]:
        """Return records where risk_score < threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.risk_score < self._threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "user_name": r.user_name,
                        "risk_factor": r.risk_factor.value,
                        "risk_score": r.risk_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["risk_score"])

    def rank_by_score(self) -> list[dict[str, Any]]:
        """Group by service, avg risk_score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.risk_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_risk_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_risk_score"])
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

    def generate_report(self) -> UserRiskReport:
        by_risk_factor: dict[str, int] = {}
        by_risk_level: dict[str, int] = {}
        by_scoring_model: dict[str, int] = {}
        for r in self._records:
            by_risk_factor[r.risk_factor.value] = by_risk_factor.get(r.risk_factor.value, 0) + 1
            by_risk_level[r.risk_level.value] = by_risk_level.get(r.risk_level.value, 0) + 1
            by_scoring_model[r.scoring_model.value] = (
                by_scoring_model.get(r.scoring_model.value, 0) + 1
            )
        gap_count = sum(1 for r in self._records if r.risk_score < self._threshold)
        scores = [r.risk_score for r in self._records]
        avg_risk_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_gaps()
        top_gaps = [o["user_name"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} user(s) below risk threshold ({self._threshold})")
        if self._records and avg_risk_score < self._threshold:
            recs.append(f"Avg risk score {avg_risk_score} below threshold ({self._threshold})")
        if not recs:
            recs.append("User risk scoring is healthy")
        return UserRiskReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_risk_score=avg_risk_score,
            by_risk_factor=by_risk_factor,
            by_risk_level=by_risk_level,
            by_scoring_model=by_scoring_model,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("user_risk_scorer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        risk_factor_dist: dict[str, int] = {}
        for r in self._records:
            key = r.risk_factor.value
            risk_factor_dist[key] = risk_factor_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "risk_factor_distribution": risk_factor_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
