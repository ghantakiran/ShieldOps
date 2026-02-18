"""Tool functions for the Remediation Agent.

Bridges infrastructure connectors, policy engine, and approval workflow
to the agent's LangGraph nodes.
"""

from datetime import UTC
from typing import Any

import structlog

from shieldops.connectors.base import ConnectorRouter
from shieldops.models.base import (
    ActionResult,
    ApprovalStatus,
    ExecutionStatus,
    HealthStatus,
    RemediationAction,
    RiskLevel,
    Snapshot,
)
from shieldops.policy.approval.workflow import ApprovalRequest, ApprovalWorkflow
from shieldops.policy.opa.client import PolicyDecision, PolicyEngine

logger = structlog.get_logger()


class RemediationToolkit:
    """Collection of tools available to the remediation agent.

    Injected into nodes at graph construction time to decouple agent logic
    from specific infrastructure and policy implementations.
    """

    def __init__(
        self,
        connector_router: ConnectorRouter | None = None,
        policy_engine: PolicyEngine | None = None,
        approval_workflow: ApprovalWorkflow | None = None,
    ) -> None:
        self._router = connector_router
        self._policy_engine = policy_engine
        self._approval_workflow = approval_workflow

    async def evaluate_policy(
        self,
        action: RemediationAction,
        agent_id: str = "remediation-agent",
        context: dict[str, Any] | None = None,
    ) -> PolicyDecision:
        """Evaluate action against OPA policies."""
        if self._policy_engine is None:
            logger.warning("policy_engine_not_configured", action=action.action_type)
            return PolicyDecision(
                allowed=True,
                reasons=["No policy engine configured — allowing by default"],
            )

        return await self._policy_engine.evaluate(action, agent_id, context)

    def classify_risk(
        self,
        action_type: str,
        environment: str,
    ) -> RiskLevel:
        """Classify risk level using the policy engine."""
        if self._policy_engine is None:
            return RiskLevel.MEDIUM

        from shieldops.models.base import Environment

        try:
            env = Environment(environment)
        except ValueError:
            env = Environment.PRODUCTION

        return self._policy_engine.classify_risk(action_type, env)

    def requires_approval(self, risk_level: RiskLevel) -> bool:
        """Check if risk level requires human approval."""
        if self._approval_workflow is None:
            return False
        return self._approval_workflow.requires_approval(risk_level)

    async def request_approval(
        self,
        request: ApprovalRequest,
    ) -> ApprovalStatus:
        """Submit approval request and wait for response."""
        if self._approval_workflow is None:
            logger.warning("approval_workflow_not_configured")
            return ApprovalStatus.APPROVED

        return await self._approval_workflow.request_approval(request)

    async def create_snapshot(
        self,
        resource_id: str,
        provider: str = "kubernetes",
    ) -> Snapshot | None:
        """Create infrastructure state snapshot before action."""
        if self._router is None:
            logger.warning("no_connector_router", resource_id=resource_id)
            return None

        try:
            connector = self._router.get(provider)
            return await connector.create_snapshot(resource_id)
        except (ValueError, Exception) as e:
            logger.error(
                "snapshot_creation_failed",
                resource_id=resource_id,
                error=str(e),
            )
            return None

    async def execute_action(
        self,
        action: RemediationAction,
        provider: str = "kubernetes",
    ) -> ActionResult:
        """Execute remediation action via infrastructure connector."""
        if self._router is None:
            return ActionResult(
                action_id=action.id,
                status=ExecutionStatus.FAILED,
                message="No connector router configured",
                started_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
            )

        try:
            connector = self._router.get(provider)
            return await connector.execute_action(action)
        except (ValueError, Exception) as e:
            logger.error(
                "action_execution_failed",
                action_id=action.id,
                error=str(e),
            )
            from datetime import datetime

            return ActionResult(
                action_id=action.id,
                status=ExecutionStatus.FAILED,
                message=str(e),
                started_at=datetime.now(UTC),
                error=str(e),
            )

    async def validate_health(
        self,
        resource_id: str,
        provider: str = "kubernetes",
        timeout_seconds: int = 120,
    ) -> HealthStatus | None:
        """Check resource health after remediation."""
        if self._router is None:
            return None

        try:
            connector = self._router.get(provider)
            health = await connector.get_health(resource_id)
            return health
        except (ValueError, Exception) as e:
            logger.error(
                "health_validation_failed",
                resource_id=resource_id,
                error=str(e),
            )
            return None

    async def rollback(
        self,
        snapshot_id: str,
        provider: str = "kubernetes",
    ) -> ActionResult:
        """Rollback to a previous snapshot."""
        if self._router is None:
            from datetime import datetime

            return ActionResult(
                action_id=f"rollback-{snapshot_id}",
                status=ExecutionStatus.FAILED,
                message="No connector router configured",
                started_at=datetime.now(UTC),
            )

        try:
            connector = self._router.get(provider)
            return await connector.rollback(snapshot_id)
        except (ValueError, Exception) as e:
            logger.error("rollback_failed", snapshot_id=snapshot_id, error=str(e))
            from datetime import datetime

            return ActionResult(
                action_id=f"rollback-{snapshot_id}",
                status=ExecutionStatus.FAILED,
                message=str(e),
                started_at=datetime.now(UTC),
                error=str(e),
            )
