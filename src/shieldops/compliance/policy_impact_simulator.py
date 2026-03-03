"""Policy Impact Simulator — simulate impact of policy changes before deployment."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class SimulationType(StrEnum):
    WHAT_IF = "what_if"
    ROLLBACK = "rollback"
    GRADUAL_ROLLOUT = "gradual_rollout"
    A_B_TEST = "a_b_test"
    FULL_DEPLOYMENT = "full_deployment"


class ImpactCategory(StrEnum):
    ACCESS_RESTRICTION = "access_restriction"
    WORKFLOW_CHANGE = "workflow_change"
    COMPLIANCE_EFFECT = "compliance_effect"
    COST_IMPACT = "cost_impact"
    USER_EXPERIENCE = "user_experience"


class SimulationResult(StrEnum):
    LOW_IMPACT = "low_impact"
    MODERATE = "moderate"
    HIGH_IMPACT = "high_impact"
    BREAKING = "breaking"
    UNKNOWN = "unknown"


# --- Models ---


class SimulationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    simulation_id: str = ""
    simulation_type: SimulationType = SimulationType.WHAT_IF
    impact_category: ImpactCategory = ImpactCategory.ACCESS_RESTRICTION
    simulation_result: SimulationResult = SimulationResult.LOW_IMPACT
    impact_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class SimulationAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    simulation_id: str = ""
    simulation_type: SimulationType = SimulationType.WHAT_IF
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class SimulationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_impact_score: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_category: dict[str, int] = Field(default_factory=dict)
    by_result: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class PolicyImpactSimulator:
    """Simulate impact of policy changes before deployment using various strategies."""

    def __init__(
        self,
        max_records: int = 200000,
        impact_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._impact_threshold = impact_threshold
        self._records: list[SimulationRecord] = []
        self._analyses: list[SimulationAnalysis] = []
        logger.info(
            "policy_impact_simulator.initialized",
            max_records=max_records,
            impact_threshold=impact_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_simulation(
        self,
        simulation_id: str,
        simulation_type: SimulationType = SimulationType.WHAT_IF,
        impact_category: ImpactCategory = ImpactCategory.ACCESS_RESTRICTION,
        simulation_result: SimulationResult = SimulationResult.LOW_IMPACT,
        impact_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> SimulationRecord:
        record = SimulationRecord(
            simulation_id=simulation_id,
            simulation_type=simulation_type,
            impact_category=impact_category,
            simulation_result=simulation_result,
            impact_score=impact_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "policy_impact_simulator.simulation_recorded",
            record_id=record.id,
            simulation_id=simulation_id,
            simulation_type=simulation_type.value,
            impact_category=impact_category.value,
        )
        return record

    def get_simulation(self, record_id: str) -> SimulationRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_simulations(
        self,
        simulation_type: SimulationType | None = None,
        impact_category: ImpactCategory | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[SimulationRecord]:
        results = list(self._records)
        if simulation_type is not None:
            results = [r for r in results if r.simulation_type == simulation_type]
        if impact_category is not None:
            results = [r for r in results if r.impact_category == impact_category]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        simulation_id: str,
        simulation_type: SimulationType = SimulationType.WHAT_IF,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> SimulationAnalysis:
        analysis = SimulationAnalysis(
            simulation_id=simulation_id,
            simulation_type=simulation_type,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "policy_impact_simulator.analysis_added",
            simulation_id=simulation_id,
            simulation_type=simulation_type.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_type_distribution(self) -> dict[str, Any]:
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.simulation_type.value
            type_data.setdefault(key, []).append(r.impact_score)
        result: dict[str, Any] = {}
        for stype, scores in type_data.items():
            result[stype] = {
                "count": len(scores),
                "avg_impact_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_impact_gaps(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.impact_score < self._impact_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "simulation_id": r.simulation_id,
                        "simulation_type": r.simulation_type.value,
                        "impact_score": r.impact_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["impact_score"])

    def rank_by_impact(self) -> list[dict[str, Any]]:
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.impact_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_impact_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_impact_score"])
        return results

    def detect_impact_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> SimulationReport:
        by_type: dict[str, int] = {}
        by_category: dict[str, int] = {}
        by_result: dict[str, int] = {}
        for r in self._records:
            by_type[r.simulation_type.value] = by_type.get(r.simulation_type.value, 0) + 1
            by_category[r.impact_category.value] = by_category.get(r.impact_category.value, 0) + 1
            by_result[r.simulation_result.value] = by_result.get(r.simulation_result.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.impact_score < self._impact_threshold)
        scores = [r.impact_score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_impact_gaps()
        top_gaps = [o["simulation_id"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(
                f"{gap_count} simulation(s) below impact threshold ({self._impact_threshold})"
            )
        if self._records and avg_score < self._impact_threshold:
            recs.append(f"Avg impact score {avg_score} below threshold ({self._impact_threshold})")
        if not recs:
            recs.append("Policy impact simulation is healthy")
        return SimulationReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_impact_score=avg_score,
            by_type=by_type,
            by_category=by_category,
            by_result=by_result,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("policy_impact_simulator.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.simulation_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "impact_threshold": self._impact_threshold,
            "type_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
