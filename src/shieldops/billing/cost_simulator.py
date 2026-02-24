"""Cost Simulation Engine — what-if cost modeling for infrastructure changes."""

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
    ADD_RESOURCE = "add_resource"
    REMOVE_RESOURCE = "remove_resource"
    RESIZE = "resize"
    MIGRATE_REGION = "migrate_region"
    CHANGE_PROVIDER = "change_provider"


class CostImpact(StrEnum):
    DECREASE_MAJOR = "decrease_major"
    DECREASE_MINOR = "decrease_minor"
    NEUTRAL = "neutral"
    INCREASE_MINOR = "increase_minor"
    INCREASE_MAJOR = "increase_major"


class SimulationStatus(StrEnum):
    DRAFT = "draft"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ARCHIVED = "archived"


# --- Models ---


class SimulationScenario(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    simulation_type: SimulationType = SimulationType.ADD_RESOURCE
    status: SimulationStatus = SimulationStatus.DRAFT
    baseline_monthly_cost: float = 0.0
    resource_name: str = ""
    resource_cost: float = 0.0
    region: str = ""
    provider: str = ""
    created_at: float = Field(default_factory=time.time)


class SimulationResult(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    scenario_id: str = ""
    projected_monthly_cost: float = 0.0
    cost_difference: float = 0.0
    cost_impact: CostImpact = CostImpact.NEUTRAL
    impact_pct: float = 0.0
    details: str = ""
    calculated_at: float = Field(default_factory=time.time)


class SimulationReport(BaseModel):
    total_scenarios: int = 0
    completed_count: int = 0
    avg_impact_pct: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_impact: dict[str, int] = Field(default_factory=dict)
    total_projected_savings: float = 0.0
    budget_breaches: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class CostSimulationEngine:
    """What-if cost modeling for infrastructure changes."""

    def __init__(
        self,
        max_scenarios: int = 50000,
        budget_breach_threshold_pct: float = 20.0,
    ) -> None:
        self._max_scenarios = max_scenarios
        self._budget_breach_threshold_pct = budget_breach_threshold_pct
        self._scenarios: list[SimulationScenario] = []
        self._results: list[SimulationResult] = []
        logger.info(
            "cost_simulator.initialized",
            max_scenarios=max_scenarios,
            budget_breach_threshold_pct=budget_breach_threshold_pct,
        )

    def create_scenario(
        self,
        name: str = "",
        simulation_type: SimulationType = SimulationType.ADD_RESOURCE,
        baseline_monthly_cost: float = 0.0,
        resource_name: str = "",
        resource_cost: float = 0.0,
        region: str = "",
        provider: str = "",
    ) -> SimulationScenario:
        """Create a new simulation scenario."""
        scenario = SimulationScenario(
            name=name,
            simulation_type=simulation_type,
            baseline_monthly_cost=baseline_monthly_cost,
            resource_name=resource_name,
            resource_cost=resource_cost,
            region=region,
            provider=provider,
        )
        self._scenarios.append(scenario)
        if len(self._scenarios) > self._max_scenarios:
            self._scenarios = self._scenarios[-self._max_scenarios :]
        logger.info(
            "cost_simulator.scenario_created",
            scenario_id=scenario.id,
            name=name,
            simulation_type=simulation_type,
            baseline_monthly_cost=baseline_monthly_cost,
        )
        return scenario

    def get_scenario(self, scenario_id: str) -> SimulationScenario | None:
        """Retrieve a single scenario by ID."""
        for s in self._scenarios:
            if s.id == scenario_id:
                return s
        return None

    def list_scenarios(
        self,
        simulation_type: SimulationType | None = None,
        status: SimulationStatus | None = None,
        limit: int = 100,
    ) -> list[SimulationScenario]:
        """List scenarios with optional filtering by type and status."""
        results = list(self._scenarios)
        if simulation_type is not None:
            results = [s for s in results if s.simulation_type == simulation_type]
        if status is not None:
            results = [s for s in results if s.status == status]
        return results[-limit:]

    def run_simulation(self, scenario_id: str) -> SimulationResult | None:
        """Run a cost simulation for a scenario.

        Calculates projected cost based on simulation type:
        - ADD_RESOURCE: baseline + resource_cost
        - REMOVE_RESOURCE: baseline - resource_cost
        - RESIZE: baseline * 0.8
        - MIGRATE_REGION: baseline * 0.9
        - CHANGE_PROVIDER: baseline * 0.85
        """
        scenario = self.get_scenario(scenario_id)
        if scenario is None:
            logger.warning(
                "cost_simulator.scenario_not_found",
                scenario_id=scenario_id,
            )
            return None

        baseline = scenario.baseline_monthly_cost

        if scenario.simulation_type == SimulationType.ADD_RESOURCE:
            projected = baseline + scenario.resource_cost
        elif scenario.simulation_type == SimulationType.REMOVE_RESOURCE:
            projected = baseline - scenario.resource_cost
        elif scenario.simulation_type == SimulationType.RESIZE:
            projected = baseline * 0.8
        elif scenario.simulation_type == SimulationType.MIGRATE_REGION:
            projected = baseline * 0.9
        elif scenario.simulation_type == SimulationType.CHANGE_PROVIDER:
            projected = baseline * 0.85
        else:
            projected = baseline

        projected = round(projected, 2)
        cost_difference = round(projected - baseline, 2)
        impact_pct = round(cost_difference / baseline * 100, 2) if baseline > 0 else 0.0

        # Determine cost impact category
        if impact_pct <= -20.0:
            cost_impact = CostImpact.DECREASE_MAJOR
        elif impact_pct < 0.0:
            cost_impact = CostImpact.DECREASE_MINOR
        elif impact_pct == 0.0:
            cost_impact = CostImpact.NEUTRAL
        elif impact_pct <= 20.0:
            cost_impact = CostImpact.INCREASE_MINOR
        else:
            cost_impact = CostImpact.INCREASE_MAJOR

        details = (
            f"{scenario.simulation_type.value}: baseline ${baseline:,.2f} -> "
            f"projected ${projected:,.2f} ({impact_pct:+.1f}%)"
        )

        result = SimulationResult(
            scenario_id=scenario_id,
            projected_monthly_cost=projected,
            cost_difference=cost_difference,
            cost_impact=cost_impact,
            impact_pct=impact_pct,
            details=details,
        )
        self._results.append(result)
        scenario.status = SimulationStatus.COMPLETED

        logger.info(
            "cost_simulator.simulation_completed",
            scenario_id=scenario_id,
            projected=projected,
            cost_difference=cost_difference,
            impact_pct=impact_pct,
        )
        return result

    def compare_scenarios(self, scenario_ids: list[str]) -> list[dict[str, Any]]:
        """Compare results for given scenarios."""
        comparisons: list[dict[str, Any]] = []
        for sid in scenario_ids:
            scenario = self.get_scenario(sid)
            if scenario is None:
                continue
            # Find result for this scenario
            result = None
            for r in self._results:
                if r.scenario_id == sid:
                    result = r
                    break
            comparisons.append(
                {
                    "scenario_id": sid,
                    "name": scenario.name,
                    "projected_cost": result.projected_monthly_cost if result else 0.0,
                    "impact_pct": result.impact_pct if result else 0.0,
                }
            )
        return comparisons

    def estimate_monthly_impact(self, scenario_id: str) -> dict[str, Any]:
        """Estimate monthly and annual cost impact for a scenario."""
        scenario = self.get_scenario(scenario_id)
        if scenario is None:
            return {
                "scenario_id": scenario_id,
                "baseline": 0.0,
                "projected": 0.0,
                "monthly_difference": 0.0,
                "annual_difference": 0.0,
            }

        # Find result for this scenario
        result = None
        for r in self._results:
            if r.scenario_id == scenario_id:
                result = r
                break

        projected = result.projected_monthly_cost if result else scenario.baseline_monthly_cost
        monthly_diff = round(projected - scenario.baseline_monthly_cost, 2)
        annual_diff = round(monthly_diff * 12, 2)

        return {
            "scenario_id": scenario_id,
            "baseline": scenario.baseline_monthly_cost,
            "projected": projected,
            "monthly_difference": monthly_diff,
            "annual_difference": annual_diff,
        }

    def identify_cost_drivers(self) -> list[dict[str, Any]]:
        """Identify top cost drivers sorted by absolute cost difference descending."""
        drivers: list[dict[str, Any]] = []
        for result in self._results:
            scenario = self.get_scenario(result.scenario_id)
            scenario_name = scenario.name if scenario else "unknown"
            drivers.append(
                {
                    "scenario_name": scenario_name,
                    "cost_difference": result.cost_difference,
                    "impact_pct": result.impact_pct,
                }
            )
        drivers.sort(key=lambda x: abs(x["cost_difference"]), reverse=True)
        return drivers

    def detect_budget_breaches(self) -> list[dict[str, Any]]:
        """Detect simulations where impact exceeds the budget breach threshold."""
        breaches: list[dict[str, Any]] = []
        for result in self._results:
            if abs(result.impact_pct) > self._budget_breach_threshold_pct:
                scenario = self.get_scenario(result.scenario_id)
                scenario_name = scenario.name if scenario else "unknown"
                breach_amount = round(abs(result.impact_pct) - self._budget_breach_threshold_pct, 2)
                breaches.append(
                    {
                        "scenario_id": result.scenario_id,
                        "scenario_name": scenario_name,
                        "impact_pct": result.impact_pct,
                        "breach_amount": breach_amount,
                    }
                )
        return breaches

    def generate_simulation_report(self) -> SimulationReport:
        """Generate a comprehensive simulation report across all scenarios."""
        completed = [s for s in self._scenarios if s.status == SimulationStatus.COMPLETED]

        by_type: dict[str, int] = {}
        for s in self._scenarios:
            key = s.simulation_type.value
            by_type[key] = by_type.get(key, 0) + 1

        by_impact: dict[str, int] = {}
        total_savings = 0.0
        impact_sum = 0.0
        for r in self._results:
            key = r.cost_impact.value
            by_impact[key] = by_impact.get(key, 0) + 1
            if r.cost_difference < 0:
                total_savings += abs(r.cost_difference)
            impact_sum += r.impact_pct

        avg_impact = round(impact_sum / len(self._results), 2) if self._results else 0.0

        breaches = self.detect_budget_breaches()

        recommendations: list[str] = []
        if total_savings > 0:
            recommendations.append(
                f"Total projected savings of ${total_savings:,.2f}/month "
                f"across {len(completed)} completed simulations"
            )

        if breaches:
            recommendations.append(
                f"{len(breaches)} scenario(s) breach the "
                f"{self._budget_breach_threshold_pct}% budget threshold — review before proceeding"
            )

        increase_major = by_impact.get(CostImpact.INCREASE_MAJOR.value, 0)
        if increase_major > 0:
            recommendations.append(
                f"{increase_major} scenario(s) would cause major cost increase — "
                f"consider alternatives"
            )

        if not self._scenarios:
            recommendations.append(
                "No scenarios created — add simulation scenarios to model cost impacts"
            )

        report = SimulationReport(
            total_scenarios=len(self._scenarios),
            completed_count=len(completed),
            avg_impact_pct=avg_impact,
            by_type=by_type,
            by_impact=by_impact,
            total_projected_savings=round(total_savings, 2),
            budget_breaches=len(breaches),
            recommendations=recommendations,
        )
        logger.info(
            "cost_simulator.report_generated",
            total_scenarios=len(self._scenarios),
            completed_count=len(completed),
            total_projected_savings=round(total_savings, 2),
        )
        return report

    def clear_data(self) -> None:
        """Clear all stored scenarios and results."""
        self._scenarios.clear()
        self._results.clear()
        logger.info("cost_simulator.data_cleared")

    def get_stats(self) -> dict[str, Any]:
        """Return aggregate statistics about scenarios and results."""
        type_counts: dict[str, int] = {}
        status_counts: dict[str, int] = {}
        for s in self._scenarios:
            type_counts[s.simulation_type.value] = type_counts.get(s.simulation_type.value, 0) + 1
            status_counts[s.status.value] = status_counts.get(s.status.value, 0) + 1

        return {
            "total_scenarios": len(self._scenarios),
            "total_results": len(self._results),
            "type_distribution": type_counts,
            "status_distribution": status_counts,
            "max_scenarios": self._max_scenarios,
            "budget_breach_threshold_pct": self._budget_breach_threshold_pct,
        }
