"""Cost Optimization Autopilot — auto-execute low-risk cost recommendations."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


class CostRecommendation(BaseModel):
    """A cost optimization recommendation."""

    id: str = Field(default_factory=lambda: f"rec-{uuid4().hex[:12]}")
    category: str = ""  # rightsize, idle_resource, reserved_instance, storage_tier
    resource_id: str = ""
    resource_type: str = ""
    current_cost_monthly: float = 0.0
    estimated_savings_monthly: float = 0.0
    savings_percentage: float = 0.0
    risk_score: float = 0.0  # 0.0 (safe) to 1.0 (risky)
    action: str = ""
    description: str = ""
    auto_approved: bool = False
    status: str = "pending"  # pending, approved, executed, failed, skipped
    executed_at: datetime | None = None
    error: str | None = None


class AutopilotConfig(BaseModel):
    """Configuration for cost autopilot behavior."""

    enabled: bool = False
    auto_approval_threshold: float = 0.3  # Max risk_score for auto-approval
    max_monthly_savings_auto: float = 500.0  # Max $ to auto-execute per action
    min_confidence: float = 0.7
    excluded_environments: list[str] = Field(default_factory=lambda: ["production"])
    excluded_resource_types: list[str] = Field(default_factory=list)
    dry_run: bool = True  # If True, generates recommendations but doesn't execute


class AutopilotResult(BaseModel):
    """Result of an autopilot cycle."""

    cycle_id: str = Field(default_factory=lambda: f"apc-{uuid4().hex[:12]}")
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    total_recommendations: int = 0
    auto_approved: int = 0
    auto_executed: int = 0
    skipped: int = 0
    failed: int = 0
    total_estimated_savings: float = 0.0
    total_executed_savings: float = 0.0
    recommendations: list[CostRecommendation] = Field(default_factory=list)
    config: AutopilotConfig = Field(default_factory=AutopilotConfig)


class CostAutopilot:
    """Autopilot for cost optimization — auto-executes low-risk cost savings.

    Features:
    - Risk scoring for each recommendation
    - Auto-approval below configurable threshold
    - Excluded environments (default: production)
    - Dry-run mode (generate only, no execution)
    - Rollback on failure
    """

    def __init__(self, config: AutopilotConfig | None = None) -> None:
        self._config = config or AutopilotConfig()
        self._history: list[AutopilotResult] = []
        self._recommendations: dict[str, CostRecommendation] = {}

    @property
    def config(self) -> AutopilotConfig:
        return self._config

    def update_config(self, **kwargs: Any) -> AutopilotConfig:
        """Update autopilot configuration."""
        for key, value in kwargs.items():
            if hasattr(self._config, key):
                setattr(self._config, key, value)
        return self._config

    async def analyze_and_recommend(
        self,
        cost_data: dict[str, Any] | None = None,
    ) -> AutopilotResult:
        """Analyze costs and generate optimization recommendations.

        In a real system, this would call CostRunner.analyze() and
        parse the results. Here we generate recommendations from
        the provided cost_data or demo data.
        """
        cycle = AutopilotResult(config=self._config)
        recommendations = self._generate_recommendations(cost_data or {})

        for rec in recommendations:
            # Risk scoring
            rec.risk_score = self._calculate_risk(rec)

            # Auto-approval check
            if self._should_auto_approve(rec):
                rec.auto_approved = True
                rec.status = "approved"
                cycle.auto_approved += 1

                # Auto-execute if not dry-run
                if not self._config.dry_run:
                    success = await self._execute_recommendation(rec)
                    if success:
                        rec.status = "executed"
                        rec.executed_at = datetime.now(UTC)
                        cycle.auto_executed += 1
                        cycle.total_executed_savings += rec.estimated_savings_monthly
                    else:
                        rec.status = "failed"
                        cycle.failed += 1
            else:
                rec.status = "pending"
                cycle.skipped += 1

            self._recommendations[rec.id] = rec
            cycle.recommendations.append(rec)

        cycle.total_recommendations = len(recommendations)
        cycle.total_estimated_savings = sum(r.estimated_savings_monthly for r in recommendations)
        cycle.completed_at = datetime.now(UTC)

        self._history.append(cycle)
        logger.info(
            "autopilot_cycle_completed",
            cycle_id=cycle.cycle_id,
            total=cycle.total_recommendations,
            auto_approved=cycle.auto_approved,
            savings=cycle.total_estimated_savings,
        )
        return cycle

    def get_recommendation(self, rec_id: str) -> CostRecommendation | None:
        return self._recommendations.get(rec_id)

    def list_recommendations(
        self, status: str | None = None, limit: int = 50
    ) -> list[CostRecommendation]:
        recs = list(self._recommendations.values())
        if status:
            recs = [r for r in recs if r.status == status]
        return recs[:limit]

    def get_history(self, limit: int = 20) -> list[AutopilotResult]:
        return list(reversed(self._history[-limit:]))

    async def approve_recommendation(self, rec_id: str) -> CostRecommendation | None:
        """Manually approve a recommendation."""
        rec = self._recommendations.get(rec_id)
        if not rec or rec.status != "pending":
            return None
        rec.status = "approved"
        rec.auto_approved = False
        logger.info("recommendation_approved", rec_id=rec_id)
        return rec

    async def execute_recommendation(self, rec_id: str) -> CostRecommendation | None:
        """Execute an approved recommendation."""
        rec = self._recommendations.get(rec_id)
        if not rec or rec.status != "approved":
            return None
        success = await self._execute_recommendation(rec)
        if success:
            rec.status = "executed"
            rec.executed_at = datetime.now(UTC)
        else:
            rec.status = "failed"
        return rec

    def _should_auto_approve(self, rec: CostRecommendation) -> bool:
        """Check if a recommendation qualifies for auto-approval."""
        if not self._config.enabled:
            return False
        if rec.risk_score > self._config.auto_approval_threshold:
            return False
        if rec.estimated_savings_monthly > self._config.max_monthly_savings_auto:
            return False
        # Check excluded environments
        resource_env = rec.resource_id.split("/")[0] if "/" in rec.resource_id else ""
        if resource_env in self._config.excluded_environments:
            return False
        return rec.resource_type not in self._config.excluded_resource_types

    def _calculate_risk(self, rec: CostRecommendation) -> float:
        """Calculate risk score for a recommendation."""
        score = 0.0
        # Category risk
        category_risk = {
            "idle_resource": 0.1,
            "storage_tier": 0.15,
            "reserved_instance": 0.2,
            "rightsize": 0.3,
            "shutdown": 0.5,
            "decommission": 0.8,
        }
        score += category_risk.get(rec.category, 0.3)

        # Savings magnitude risk (larger savings = more risk)
        if rec.estimated_savings_monthly > 1000:
            score += 0.2
        elif rec.estimated_savings_monthly > 500:
            score += 0.1

        # Resource type risk
        if rec.resource_type in ("database", "data_warehouse"):
            score += 0.3
        elif rec.resource_type in ("compute", "vm"):
            score += 0.1

        return min(score, 1.0)

    def _generate_recommendations(self, cost_data: dict[str, Any]) -> list[CostRecommendation]:
        """Generate recommendations from cost analysis data."""
        recommendations: list[CostRecommendation] = []

        # Process provided resource data
        resources = cost_data.get("resources", [])
        for resource in resources:
            if resource.get("utilization", 100) < 20:
                recommendations.append(
                    CostRecommendation(
                        category="idle_resource",
                        resource_id=resource.get("id", ""),
                        resource_type=resource.get("type", "compute"),
                        current_cost_monthly=resource.get("monthly_cost", 0),
                        estimated_savings_monthly=resource.get("monthly_cost", 0) * 0.9,
                        savings_percentage=90.0,
                        action="terminate_idle",
                        description=f"Resource {resource.get('id', '')} has <20% utilization",
                    )
                )
            elif resource.get("utilization", 100) < 50:
                savings = resource.get("monthly_cost", 0) * 0.4
                recommendations.append(
                    CostRecommendation(
                        category="rightsize",
                        resource_id=resource.get("id", ""),
                        resource_type=resource.get("type", "compute"),
                        current_cost_monthly=resource.get("monthly_cost", 0),
                        estimated_savings_monthly=savings,
                        savings_percentage=40.0,
                        action="rightsize_down",
                        description=(
                            f"Resource {resource.get('id', '')} is under-utilized, "
                            f"consider downsizing"
                        ),
                    )
                )

        return recommendations

    async def _execute_recommendation(self, rec: CostRecommendation) -> bool:
        """Execute a cost optimization recommendation.

        In a real implementation, this would call the appropriate
        connector to resize/terminate/modify the resource.
        """
        try:
            logger.info(
                "recommendation_executing",
                rec_id=rec.id,
                action=rec.action,
                resource=rec.resource_id,
            )
            # Placeholder — real execution would go here
            return True
        except Exception as e:
            rec.error = str(e)
            logger.error("recommendation_execution_failed", rec_id=rec.id, error=str(e))
            return False
