"""Merge Risk Assessor — assess merge risk, track assessments, and detect trends."""

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
    CHANGE_SIZE = "change_size"
    TEST_COVERAGE = "test_coverage"
    FILE_COMPLEXITY = "file_complexity"
    REVIEWER_FAMILIARITY = "reviewer_familiarity"
    DEPLOYMENT_WINDOW = "deployment_window"


class RiskLevel(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    MINIMAL = "minimal"


class MergeOutcome(StrEnum):
    CLEAN = "clean"
    CONFLICT_RESOLVED = "conflict_resolved"
    REVERTED = "reverted"
    CAUSED_INCIDENT = "caused_incident"
    DELAYED = "delayed"


# --- Models ---


class MergeRiskRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    merge_id: str = ""
    risk_factor: RiskFactor = RiskFactor.CHANGE_SIZE
    risk_level: RiskLevel = RiskLevel.LOW
    merge_outcome: MergeOutcome = MergeOutcome.CLEAN
    risk_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class RiskAssessment(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    merge_id: str = ""
    risk_factor: RiskFactor = RiskFactor.CHANGE_SIZE
    value: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class MergeRiskReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_assessments: int = 0
    high_risk_merges: int = 0
    avg_risk_score: float = 0.0
    by_factor: dict[str, int] = Field(default_factory=dict)
    by_level: dict[str, int] = Field(default_factory=dict)
    by_outcome: dict[str, int] = Field(default_factory=dict)
    top_risky: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class MergeRiskAssessor:
    """Assess merge risk, identify patterns, and detect trends."""

    def __init__(
        self,
        max_records: int = 200000,
        max_risk_score: float = 70.0,
    ) -> None:
        self._max_records = max_records
        self._max_risk_score = max_risk_score
        self._records: list[MergeRiskRecord] = []
        self._assessments: list[RiskAssessment] = []
        logger.info(
            "merge_risk.initialized",
            max_records=max_records,
            max_risk_score=max_risk_score,
        )

    # -- record / get / list ------------------------------------------------

    def record_merge(
        self,
        merge_id: str,
        risk_factor: RiskFactor = RiskFactor.CHANGE_SIZE,
        risk_level: RiskLevel = RiskLevel.LOW,
        merge_outcome: MergeOutcome = MergeOutcome.CLEAN,
        risk_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> MergeRiskRecord:
        record = MergeRiskRecord(
            merge_id=merge_id,
            risk_factor=risk_factor,
            risk_level=risk_level,
            merge_outcome=merge_outcome,
            risk_score=risk_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "merge_risk.merge_recorded",
            record_id=record.id,
            merge_id=merge_id,
            risk_factor=risk_factor.value,
            risk_level=risk_level.value,
        )
        return record

    def get_merge(self, record_id: str) -> MergeRiskRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_merges(
        self,
        factor: RiskFactor | None = None,
        level: RiskLevel | None = None,
        service: str | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[MergeRiskRecord]:
        results = list(self._records)
        if factor is not None:
            results = [r for r in results if r.risk_factor == factor]
        if level is not None:
            results = [r for r in results if r.risk_level == level]
        if service is not None:
            results = [r for r in results if r.service == service]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_assessment(
        self,
        merge_id: str,
        risk_factor: RiskFactor = RiskFactor.CHANGE_SIZE,
        value: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> RiskAssessment:
        assessment = RiskAssessment(
            merge_id=merge_id,
            risk_factor=risk_factor,
            value=value,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._assessments.append(assessment)
        if len(self._assessments) > self._max_records:
            self._assessments = self._assessments[-self._max_records :]
        logger.info(
            "merge_risk.assessment_added",
            merge_id=merge_id,
            risk_factor=risk_factor.value,
            value=value,
        )
        return assessment

    # -- domain operations --------------------------------------------------

    def analyze_merge_risk_patterns(self) -> dict[str, Any]:
        """Group by factor; return count and avg risk score per factor."""
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

    def identify_high_risk_merges(self) -> list[dict[str, Any]]:
        """Return records where level == CRITICAL or HIGH."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.risk_level in (
                RiskLevel.CRITICAL,
                RiskLevel.HIGH,
            ):
                results.append(
                    {
                        "record_id": r.id,
                        "merge_id": r.merge_id,
                        "risk_factor": r.risk_factor.value,
                        "risk_level": r.risk_level.value,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_risk_score(self) -> list[dict[str, Any]]:
        """Group by service, total records, sort descending by avg score."""
        service_data: dict[str, list[float]] = {}
        for r in self._records:
            service_data.setdefault(r.service, []).append(r.risk_score)
        results: list[dict[str, Any]] = []
        for service, scores in service_data.items():
            results.append(
                {
                    "service": service,
                    "record_count": len(scores),
                    "avg_risk_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_risk_score"], reverse=True)
        return results

    def detect_risk_trends(self) -> dict[str, Any]:
        """Split-half on value; delta threshold 5.0."""
        if len(self._assessments) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        values = [a.value for a in self._assessments]
        mid = len(values) // 2
        first_half = values[:mid]
        second_half = values[mid:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        delta = round(avg_second - avg_first, 2)
        if abs(delta) < 5.0:
            trend = "stable"
        elif delta > 0:
            trend = "increasing"
        else:
            trend = "decreasing"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> MergeRiskReport:
        by_factor: dict[str, int] = {}
        by_level: dict[str, int] = {}
        by_outcome: dict[str, int] = {}
        for r in self._records:
            by_factor[r.risk_factor.value] = by_factor.get(r.risk_factor.value, 0) + 1
            by_level[r.risk_level.value] = by_level.get(r.risk_level.value, 0) + 1
            by_outcome[r.merge_outcome.value] = by_outcome.get(r.merge_outcome.value, 0) + 1
        high_risk_count = sum(
            1 for r in self._records if r.risk_level in (RiskLevel.CRITICAL, RiskLevel.HIGH)
        )
        scores = [r.risk_score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        rankings = self.rank_by_risk_score()
        top_risky = [rk["service"] for rk in rankings[:5]]
        recs: list[str] = []
        above_threshold = sum(1 for r in self._records if r.risk_score > self._max_risk_score)
        above_rate = round(above_threshold / len(self._records) * 100, 2) if self._records else 0.0
        if above_rate > 20.0:
            recs.append(f"High risk rate {above_rate}% exceeds threshold ({self._max_risk_score})")
        if high_risk_count > 0:
            recs.append(f"{high_risk_count} high-risk merge(s) detected — review risk")
        if not recs:
            recs.append("Merge risk levels are acceptable")
        return MergeRiskReport(
            total_records=len(self._records),
            total_assessments=len(self._assessments),
            high_risk_merges=high_risk_count,
            avg_risk_score=avg_score,
            by_factor=by_factor,
            by_level=by_level,
            by_outcome=by_outcome,
            top_risky=top_risky,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._assessments.clear()
        logger.info("merge_risk.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        factor_dist: dict[str, int] = {}
        for r in self._records:
            key = r.risk_factor.value
            factor_dist[key] = factor_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_assessments": len(self._assessments),
            "max_risk_score": self._max_risk_score,
            "factor_distribution": factor_dist,
            "unique_services": len({r.service for r in self._records}),
            "unique_merges": len({r.merge_id for r in self._records}),
        }
