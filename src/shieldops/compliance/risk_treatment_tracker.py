"""Risk Treatment Tracker — track risk treatment decisions and residual risk."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class TreatmentStrategy(StrEnum):
    MITIGATE = "mitigate"
    ACCEPT = "accept"
    TRANSFER = "transfer"
    AVOID = "avoid"
    SHARE = "share"


class TreatmentStatus(StrEnum):
    IMPLEMENTED = "implemented"
    IN_PROGRESS = "in_progress"
    PLANNED = "planned"
    DEFERRED = "deferred"
    REJECTED = "rejected"


class ResidualRiskLevel(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NEGLIGIBLE = "negligible"


# --- Models ---


class TreatmentRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    risk_name: str = ""
    treatment_strategy: TreatmentStrategy = TreatmentStrategy.MITIGATE
    treatment_status: TreatmentStatus = TreatmentStatus.IMPLEMENTED
    residual_risk_level: ResidualRiskLevel = ResidualRiskLevel.CRITICAL
    residual_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class TreatmentAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    risk_name: str = ""
    treatment_strategy: TreatmentStrategy = TreatmentStrategy.MITIGATE
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class TreatmentReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    high_residual_count: int = 0
    avg_residual_score: float = 0.0
    by_strategy: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    by_risk_level: dict[str, int] = Field(default_factory=dict)
    top_high_residual: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class RiskTreatmentTracker:
    """Track risk treatment decisions and monitor residual risk levels."""

    def __init__(
        self,
        max_records: int = 200000,
        residual_risk_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._residual_risk_threshold = residual_risk_threshold
        self._records: list[TreatmentRecord] = []
        self._analyses: list[TreatmentAnalysis] = []
        logger.info(
            "risk_treatment_tracker.initialized",
            max_records=max_records,
            residual_risk_threshold=residual_risk_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_treatment(
        self,
        risk_name: str,
        treatment_strategy: TreatmentStrategy = TreatmentStrategy.MITIGATE,
        treatment_status: TreatmentStatus = TreatmentStatus.IMPLEMENTED,
        residual_risk_level: ResidualRiskLevel = ResidualRiskLevel.CRITICAL,
        residual_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> TreatmentRecord:
        record = TreatmentRecord(
            risk_name=risk_name,
            treatment_strategy=treatment_strategy,
            treatment_status=treatment_status,
            residual_risk_level=residual_risk_level,
            residual_score=residual_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "risk_treatment_tracker.treatment_recorded",
            record_id=record.id,
            risk_name=risk_name,
            treatment_strategy=treatment_strategy.value,
            treatment_status=treatment_status.value,
        )
        return record

    def get_treatment(self, record_id: str) -> TreatmentRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_treatments(
        self,
        treatment_strategy: TreatmentStrategy | None = None,
        treatment_status: TreatmentStatus | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[TreatmentRecord]:
        results = list(self._records)
        if treatment_strategy is not None:
            results = [r for r in results if r.treatment_strategy == treatment_strategy]
        if treatment_status is not None:
            results = [r for r in results if r.treatment_status == treatment_status]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        risk_name: str,
        treatment_strategy: TreatmentStrategy = TreatmentStrategy.MITIGATE,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> TreatmentAnalysis:
        analysis = TreatmentAnalysis(
            risk_name=risk_name,
            treatment_strategy=treatment_strategy,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "risk_treatment_tracker.analysis_added",
            risk_name=risk_name,
            treatment_strategy=treatment_strategy.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_treatment_distribution(self) -> dict[str, Any]:
        """Group by treatment_strategy; return count and avg residual_score."""
        strategy_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.treatment_strategy.value
            strategy_data.setdefault(key, []).append(r.residual_score)
        result: dict[str, Any] = {}
        for strategy, scores in strategy_data.items():
            result[strategy] = {
                "count": len(scores),
                "avg_residual_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_high_residual_treatments(self) -> list[dict[str, Any]]:
        """Return records where residual_score > residual_risk_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.residual_score > self._residual_risk_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "risk_name": r.risk_name,
                        "treatment_strategy": r.treatment_strategy.value,
                        "residual_score": r.residual_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["residual_score"], reverse=True)

    def rank_by_residual(self) -> list[dict[str, Any]]:
        """Group by service, avg residual_score, sort descending (highest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.residual_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_residual_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_residual_score"], reverse=True)
        return results

    def detect_treatment_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> TreatmentReport:
        by_strategy: dict[str, int] = {}
        by_status: dict[str, int] = {}
        by_risk_level: dict[str, int] = {}
        for r in self._records:
            by_strategy[r.treatment_strategy.value] = (
                by_strategy.get(r.treatment_strategy.value, 0) + 1
            )
            by_status[r.treatment_status.value] = by_status.get(r.treatment_status.value, 0) + 1
            by_risk_level[r.residual_risk_level.value] = (
                by_risk_level.get(r.residual_risk_level.value, 0) + 1
            )
        high_residual_count = sum(
            1 for r in self._records if r.residual_score > self._residual_risk_threshold
        )
        scores = [r.residual_score for r in self._records]
        avg_residual_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        high_list = self.identify_high_residual_treatments()
        top_high_residual = [o["risk_name"] for o in high_list[:5]]
        recs: list[str] = []
        if self._records and high_residual_count > 0:
            recs.append(
                f"{high_residual_count} treatment(s) above residual risk threshold "
                f"({self._residual_risk_threshold})"
            )
        if self._records and avg_residual_score > self._residual_risk_threshold:
            recs.append(
                f"Avg residual score {avg_residual_score} above threshold "
                f"({self._residual_risk_threshold})"
            )
        if not recs:
            recs.append("Risk treatment residual levels are healthy")
        return TreatmentReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            high_residual_count=high_residual_count,
            avg_residual_score=avg_residual_score,
            by_strategy=by_strategy,
            by_status=by_status,
            by_risk_level=by_risk_level,
            top_high_residual=top_high_residual,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("risk_treatment_tracker.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        strategy_dist: dict[str, int] = {}
        for r in self._records:
            key = r.treatment_strategy.value
            strategy_dist[key] = strategy_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "residual_risk_threshold": self._residual_risk_threshold,
            "strategy_distribution": strategy_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
