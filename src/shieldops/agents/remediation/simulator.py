"""Remediation simulation — dry-run without touching infrastructure."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


class SimulationStep(BaseModel):
    """A single step in the simulation plan."""

    order: int = 0
    action: str = ""
    target: str = ""
    description: str = ""
    risk_level: str = "low"
    reversible: bool = True
    estimated_duration_seconds: int = 0


class ImpactEstimate(BaseModel):
    """Estimated impact of the remediation."""

    affected_resources: list[str] = Field(default_factory=list)
    affected_services: list[str] = Field(default_factory=list)
    downtime_risk: str = "none"  # none, minimal, moderate, significant
    data_loss_risk: str = "none"  # none, minimal, moderate, significant
    blast_radius: str = "single_resource"  # single_resource, service, environment, global
    confidence: float = 0.0


class SimulationResult(BaseModel):
    """Result of a remediation simulation (dry-run)."""

    simulation_id: str = Field(default_factory=lambda: f"sim-{uuid4().hex[:12]}")
    action_type: str = ""
    target_resource: str = ""
    environment: str = ""
    risk_level: str = "low"
    status: str = "completed"  # completed, failed, rejected
    planned_steps: list[SimulationStep] = Field(default_factory=list)
    impact: ImpactEstimate = Field(default_factory=ImpactEstimate)
    policy_check: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    recommendation: str = ""
    simulated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    duration_ms: int = 0


class RemediationSimulator:
    """Simulates remediation actions without executing them.

    Analyzes the action, generates a step plan, estimates impact,
    and checks policies — all without touching infrastructure.
    """

    def __init__(self, policy_engine: Any | None = None) -> None:
        self._policy_engine = policy_engine
        self._simulations: dict[str, SimulationResult] = {}

    async def simulate(
        self,
        action_type: str,
        target_resource: str,
        environment: str = "production",
        risk_level: str = "low",
        parameters: dict[str, Any] | None = None,
    ) -> SimulationResult:
        """Run a dry-run simulation of a remediation action."""
        start = datetime.now(UTC)
        params = parameters or {}

        # Generate planned steps
        steps = self._generate_steps(action_type, target_resource, params)

        # Estimate impact
        impact = self._estimate_impact(action_type, target_resource, environment, risk_level)

        # Check policies
        policy_result = await self._check_policy(
            action_type, target_resource, environment, risk_level
        )

        # Generate warnings
        warnings = self._generate_warnings(action_type, environment, risk_level, impact)

        # Generate recommendation
        recommendation = self._generate_recommendation(risk_level, impact, policy_result, warnings)

        status = "completed"
        if policy_result.get("denied"):
            status = "rejected"

        elapsed = int((datetime.now(UTC) - start).total_seconds() * 1000)

        result = SimulationResult(
            action_type=action_type,
            target_resource=target_resource,
            environment=environment,
            risk_level=risk_level,
            status=status,
            planned_steps=steps,
            impact=impact,
            policy_check=policy_result,
            warnings=warnings,
            recommendation=recommendation,
            duration_ms=elapsed,
        )

        self._simulations[result.simulation_id] = result
        logger.info(
            "simulation_completed",
            simulation_id=result.simulation_id,
            action=action_type,
            status=status,
        )
        return result

    def get_simulation(self, simulation_id: str) -> SimulationResult | None:
        return self._simulations.get(simulation_id)

    def list_simulations(self, limit: int = 50) -> list[SimulationResult]:
        sims = sorted(
            self._simulations.values(),
            key=lambda s: s.simulated_at,
            reverse=True,
        )
        return sims[:limit]

    def _generate_steps(
        self, action_type: str, target: str, params: dict[str, Any]
    ) -> list[SimulationStep]:
        """Generate simulation steps based on action type."""
        step_templates: dict[str, list[dict[str, Any]]] = {
            "restart_service": [
                {
                    "action": "snapshot",
                    "description": f"Take snapshot of {target}",
                    "risk_level": "low",
                    "duration": 5,
                },
                {
                    "action": "drain_connections",
                    "description": f"Drain active connections on {target}",
                    "risk_level": "low",
                    "duration": 10,
                },
                {
                    "action": "restart",
                    "description": f"Restart service {target}",
                    "risk_level": "medium",
                    "duration": 15,
                },
                {
                    "action": "health_check",
                    "description": f"Verify {target} is healthy",
                    "risk_level": "low",
                    "duration": 10,
                },
            ],
            "scale_up": [
                {
                    "action": "snapshot",
                    "description": f"Record current state of {target}",
                    "risk_level": "low",
                    "duration": 5,
                },
                {
                    "action": "scale",
                    "description": f"Scale up {target} by {params.get('replicas', 2)} replicas",
                    "risk_level": "low",
                    "duration": 30,
                },
                {
                    "action": "health_check",
                    "description": "Verify new replicas are healthy",
                    "risk_level": "low",
                    "duration": 15,
                },
            ],
            "scale_down": [
                {
                    "action": "snapshot",
                    "description": f"Record current state of {target}",
                    "risk_level": "low",
                    "duration": 5,
                },
                {
                    "action": "drain",
                    "description": f"Drain pods on {target}",
                    "risk_level": "medium",
                    "duration": 20,
                },
                {
                    "action": "scale",
                    "description": f"Scale down {target}",
                    "risk_level": "medium",
                    "duration": 15,
                },
            ],
            "rollback": [
                {
                    "action": "snapshot",
                    "description": f"Snapshot current state of {target}",
                    "risk_level": "low",
                    "duration": 5,
                },
                {
                    "action": "identify_version",
                    "description": "Identify rollback target version",
                    "risk_level": "low",
                    "duration": 5,
                },
                {
                    "action": "rollback",
                    "description": f"Rollback {target} to previous version",
                    "risk_level": "high",
                    "duration": 30,
                },
                {
                    "action": "health_check",
                    "description": "Verify rollback success",
                    "risk_level": "low",
                    "duration": 15,
                },
            ],
            "patch": [
                {
                    "action": "snapshot",
                    "description": f"Snapshot {target} before patching",
                    "risk_level": "low",
                    "duration": 5,
                },
                {
                    "action": "download_patch",
                    "description": "Download and verify patch",
                    "risk_level": "low",
                    "duration": 10,
                },
                {
                    "action": "apply_patch",
                    "description": f"Apply patch to {target}",
                    "risk_level": "high",
                    "duration": 45,
                },
                {
                    "action": "restart",
                    "description": f"Restart {target} with patch",
                    "risk_level": "medium",
                    "duration": 15,
                },
                {
                    "action": "health_check",
                    "description": "Verify patched service health",
                    "risk_level": "low",
                    "duration": 10,
                },
            ],
        }

        templates = step_templates.get(
            action_type,
            [
                {
                    "action": action_type,
                    "description": f"Execute {action_type} on {target}",
                    "risk_level": "medium",
                    "duration": 30,
                },
            ],
        )

        return [
            SimulationStep(
                order=i + 1,
                action=t["action"],
                target=target,
                description=t["description"],
                risk_level=t.get("risk_level", "low"),
                reversible=t.get("risk_level", "low") != "high",
                estimated_duration_seconds=t.get("duration", 10),
            )
            for i, t in enumerate(templates)
        ]

    def _estimate_impact(
        self, action_type: str, target: str, environment: str, risk_level: str
    ) -> ImpactEstimate:
        """Estimate the impact of the remediation."""
        # Determine blast radius
        blast_radius = "single_resource"
        if action_type in ("rollback", "patch"):
            blast_radius = "service"
        if risk_level in ("high", "critical"):
            blast_radius = "service"

        # Determine downtime risk
        downtime_map = {
            "restart_service": "minimal",
            "scale_up": "none",
            "scale_down": "minimal",
            "rollback": "moderate",
            "patch": "moderate",
        }
        downtime = downtime_map.get(action_type, "minimal")

        # Higher risk in production
        confidence = 0.85
        if environment == "production":
            confidence = 0.7
            if risk_level in ("high", "critical"):
                downtime = "significant" if downtime == "moderate" else downtime

        return ImpactEstimate(
            affected_resources=[target],
            affected_services=[target.split("/")[0] if "/" in target else target],
            downtime_risk=downtime,
            data_loss_risk="none",
            blast_radius=blast_radius,
            confidence=confidence,
        )

    async def _check_policy(
        self, action_type: str, target: str, environment: str, risk_level: str
    ) -> dict[str, Any]:
        """Check OPA policies for the action (simulation mode)."""
        if not self._policy_engine:
            return {"checked": False, "result": "no_policy_engine", "denied": False}

        try:
            result = await self._policy_engine.evaluate(
                action_type=action_type,
                target_resource=target,
                environment=environment,
                risk_level=risk_level,
            )
            return {
                "checked": True,
                "result": "allowed" if result.get("allow") else "denied",
                "denied": not result.get("allow", True),
                "violations": result.get("violations", []),
            }
        except Exception as e:
            return {"checked": False, "result": f"error: {e}", "denied": False}

    def _generate_warnings(
        self, action_type: str, environment: str, risk_level: str, impact: ImpactEstimate
    ) -> list[str]:
        """Generate warnings based on the simulation analysis."""
        warnings: list[str] = []
        if environment == "production":
            warnings.append("Action targets production environment — manual approval recommended")
        if risk_level in ("high", "critical"):
            warnings.append(f"High risk action ({risk_level}) — review planned steps carefully")
        if impact.downtime_risk in ("moderate", "significant"):
            warnings.append(f"Downtime risk: {impact.downtime_risk}")
        if action_type == "rollback":
            warnings.append("Rollback may cause temporary service disruption")
        if impact.blast_radius in ("service", "environment", "global"):
            warnings.append(f"Blast radius: {impact.blast_radius} — multiple components affected")
        return warnings

    def _generate_recommendation(
        self, risk_level: str, impact: ImpactEstimate, policy: dict[str, Any], warnings: list[str]
    ) -> str:
        """Generate a recommendation based on simulation results."""
        if policy.get("denied"):
            return "BLOCKED: Policy check denied this action. Review violations before proceeding."
        if risk_level == "critical":
            return "CAUTION: Critical risk action. Requires senior approval and maintenance window."
        if risk_level == "high" or len(warnings) >= 3:
            return (
                "REVIEW: Multiple risk factors detected. "
                "Review planned steps and schedule during low-traffic window."
            )
        if impact.downtime_risk in ("moderate", "significant"):
            return (
                "SCHEDULE: Action may cause downtime. "
                "Consider scheduling during maintenance window."
            )
        return "SAFE: Low risk action. Safe to proceed with standard approval."
