"""Capacity Simulation Engine — simulate capacity scenarios and what-if analysis."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class SimulationScenario(StrEnum):
    PEAK_LOAD = "peak_load"
    FAILURE_MODE = "failure_mode"
    GROWTH_PROJECTION = "growth_projection"
    COST_OPTIMIZATION = "cost_optimization"
    DISASTER_RECOVERY = "disaster_recovery"


class SimulationOutcome(StrEnum):
    WITHIN_CAPACITY = "within_capacity"
    NEAR_LIMIT = "near_limit"
    OVER_CAPACITY = "over_capacity"
    REQUIRES_SCALING = "requires_scaling"
    CRITICAL_SHORTAGE = "critical_shortage"


class SimulationConfidence(StrEnum):
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    SPECULATIVE = "speculative"
    UNKNOWN = "unknown"


# --- Models ---


class SimulationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    scenario_id: str = ""
    simulation_scenario: SimulationScenario = SimulationScenario.PEAK_LOAD
    simulation_outcome: SimulationOutcome = SimulationOutcome.WITHIN_CAPACITY
    simulation_confidence: SimulationConfidence = SimulationConfidence.UNKNOWN
    capacity_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class SimulationResult(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    scenario_id: str = ""
    simulation_scenario: SimulationScenario = SimulationScenario.PEAK_LOAD
    result_value: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class CapacitySimulationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_results: int = 0
    over_capacity_count: int = 0
    avg_capacity_score: float = 0.0
    by_scenario: dict[str, int] = Field(default_factory=dict)
    by_outcome: dict[str, int] = Field(default_factory=dict)
    by_confidence: dict[str, int] = Field(default_factory=dict)
    top_at_risk: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class CapacitySimulationEngine:
    """Simulate capacity scenarios, what-if analysis for scaling decisions."""

    def __init__(
        self,
        max_records: int = 200000,
        max_over_capacity_pct: float = 10.0,
    ) -> None:
        self._max_records = max_records
        self._max_over_capacity_pct = max_over_capacity_pct
        self._records: list[SimulationRecord] = []
        self._results: list[SimulationResult] = []
        logger.info(
            "capacity_simulation.initialized",
            max_records=max_records,
            max_over_capacity_pct=max_over_capacity_pct,
        )

    # -- record / get / list ------------------------------------------------

    def record_simulation(
        self,
        scenario_id: str,
        simulation_scenario: SimulationScenario = SimulationScenario.PEAK_LOAD,
        simulation_outcome: SimulationOutcome = SimulationOutcome.WITHIN_CAPACITY,
        simulation_confidence: SimulationConfidence = SimulationConfidence.UNKNOWN,
        capacity_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> SimulationRecord:
        record = SimulationRecord(
            scenario_id=scenario_id,
            simulation_scenario=simulation_scenario,
            simulation_outcome=simulation_outcome,
            simulation_confidence=simulation_confidence,
            capacity_score=capacity_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "capacity_simulation.simulation_recorded",
            record_id=record.id,
            scenario_id=scenario_id,
            simulation_scenario=simulation_scenario.value,
            simulation_outcome=simulation_outcome.value,
        )
        return record

    def get_simulation(self, record_id: str) -> SimulationRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_simulations(
        self,
        scenario: SimulationScenario | None = None,
        outcome: SimulationOutcome | None = None,
        service: str | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[SimulationRecord]:
        results = list(self._records)
        if scenario is not None:
            results = [r for r in results if r.simulation_scenario == scenario]
        if outcome is not None:
            results = [r for r in results if r.simulation_outcome == outcome]
        if service is not None:
            results = [r for r in results if r.service == service]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_result(
        self,
        scenario_id: str,
        simulation_scenario: SimulationScenario = SimulationScenario.PEAK_LOAD,
        result_value: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> SimulationResult:
        result = SimulationResult(
            scenario_id=scenario_id,
            simulation_scenario=simulation_scenario,
            result_value=result_value,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._results.append(result)
        if len(self._results) > self._max_records:
            self._results = self._results[-self._max_records :]
        logger.info(
            "capacity_simulation.result_added",
            scenario_id=scenario_id,
            simulation_scenario=simulation_scenario.value,
            result_value=result_value,
        )
        return result

    # -- domain operations --------------------------------------------------

    def analyze_simulation_outcomes(self) -> dict[str, Any]:
        """Group by scenario; return count and avg capacity score."""
        scenario_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.simulation_scenario.value
            scenario_data.setdefault(key, []).append(r.capacity_score)
        result: dict[str, Any] = {}
        for scenario, scores in scenario_data.items():
            result[scenario] = {
                "count": len(scores),
                "avg_capacity_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_over_capacity_scenarios(self) -> list[dict[str, Any]]:
        """Return records where outcome is OVER_CAPACITY or CRITICAL_SHORTAGE."""
        over_outcomes = {SimulationOutcome.OVER_CAPACITY, SimulationOutcome.CRITICAL_SHORTAGE}
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.simulation_outcome in over_outcomes:
                results.append(
                    {
                        "record_id": r.id,
                        "scenario_id": r.scenario_id,
                        "simulation_scenario": r.simulation_scenario.value,
                        "simulation_outcome": r.simulation_outcome.value,
                        "capacity_score": r.capacity_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_risk(self) -> list[dict[str, Any]]:
        """Group by service, count over-capacity records, sort descending."""
        over_outcomes = {SimulationOutcome.OVER_CAPACITY, SimulationOutcome.CRITICAL_SHORTAGE}
        svc_risk: dict[str, int] = {}
        for r in self._records:
            if r.simulation_outcome in over_outcomes:
                svc_risk[r.service] = svc_risk.get(r.service, 0) + 1
        results: list[dict[str, Any]] = []
        for svc, count in svc_risk.items():
            results.append(
                {
                    "service": svc,
                    "over_capacity_count": count,
                }
            )
        results.sort(key=lambda x: x["over_capacity_count"], reverse=True)
        return results

    def detect_capacity_trends(self) -> dict[str, Any]:
        """Split-half comparison on result_value; delta threshold 5.0."""
        if len(self._results) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        scores = [r.result_value for r in self._results]
        mid = len(scores) // 2
        first_half = scores[:mid]
        second_half = scores[mid:]
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

    def generate_report(self) -> CapacitySimulationReport:
        by_scenario: dict[str, int] = {}
        by_outcome: dict[str, int] = {}
        by_confidence: dict[str, int] = {}
        for r in self._records:
            by_scenario[r.simulation_scenario.value] = (
                by_scenario.get(r.simulation_scenario.value, 0) + 1
            )
            by_outcome[r.simulation_outcome.value] = (
                by_outcome.get(r.simulation_outcome.value, 0) + 1
            )
            by_confidence[r.simulation_confidence.value] = (
                by_confidence.get(r.simulation_confidence.value, 0) + 1
            )
        over_capacity_count = sum(
            1
            for r in self._records
            if r.simulation_outcome
            in {SimulationOutcome.OVER_CAPACITY, SimulationOutcome.CRITICAL_SHORTAGE}
        )
        avg_capacity_score = (
            round(
                sum(r.capacity_score for r in self._records) / len(self._records),
                2,
            )
            if self._records
            else 0.0
        )
        ranked = self.rank_by_risk()
        top_at_risk = [r["service"] for r in ranked[:5]]
        recs: list[str] = []
        if over_capacity_count > 0:
            recs.append(
                f"{over_capacity_count} over-capacity scenario(s) — review scaling strategy"
            )
        over_pct = (
            round(over_capacity_count / len(self._records) * 100, 2) if self._records else 0.0
        )
        if over_pct > self._max_over_capacity_pct:
            recs.append(
                f"Over-capacity rate {over_pct}% exceeds threshold ({self._max_over_capacity_pct}%)"
            )
        if not recs:
            recs.append("Capacity simulation levels are healthy")
        return CapacitySimulationReport(
            total_records=len(self._records),
            total_results=len(self._results),
            over_capacity_count=over_capacity_count,
            avg_capacity_score=avg_capacity_score,
            by_scenario=by_scenario,
            by_outcome=by_outcome,
            by_confidence=by_confidence,
            top_at_risk=top_at_risk,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._results.clear()
        logger.info("capacity_simulation.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        scenario_dist: dict[str, int] = {}
        for r in self._records:
            key = r.simulation_scenario.value
            scenario_dist[key] = scenario_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_results": len(self._results),
            "max_over_capacity_pct": self._max_over_capacity_pct,
            "scenario_distribution": scenario_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
