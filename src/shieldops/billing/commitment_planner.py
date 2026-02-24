"""Cloud Commitment Planner — plan optimal mix of on-demand, reserved, savings plans, and spot."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class PricingModel(StrEnum):
    ON_DEMAND = "on_demand"
    RESERVED_1YR = "reserved_1yr"
    RESERVED_3YR = "reserved_3yr"
    SAVINGS_PLAN = "savings_plan"
    SPOT = "spot"


class WorkloadPattern(StrEnum):
    STEADY_STATE = "steady_state"
    BURST = "burst"
    CYCLIC = "cyclic"
    DECLINING = "declining"
    UNPREDICTABLE = "unpredictable"


class RecommendationConfidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    SPECULATIVE = "speculative"
    INSUFFICIENT_DATA = "insufficient_data"


# --- Models ---


class WorkloadProfile(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    current_pricing: PricingModel = PricingModel.ON_DEMAND
    pattern: WorkloadPattern = WorkloadPattern.STEADY_STATE
    monthly_cost: float = 0.0
    avg_utilization_pct: float = 0.0
    peak_utilization_pct: float = 0.0
    created_at: float = Field(default_factory=time.time)


class CommitmentRecommendation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    workload_id: str = ""
    recommended_pricing: PricingModel = PricingModel.ON_DEMAND
    confidence: RecommendationConfidence = RecommendationConfidence.MEDIUM
    estimated_savings_pct: float = 0.0
    estimated_monthly_savings: float = 0.0
    rationale: str = ""
    created_at: float = Field(default_factory=time.time)


class CommitmentPlanReport(BaseModel):
    total_workloads: int = 0
    total_monthly_cost: float = 0.0
    potential_savings: float = 0.0
    savings_pct: float = 0.0
    by_pricing: dict[str, int] = Field(default_factory=dict)
    by_pattern: dict[str, int] = Field(default_factory=dict)
    recommendations_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


_SAVINGS_PCT: dict[PricingModel, float] = {
    PricingModel.RESERVED_3YR: 40.0,
    PricingModel.RESERVED_1YR: 25.0,
    PricingModel.SAVINGS_PLAN: 20.0,
    PricingModel.SPOT: 60.0,
    PricingModel.ON_DEMAND: 0.0,
}


class CloudCommitmentPlanner:
    """Plan optimal mix of on-demand, reserved, savings plans, and spot pricing."""

    def __init__(
        self,
        max_workloads: int = 100000,
        min_savings_threshold_pct: float = 10.0,
    ) -> None:
        self._max_workloads = max_workloads
        self._min_savings_threshold_pct = min_savings_threshold_pct
        self._workloads: list[WorkloadProfile] = []
        self._recommendations: list[CommitmentRecommendation] = []
        logger.info(
            "commitment_planner.initialized",
            max_workloads=max_workloads,
            min_savings_threshold_pct=min_savings_threshold_pct,
        )

    def register_workload(
        self,
        service_name: str = "",
        current_pricing: PricingModel = PricingModel.ON_DEMAND,
        pattern: WorkloadPattern = WorkloadPattern.STEADY_STATE,
        monthly_cost: float = 0.0,
        avg_utilization_pct: float = 0.0,
        peak_utilization_pct: float = 0.0,
    ) -> WorkloadProfile:
        """Register a workload profile for commitment planning."""
        workload = WorkloadProfile(
            service_name=service_name,
            current_pricing=current_pricing,
            pattern=pattern,
            monthly_cost=monthly_cost,
            avg_utilization_pct=avg_utilization_pct,
            peak_utilization_pct=peak_utilization_pct,
        )
        self._workloads.append(workload)
        if len(self._workloads) > self._max_workloads:
            self._workloads = self._workloads[-self._max_workloads :]
        logger.info(
            "commitment_planner.workload_registered",
            workload_id=workload.id,
            service_name=service_name,
            pattern=pattern,
            monthly_cost=monthly_cost,
        )
        return workload

    def get_workload(self, wl_id: str) -> WorkloadProfile | None:
        """Retrieve a single workload profile by ID."""
        for w in self._workloads:
            if w.id == wl_id:
                return w
        return None

    def list_workloads(
        self,
        pattern: WorkloadPattern | None = None,
        current_pricing: PricingModel | None = None,
        limit: int = 100,
    ) -> list[WorkloadProfile]:
        """List workloads with optional filtering by pattern and pricing model."""
        results = list(self._workloads)
        if pattern is not None:
            results = [w for w in results if w.pattern == pattern]
        if current_pricing is not None:
            results = [w for w in results if w.current_pricing == current_pricing]
        return results[-limit:]

    def recommend_pricing_model(self, workload_id: str) -> CommitmentRecommendation | None:
        """Recommend optimal pricing model for a workload based on pattern and utilization."""
        workload = self.get_workload(workload_id)
        if workload is None:
            logger.warning(
                "commitment_planner.workload_not_found",
                workload_id=workload_id,
            )
            return None

        # Determine recommended pricing based on pattern + utilization
        if workload.pattern == WorkloadPattern.STEADY_STATE:
            if workload.avg_utilization_pct > 70.0:
                recommended = PricingModel.RESERVED_3YR
                confidence = RecommendationConfidence.HIGH
                rationale = (
                    "Steady-state workload with high utilization (>70%) — "
                    "3-year reserved instance provides maximum savings"
                )
            else:
                recommended = PricingModel.RESERVED_1YR
                confidence = RecommendationConfidence.MEDIUM
                rationale = (
                    "Steady-state workload with moderate utilization — "
                    "1-year reserved instance balances savings and flexibility"
                )
        elif workload.pattern == WorkloadPattern.BURST:
            recommended = PricingModel.SPOT
            confidence = RecommendationConfidence.MEDIUM
            rationale = (
                "Burst workload pattern — spot instances offer "
                "significant savings for interruptible burst capacity"
            )
        elif workload.pattern == WorkloadPattern.CYCLIC:
            recommended = PricingModel.SAVINGS_PLAN
            confidence = RecommendationConfidence.MEDIUM
            rationale = (
                "Cyclic workload pattern — savings plan provides "
                "flexible commitment across usage cycles"
            )
        elif workload.pattern == WorkloadPattern.DECLINING:
            recommended = PricingModel.ON_DEMAND
            confidence = RecommendationConfidence.LOW
            rationale = (
                "Declining workload pattern — on-demand avoids commitment risk as usage decreases"
            )
        else:  # UNPREDICTABLE
            recommended = PricingModel.ON_DEMAND
            confidence = RecommendationConfidence.LOW
            rationale = (
                "Unpredictable workload pattern — on-demand provides "
                "maximum flexibility without commitment risk"
            )

        savings_pct = _SAVINGS_PCT.get(recommended, 0.0)
        monthly_savings = round(workload.monthly_cost * savings_pct / 100, 2)

        recommendation = CommitmentRecommendation(
            workload_id=workload_id,
            recommended_pricing=recommended,
            confidence=confidence,
            estimated_savings_pct=savings_pct,
            estimated_monthly_savings=monthly_savings,
            rationale=rationale,
        )
        self._recommendations.append(recommendation)
        logger.info(
            "commitment_planner.recommendation_created",
            workload_id=workload_id,
            recommended_pricing=recommended,
            savings_pct=savings_pct,
            monthly_savings=monthly_savings,
        )
        return recommendation

    def calculate_optimal_mix(self) -> dict[str, Any]:
        """Generate recommendations for all workloads and calculate optimal pricing mix."""
        # Clear previous recommendations and regenerate
        self._recommendations.clear()
        for workload in self._workloads:
            self.recommend_pricing_model(workload.id)

        # Aggregate optimal mix
        optimal_mix: dict[str, int] = {}
        total_potential_savings = 0.0
        for rec in self._recommendations:
            key = rec.recommended_pricing.value
            optimal_mix[key] = optimal_mix.get(key, 0) + 1
            total_potential_savings += rec.estimated_monthly_savings

        return {
            "total_workloads": len(self._workloads),
            "optimal_mix": optimal_mix,
            "total_potential_savings": round(total_potential_savings, 2),
        }

    def estimate_savings(self, workload_id: str) -> dict[str, Any]:
        """Estimate potential savings for a single workload."""
        workload = self.get_workload(workload_id)
        if workload is None:
            return {
                "workload_id": workload_id,
                "current_cost": 0.0,
                "recommended_pricing": PricingModel.ON_DEMAND.value,
                "estimated_savings_pct": 0.0,
                "estimated_monthly_savings": 0.0,
            }

        # Find existing recommendation or create one
        rec = None
        for r in self._recommendations:
            if r.workload_id == workload_id:
                rec = r
                break
        if rec is None:
            rec = self.recommend_pricing_model(workload_id)

        savings_pct = rec.estimated_savings_pct if rec else 0.0
        monthly_savings = rec.estimated_monthly_savings if rec else 0.0
        recommended = rec.recommended_pricing.value if rec else PricingModel.ON_DEMAND.value

        return {
            "workload_id": workload_id,
            "current_cost": workload.monthly_cost,
            "recommended_pricing": recommended,
            "estimated_savings_pct": savings_pct,
            "estimated_monthly_savings": monthly_savings,
        }

    def detect_workload_pattern(self, workload_id: str) -> dict[str, Any]:
        """Detect workload pattern based on utilization metrics."""
        workload = self.get_workload(workload_id)
        if workload is None:
            return {
                "workload_id": workload_id,
                "detected_pattern": WorkloadPattern.UNPREDICTABLE.value,
                "confidence": RecommendationConfidence.INSUFFICIENT_DATA.value,
            }

        avg = workload.avg_utilization_pct
        peak = workload.peak_utilization_pct
        spread = peak - avg

        if avg > 80.0 and spread < 10.0:
            detected = WorkloadPattern.STEADY_STATE
            confidence = RecommendationConfidence.HIGH
        elif peak > 90.0 and avg < 50.0:
            detected = WorkloadPattern.BURST
            confidence = RecommendationConfidence.HIGH
        elif 30.0 <= avg <= 70.0 and 20.0 <= spread <= 40.0:
            detected = WorkloadPattern.CYCLIC
            confidence = RecommendationConfidence.MEDIUM
        elif avg < 30.0:
            detected = WorkloadPattern.DECLINING
            confidence = RecommendationConfidence.MEDIUM
        else:
            detected = WorkloadPattern.UNPREDICTABLE
            confidence = RecommendationConfidence.LOW

        logger.info(
            "commitment_planner.pattern_detected",
            workload_id=workload_id,
            detected_pattern=detected,
            confidence=confidence,
        )
        return {
            "workload_id": workload_id,
            "detected_pattern": detected.value,
            "confidence": confidence.value,
        }

    def compare_commitment_scenarios(self, workload_id: str) -> list[dict[str, Any]]:
        """Compare cost under each pricing model for a workload."""
        workload = self.get_workload(workload_id)
        if workload is None:
            return []

        scenarios: list[dict[str, Any]] = []
        for model in PricingModel:
            savings_pct = _SAVINGS_PCT.get(model, 0.0)
            projected_cost = round(workload.monthly_cost * (1 - savings_pct / 100), 2)
            scenarios.append(
                {
                    "pricing_model": model.value,
                    "monthly_cost": projected_cost,
                    "savings_pct": savings_pct,
                }
            )
        return scenarios

    def generate_plan_report(self) -> CommitmentPlanReport:
        """Generate a comprehensive commitment plan report."""
        total_monthly_cost = sum(w.monthly_cost for w in self._workloads)
        potential_savings = sum(r.estimated_monthly_savings for r in self._recommendations)
        savings_pct = (
            round(potential_savings / total_monthly_cost * 100, 2)
            if total_monthly_cost > 0
            else 0.0
        )

        by_pricing: dict[str, int] = {}
        for w in self._workloads:
            key = w.current_pricing.value
            by_pricing[key] = by_pricing.get(key, 0) + 1

        by_pattern: dict[str, int] = {}
        for w in self._workloads:
            key = w.pattern.value
            by_pattern[key] = by_pattern.get(key, 0) + 1

        recommendations: list[str] = []
        if potential_savings > 0:
            recommendations.append(
                f"Total potential savings of ${potential_savings:,.2f}/month "
                f"({savings_pct:.1f}%) available through commitment optimization"
            )

        on_demand_count = by_pricing.get(PricingModel.ON_DEMAND.value, 0)
        if on_demand_count > len(self._workloads) / 2:
            recommendations.append(
                f"{on_demand_count} workloads still on on-demand pricing — "
                f"review for commitment eligibility"
            )

        steady_count = by_pattern.get(WorkloadPattern.STEADY_STATE.value, 0)
        if steady_count > 0:
            recommendations.append(
                f"{steady_count} steady-state workloads are prime candidates "
                f"for reserved instance commitments"
            )

        if not self._workloads:
            recommendations.append(
                "No workloads registered — add workload profiles to enable planning"
            )

        report = CommitmentPlanReport(
            total_workloads=len(self._workloads),
            total_monthly_cost=round(total_monthly_cost, 2),
            potential_savings=round(potential_savings, 2),
            savings_pct=savings_pct,
            by_pricing=by_pricing,
            by_pattern=by_pattern,
            recommendations_count=len(self._recommendations),
            recommendations=recommendations,
        )
        logger.info(
            "commitment_planner.report_generated",
            total_workloads=len(self._workloads),
            total_monthly_cost=round(total_monthly_cost, 2),
            potential_savings=round(potential_savings, 2),
        )
        return report

    def clear_data(self) -> None:
        """Clear all stored workloads and recommendations."""
        self._workloads.clear()
        self._recommendations.clear()
        logger.info("commitment_planner.data_cleared")

    def get_stats(self) -> dict[str, Any]:
        """Return aggregate statistics about workloads and recommendations."""
        pricing_counts: dict[str, int] = {}
        pattern_counts: dict[str, int] = {}
        for w in self._workloads:
            pricing_counts[w.current_pricing.value] = (
                pricing_counts.get(w.current_pricing.value, 0) + 1
            )
            pattern_counts[w.pattern.value] = pattern_counts.get(w.pattern.value, 0) + 1

        return {
            "total_workloads": len(self._workloads),
            "total_recommendations": len(self._recommendations),
            "pricing_distribution": pricing_counts,
            "pattern_distribution": pattern_counts,
            "max_workloads": self._max_workloads,
            "min_savings_threshold_pct": self._min_savings_threshold_pct,
        }
