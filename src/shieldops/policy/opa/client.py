"""OPA policy evaluation client."""

from typing import Any

import httpx
import structlog

from shieldops.config import settings
from shieldops.models.base import Environment, RemediationAction, RiskLevel

logger = structlog.get_logger()


class PolicyDecision:
    """Result of a policy evaluation."""

    def __init__(self, allowed: bool, reasons: list[str] | None = None) -> None:
        self.allowed = allowed
        self.reasons = reasons or []

    @property
    def denied(self) -> bool:
        return not self.allowed


class PolicyEngine:
    """Evaluates agent actions against OPA policies before execution.

    Every agent action must pass through this engine. No exceptions.
    """

    def __init__(
        self,
        opa_url: str | None = None,
        rate_limiter: Any = None,
    ) -> None:
        self._opa_url = opa_url or settings.opa_endpoint
        self._client = httpx.AsyncClient(timeout=5.0)
        self._rate_limiter = rate_limiter

    async def evaluate(
        self,
        action: RemediationAction,
        agent_id: str,
        context: dict[str, Any] | None = None,
    ) -> PolicyDecision:
        """Evaluate an action against OPA policies.

        Args:
            action: The remediation action to evaluate.
            agent_id: ID of the agent requesting the action.
            context: Additional context (time of day, recent actions, etc.).

        Returns:
            PolicyDecision indicating whether the action is allowed.
        """
        ctx = dict(context or {})

        # Enrich context with rate limiter data
        if self._rate_limiter:
            try:
                actions_this_hour = await self._rate_limiter.count_recent_actions(
                    action.environment.value
                )
                ctx.setdefault("actions_this_hour", actions_this_hour)
            except Exception as e:
                logger.warning("rate_limiter_enrichment_failed", error=str(e))

        if self._rate_limiter:
            try:
                actions_this_minute = await self._rate_limiter.count_recent_actions_minute(
                    action.environment.value
                )
                ctx.setdefault("actions_this_minute", actions_this_minute)
            except Exception as e:
                logger.warning("rate_limiter_minute_enrichment_failed", error=str(e))

            team = action.parameters.get("team") or ctx.get("team")
            if team and self._rate_limiter:
                try:
                    team_actions = await self._rate_limiter.count_team_actions(
                        team, action.environment.value
                    )
                    ctx.setdefault("team_actions_this_hour", team_actions)
                except Exception as e:
                    logger.warning("rate_limiter_team_enrichment_failed", error=str(e))

        input_data = {
            "action": action.action_type,
            "target_resource": action.target_resource,
            "environment": action.environment.value,
            "risk_level": action.risk_level.value,
            "parameters": action.parameters,
            "agent_id": agent_id,
            "team": action.parameters.get("team") or ctx.get("team"),
            "resource_labels": action.parameters.get(
                "resource_labels", ctx.get("resource_labels", {})
            ),
            "context": ctx,
        }

        try:
            response = await self._client.post(
                f"{self._opa_url}/v1/data/shieldops/allow",
                json={"input": input_data},
            )
            response.raise_for_status()
            result = response.json()

            allowed = result.get("result", False)
            reasons = result.get("reasons", [])

            logger.info(
                "policy_evaluation",
                action=action.action_type,
                target=action.target_resource,
                environment=action.environment.value,
                allowed=allowed,
                reasons=reasons,
            )

            # Increment rate limiter on allowed actions
            if allowed and self._rate_limiter:
                try:
                    await self._rate_limiter.increment(action.environment.value)
                except Exception as e:
                    logger.warning("rate_limiter_increment_failed", error=str(e))

                try:
                    await self._rate_limiter.increment_minute(action.environment.value)
                    team = action.parameters.get("team") or ctx.get("team")
                    if team:
                        await self._rate_limiter.increment_team(team, action.environment.value)
                except Exception as e:
                    logger.warning("rate_limiter_extended_increment_failed", error=str(e))

            return PolicyDecision(allowed=allowed, reasons=reasons)

        except httpx.HTTPError as e:
            logger.error("policy_evaluation_failed", error=str(e))
            # Fail closed: if we can't evaluate policy, deny the action
            return PolicyDecision(
                allowed=False,
                reasons=[f"Policy evaluation failed: {e}. Defaulting to deny."],
            )

    def classify_risk(
        self,
        action_type: str,
        environment: Environment,
    ) -> RiskLevel:
        """Classify the risk level of an action in a given environment.

        Default risk classification (overridable via OPA policies):
        - Dev environments: most actions are low risk
        - Staging: medium risk
        - Production: high/critical risk for destructive operations
        """
        destructive_actions = {
            "drain_node",
            "delete_namespace",
            "modify_network_policy",
            "modify_iam_policy",
        }
        high_impact_actions = {
            "rollback_deployment",
            "rotate_credentials",
            "scale_down",
        }

        if action_type in destructive_actions:
            return RiskLevel.CRITICAL

        if environment == Environment.PRODUCTION:
            if action_type in high_impact_actions:
                return RiskLevel.HIGH
            return RiskLevel.MEDIUM

        if environment == Environment.STAGING:
            if action_type in high_impact_actions:
                return RiskLevel.MEDIUM
            return RiskLevel.LOW

        return RiskLevel.LOW

    async def close(self) -> None:
        """Close the HTTP client and rate limiter."""
        await self._client.aclose()
        if self._rate_limiter:
            try:
                await self._rate_limiter.close()
            except Exception:
                logger.debug("rate_limiter_close_failed")
