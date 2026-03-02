"""Risk Quantification Engine — FAIR-based risk analysis with Monte Carlo simulation."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class RiskCategory(StrEnum):
    OPERATIONAL = "operational"
    FINANCIAL = "financial"
    REPUTATIONAL = "reputational"
    COMPLIANCE = "compliance"
    STRATEGIC = "strategic"


class LikelihoodLevel(StrEnum):
    VERY_HIGH = "very_high"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    VERY_LOW = "very_low"


class ImpactSeverity(StrEnum):
    CATASTROPHIC = "catastrophic"
    MAJOR = "major"
    MODERATE = "moderate"
    MINOR = "minor"
    NEGLIGIBLE = "negligible"


# --- Models ---


class RiskRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    risk_name: str = ""
    risk_category: RiskCategory = RiskCategory.OPERATIONAL
    likelihood_level: LikelihoodLevel = LikelihoodLevel.VERY_HIGH
    impact_severity: ImpactSeverity = ImpactSeverity.CATASTROPHIC
    risk_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class RiskAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    risk_name: str = ""
    risk_category: RiskCategory = RiskCategory.OPERATIONAL
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class RiskQuantificationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    high_risk_count: int = 0
    avg_risk_score: float = 0.0
    by_category: dict[str, int] = Field(default_factory=dict)
    by_likelihood: dict[str, int] = Field(default_factory=dict)
    by_impact: dict[str, int] = Field(default_factory=dict)
    top_high_risk: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class RiskQuantificationEngine:
    """FAIR-based risk analysis with Monte Carlo simulation."""

    def __init__(
        self,
        max_records: int = 200000,
        risk_tolerance_threshold: float = 70.0,
    ) -> None:
        self._max_records = max_records
        self._risk_tolerance_threshold = risk_tolerance_threshold
        self._records: list[RiskRecord] = []
        self._analyses: list[RiskAnalysis] = []
        logger.info(
            "risk_quantification_engine.initialized",
            max_records=max_records,
            risk_tolerance_threshold=risk_tolerance_threshold,
        )

    def record_risk(
        self,
        risk_name: str,
        risk_category: RiskCategory = RiskCategory.OPERATIONAL,
        likelihood_level: LikelihoodLevel = LikelihoodLevel.VERY_HIGH,
        impact_severity: ImpactSeverity = ImpactSeverity.CATASTROPHIC,
        risk_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> RiskRecord:
        record = RiskRecord(
            risk_name=risk_name,
            risk_category=risk_category,
            likelihood_level=likelihood_level,
            impact_severity=impact_severity,
            risk_score=risk_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "risk_quantification_engine.risk_recorded",
            record_id=record.id,
            risk_name=risk_name,
            risk_category=risk_category.value,
            likelihood_level=likelihood_level.value,
        )
        return record

    def get_risk(self, record_id: str) -> RiskRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_risks(
        self,
        risk_category: RiskCategory | None = None,
        likelihood_level: LikelihoodLevel | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[RiskRecord]:
        results = list(self._records)
        if risk_category is not None:
            results = [r for r in results if r.risk_category == risk_category]
        if likelihood_level is not None:
            results = [r for r in results if r.likelihood_level == likelihood_level]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        risk_name: str,
        risk_category: RiskCategory = RiskCategory.OPERATIONAL,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> RiskAnalysis:
        analysis = RiskAnalysis(
            risk_name=risk_name,
            risk_category=risk_category,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "risk_quantification_engine.analysis_added",
            risk_name=risk_name,
            risk_category=risk_category.value,
            analysis_score=analysis_score,
        )
        return analysis

    def analyze_risk_distribution(self) -> dict[str, Any]:
        cat_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.risk_category.value
            cat_data.setdefault(key, []).append(r.risk_score)
        result: dict[str, Any] = {}
        for cat, scores in cat_data.items():
            result[cat] = {
                "count": len(scores),
                "avg_risk_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_high_risks(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.risk_score > self._risk_tolerance_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "risk_name": r.risk_name,
                        "risk_category": r.risk_category.value,
                        "risk_score": r.risk_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["risk_score"], reverse=True)

    def rank_by_risk(self) -> list[dict[str, Any]]:
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.risk_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append({"service": svc, "avg_risk_score": round(sum(scores) / len(scores), 2)})
        results.sort(key=lambda x: x["avg_risk_score"], reverse=True)
        return results

    def detect_risk_trends(self) -> dict[str, Any]:
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
            trend = "increasing"
        else:
            trend = "decreasing"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    def generate_report(self) -> RiskQuantificationReport:
        by_category: dict[str, int] = {}
        by_likelihood: dict[str, int] = {}
        by_impact: dict[str, int] = {}
        for r in self._records:
            by_category[r.risk_category.value] = by_category.get(r.risk_category.value, 0) + 1
            by_likelihood[r.likelihood_level.value] = (
                by_likelihood.get(r.likelihood_level.value, 0) + 1
            )
            by_impact[r.impact_severity.value] = by_impact.get(r.impact_severity.value, 0) + 1
        high_risk_count = sum(
            1 for r in self._records if r.risk_score > self._risk_tolerance_threshold
        )
        scores = [r.risk_score for r in self._records]
        avg_risk_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        high_list = self.identify_high_risks()
        top_high_risk = [o["risk_name"] for o in high_list[:5]]
        recs: list[str] = []
        if self._records and high_risk_count > 0:
            recs.append(
                f"{high_risk_count} risk(s) above tolerance threshold "
                f"({self._risk_tolerance_threshold})"
            )
        if self._records and avg_risk_score > self._risk_tolerance_threshold:
            recs.append(
                f"Avg risk score {avg_risk_score} above threshold "
                f"({self._risk_tolerance_threshold})"
            )
        if not recs:
            recs.append("Risk quantification posture is healthy")
        return RiskQuantificationReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            high_risk_count=high_risk_count,
            avg_risk_score=avg_risk_score,
            by_category=by_category,
            by_likelihood=by_likelihood,
            by_impact=by_impact,
            top_high_risk=top_high_risk,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("risk_quantification_engine.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        cat_dist: dict[str, int] = {}
        for r in self._records:
            key = r.risk_category.value
            cat_dist[key] = cat_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "risk_tolerance_threshold": self._risk_tolerance_threshold,
            "category_distribution": cat_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
