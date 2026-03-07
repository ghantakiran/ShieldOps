"""OPA policy gate for Kubernetes remediation actions.

Evaluates every remediation action against OPA policies before execution.
Enforces blast-radius limits, namespace restrictions, and approval workflows.
"""

from __future__ import annotations

from typing import Any

import structlog
from httpx import AsyncClient, HTTPStatusError

from shieldops.config.settings import Settings
from shieldops.remediation.models import (
    ApprovalRequirement,
    K8sActionType,
    PolicyDecision,
    RiskLevel,
)

logger = structlog.get_logger()

# Namespaces that are always off-limits for automated remediation
PROTECTED_NAMESPACES: frozenset[str] = frozenset(
    {
        "kube-system",
        "kube-public",
        "kube-node-lease",
        "cert-manager",
        "istio-system",
    }
)

# Maximum pods that can be affected per action in production
MAX_PROD_POD_BLAST_RADIUS = 5

# Risk classification by action type
ACTION_RISK_MAP: dict[K8sActionType, RiskLevel] = {
    K8sActionType.RESTART_POD: RiskLevel.LOW,
    K8sActionType.DELETE_EVICTED_PODS: RiskLevel.LOW,
    K8sActionType.RESTART_DEPLOYMENT: RiskLevel.MEDIUM,
    K8sActionType.SCALE_DEPLOYMENT: RiskLevel.MEDIUM,
    K8sActionType.SCALE_HPA: RiskLevel.MEDIUM,
    K8sActionType.UPDATE_CONFIG_MAP: RiskLevel.MEDIUM,
    K8sActionType.UPDATE_RESOURCE_LIMITS: RiskLevel.MEDIUM,
    K8sActionType.ROLLBACK_DEPLOYMENT: RiskLevel.HIGH,
    K8sActionType.CORDON_NODE: RiskLevel.HIGH,
    K8sActionType.DRAIN_NODE: RiskLevel.CRITICAL,
}

# Approval requirements by risk level and environment
APPROVAL_MATRIX: dict[tuple[RiskLevel, str], ApprovalRequirement] = {
    (RiskLevel.LOW, "development"): ApprovalRequirement.AUTO_APPROVE,
    (RiskLevel.LOW, "staging"): ApprovalRequirement.AUTO_APPROVE,
    (RiskLevel.LOW, "production"): ApprovalRequirement.AUTO_APPROVE,
    (RiskLevel.MEDIUM, "development"): ApprovalRequirement.AUTO_APPROVE,
    (RiskLevel.MEDIUM, "staging"): ApprovalRequirement.AUTO_APPROVE,
    (RiskLevel.MEDIUM, "production"): ApprovalRequirement.NOTIFY,
    (RiskLevel.HIGH, "development"): ApprovalRequirement.AUTO_APPROVE,
    (RiskLevel.HIGH, "staging"): ApprovalRequirement.NOTIFY,
    (RiskLevel.HIGH, "production"): ApprovalRequirement.REQUIRE_APPROVAL,
    (RiskLevel.CRITICAL, "development"): ApprovalRequirement.NOTIFY,
    (RiskLevel.CRITICAL, "staging"): ApprovalRequirement.REQUIRE_APPROVAL,
    (RiskLevel.CRITICAL, "production"): ApprovalRequirement.REQUIRE_APPROVAL,
}


class PolicyGate:
    """Evaluates remediation actions against OPA policies before execution.

    Applies built-in safety rules and optionally delegates to an external
    OPA server for custom organizational policies.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or Settings()
        self._opa_endpoint = self._settings.opa_endpoint

    async def evaluate_action(
        self,
        action_type: K8sActionType,
        namespace: str,
        resource_name: str,
        environment: str,
        parameters: dict[str, Any] | None = None,
    ) -> PolicyDecision:
        """Evaluate a remediation action against all policy rules.

        Args:
            action_type: The K8s remediation action to perform.
            namespace: Target Kubernetes namespace.
            resource_name: Name of the target resource.
            environment: Target environment (development/staging/production).
            parameters: Action-specific parameters (e.g., replicas count).

        Returns:
            PolicyDecision with allowed/denied status, risk level, and
            approval requirements.
        """
        params = parameters or {}
        risk_level = ACTION_RISK_MAP.get(action_type, RiskLevel.HIGH)
        violated: list[str] = []

        logger.info(
            "policy_gate_evaluating",
            action_type=action_type,
            namespace=namespace,
            resource=resource_name,
            environment=environment,
        )

        # Rule 1: Protected namespace check
        if namespace in PROTECTED_NAMESPACES:
            violated.append(f"namespace_protected: '{namespace}' is a protected system namespace")

        # Rule 2: No scale-to-zero in production
        if (
            action_type == K8sActionType.SCALE_DEPLOYMENT
            and environment == "production"
            and params.get("replicas", 1) == 0
        ):
            violated.append("scale_to_zero_prod: scaling to 0 replicas is forbidden in production")

        # Rule 3: Blast radius limit for pod operations in production
        if (
            action_type in {K8sActionType.RESTART_DEPLOYMENT, K8sActionType.SCALE_DEPLOYMENT}
            and environment == "production"
        ):
            replicas = params.get("replicas")
            if replicas is not None and replicas > MAX_PROD_POD_BLAST_RADIUS:
                violated.append(
                    f"blast_radius_exceeded: affecting {replicas} pods exceeds "
                    f"production limit of {MAX_PROD_POD_BLAST_RADIUS}"
                )

        # Rule 4: Drain requires force-disable for production
        if (
            action_type == K8sActionType.DRAIN_NODE
            and environment == "production"
            and not params.get("force", False)
        ):
            # Non-force drain in prod is allowed but elevated to critical
            risk_level = RiskLevel.CRITICAL

        # Rule 5: Resource limits must be positive
        if action_type == K8sActionType.UPDATE_RESOURCE_LIMITS:
            cpu = params.get("cpu_limit", "")
            memory = params.get("memory_limit", "")
            if not cpu and not memory:
                violated.append(
                    "empty_resource_limits: at least one of cpu_limit or memory_limit required"
                )

        # Delegate to external OPA if configured and reachable
        opa_decision = await self._evaluate_opa(
            action_type=action_type,
            namespace=namespace,
            resource_name=resource_name,
            environment=environment,
            parameters=params,
        )
        if opa_decision is not None:
            violated.extend(opa_decision)

        # Determine approval requirement
        approval = APPROVAL_MATRIX.get(
            (risk_level, environment),
            ApprovalRequirement.REQUIRE_APPROVAL,
        )

        allowed = len(violated) == 0
        reason = "all policies passed" if allowed else "; ".join(violated)

        decision = PolicyDecision(
            allowed=allowed,
            reason=reason,
            risk_level=risk_level,
            requires_approval=approval,
            violated_policies=violated,
        )

        logger.info(
            "policy_gate_result",
            allowed=allowed,
            risk_level=risk_level,
            approval=approval,
            violations=len(violated),
        )

        return decision

    async def _evaluate_opa(
        self,
        action_type: K8sActionType,
        namespace: str,
        resource_name: str,
        environment: str,
        parameters: dict[str, Any],
    ) -> list[str] | None:
        """Query the external OPA server for additional policy evaluation.

        Returns a list of violation strings, or None if OPA is unavailable.
        OPA failures are non-blocking (fail-open for built-in rules,
        but violations from OPA are enforced).
        """
        opa_url = f"{self._opa_endpoint}/v1/data/shieldops/remediation/deny"
        input_payload = {
            "input": {
                "action_type": str(action_type),
                "namespace": namespace,
                "resource_name": resource_name,
                "environment": environment,
                "parameters": parameters,
            }
        }

        try:
            async with AsyncClient(timeout=5.0) as http:
                resp = await http.post(opa_url, json=input_payload)
                resp.raise_for_status()
                data = resp.json()

            # OPA returns {"result": ["reason1", "reason2"]} for denials
            denials = data.get("result", [])
            if isinstance(denials, list) and denials:
                return [f"opa: {d}" for d in denials]
            return []

        except HTTPStatusError as exc:
            logger.warning(
                "opa_http_error",
                status=exc.response.status_code,
                url=opa_url,
            )
            return None
        except Exception as exc:
            logger.warning(
                "opa_unreachable",
                error=str(exc),
                url=opa_url,
            )
            return None
