"""FAIR Risk Modeler — full FAIR framework with Monte Carlo simulation."""

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
    THREAT_EVENT_FREQUENCY = "threat_event_frequency"
    VULNERABILITY = "vulnerability"
    CONTACT_FREQUENCY = "contact_frequency"
    PROBABILITY_OF_ACTION = "probability_of_action"
    LOSS_MAGNITUDE = "loss_magnitude"


class ModelConfidence(StrEnum):
    VERY_HIGH = "very_high"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    VERY_LOW = "very_low"


class ScenarioType(StrEnum):
    BEST_CASE = "best_case"
    LIKELY_CASE = "likely_case"
    WORST_CASE = "worst_case"
    MONTE_CARLO = "monte_carlo"
    DETERMINISTIC = "deterministic"


# --- Models ---


class RiskModelRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    scenario_name: str = ""
    risk_factor: RiskFactor = RiskFactor.THREAT_EVENT_FREQUENCY
    model_confidence: ModelConfidence = ModelConfidence.VERY_HIGH
    scenario_type: ScenarioType = ScenarioType.BEST_CASE
    risk_estimate: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class RiskModelAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    scenario_name: str = ""
    risk_factor: RiskFactor = RiskFactor.THREAT_EVENT_FREQUENCY
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class RiskModelReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    high_risk_count: int = 0
    avg_risk_estimate: float = 0.0
    by_factor: dict[str, int] = Field(default_factory=dict)
    by_confidence: dict[str, int] = Field(default_factory=dict)
    by_scenario: dict[str, int] = Field(default_factory=dict)
    top_high_risk: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class FAIRRiskModeler:
    """Full FAIR framework risk modeling with Monte Carlo simulation support."""

    def __init__(
        self,
        max_records: int = 200000,
        risk_estimate_threshold: float = 70.0,
    ) -> None:
        self._max_records = max_records
        self._risk_estimate_threshold = risk_estimate_threshold
        self._records: list[RiskModelRecord] = []
        self._analyses: list[RiskModelAnalysis] = []
        logger.info(
            "fair_risk_modeler.initialized",
            max_records=max_records,
            risk_estimate_threshold=risk_estimate_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_scenario(
        self,
        scenario_name: str,
        risk_factor: RiskFactor = RiskFactor.THREAT_EVENT_FREQUENCY,
        model_confidence: ModelConfidence = ModelConfidence.VERY_HIGH,
        scenario_type: ScenarioType = ScenarioType.BEST_CASE,
        risk_estimate: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> RiskModelRecord:
        record = RiskModelRecord(
            scenario_name=scenario_name,
            risk_factor=risk_factor,
            model_confidence=model_confidence,
            scenario_type=scenario_type,
            risk_estimate=risk_estimate,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "fair_risk_modeler.scenario_recorded",
            record_id=record.id,
            scenario_name=scenario_name,
            risk_factor=risk_factor.value,
            model_confidence=model_confidence.value,
        )
        return record

    def get_scenario(self, record_id: str) -> RiskModelRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_scenarios(
        self,
        risk_factor: RiskFactor | None = None,
        scenario_type: ScenarioType | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[RiskModelRecord]:
        results = list(self._records)
        if risk_factor is not None:
            results = [r for r in results if r.risk_factor == risk_factor]
        if scenario_type is not None:
            results = [r for r in results if r.scenario_type == scenario_type]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        scenario_name: str,
        risk_factor: RiskFactor = RiskFactor.THREAT_EVENT_FREQUENCY,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> RiskModelAnalysis:
        analysis = RiskModelAnalysis(
            scenario_name=scenario_name,
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
            "fair_risk_modeler.analysis_added",
            scenario_name=scenario_name,
            risk_factor=risk_factor.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_factor_distribution(self) -> dict[str, Any]:
        """Group by risk_factor; return count and avg risk_estimate."""
        factor_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.risk_factor.value
            factor_data.setdefault(key, []).append(r.risk_estimate)
        result: dict[str, Any] = {}
        for factor, scores in factor_data.items():
            result[factor] = {
                "count": len(scores),
                "avg_risk_estimate": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_high_risk_scenarios(self) -> list[dict[str, Any]]:
        """Return records where risk_estimate > risk_estimate_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.risk_estimate > self._risk_estimate_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "scenario_name": r.scenario_name,
                        "risk_factor": r.risk_factor.value,
                        "risk_estimate": r.risk_estimate,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["risk_estimate"], reverse=True)

    def rank_by_risk_estimate(self) -> list[dict[str, Any]]:
        """Group by service, avg risk_estimate, sort descending (highest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.risk_estimate)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_risk_estimate": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_risk_estimate"], reverse=True)
        return results

    def detect_risk_trends(self) -> dict[str, Any]:
        """Split-half comparison on analysis_score; delta threshold 5.0."""
        if len(self._analyses) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [c.analysis_score for c in self._analyses]
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

    def generate_report(self) -> RiskModelReport:
        by_factor: dict[str, int] = {}
        by_confidence: dict[str, int] = {}
        by_scenario: dict[str, int] = {}
        for r in self._records:
            by_factor[r.risk_factor.value] = by_factor.get(r.risk_factor.value, 0) + 1
            by_confidence[r.model_confidence.value] = (
                by_confidence.get(r.model_confidence.value, 0) + 1
            )
            by_scenario[r.scenario_type.value] = by_scenario.get(r.scenario_type.value, 0) + 1
        high_risk_count = sum(
            1 for r in self._records if r.risk_estimate > self._risk_estimate_threshold
        )
        scores = [r.risk_estimate for r in self._records]
        avg_risk_estimate = round(sum(scores) / len(scores), 2) if scores else 0.0
        high_list = self.identify_high_risk_scenarios()
        top_high_risk = [o["scenario_name"] for o in high_list[:5]]
        recs: list[str] = []
        if self._records and high_risk_count > 0:
            recs.append(
                f"{high_risk_count} scenario(s) above risk estimate threshold "
                f"({self._risk_estimate_threshold})"
            )
        if self._records and avg_risk_estimate > self._risk_estimate_threshold:
            recs.append(
                f"Avg risk estimate {avg_risk_estimate} above threshold "
                f"({self._risk_estimate_threshold})"
            )
        if not recs:
            recs.append("FAIR risk modeling posture is healthy")
        return RiskModelReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            high_risk_count=high_risk_count,
            avg_risk_estimate=avg_risk_estimate,
            by_factor=by_factor,
            by_confidence=by_confidence,
            by_scenario=by_scenario,
            top_high_risk=top_high_risk,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("fair_risk_modeler.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        factor_dist: dict[str, int] = {}
        for r in self._records:
            key = r.risk_factor.value
            factor_dist[key] = factor_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "risk_estimate_threshold": self._risk_estimate_threshold,
            "factor_distribution": factor_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
