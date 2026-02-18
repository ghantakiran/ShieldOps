"""Node implementations for the Remediation Agent LangGraph workflow.

Each node is an async function that:
1. Evaluates policies, assesses risk, or executes actions via the RemediationToolkit
2. Uses the LLM for risk assessment and validation interpretation
3. Updates the remediation state with results
4. Records its reasoning step in the audit trail
"""

from datetime import UTC, datetime
from typing import Any, cast
from uuid import uuid4

import structlog

from shieldops.agents.remediation.models import (
    PolicyResult,
    RemediationState,
    RemediationStep,
    ValidationCheck,
)
from shieldops.agents.remediation.prompts import (
    SYSTEM_RISK_ASSESSMENT,
    SYSTEM_VALIDATION_ASSESSMENT,
    RiskAssessmentResult,
    ValidationAssessmentResult,
)
from shieldops.agents.remediation.tools import RemediationToolkit
from shieldops.models.base import ExecutionStatus, RiskLevel
from shieldops.policy.approval.workflow import ApprovalRequest
from shieldops.utils.llm import llm_structured

logger = structlog.get_logger()

# Module-level toolkit reference, set by the runner at graph construction time.
_toolkit: RemediationToolkit | None = None


def set_toolkit(toolkit: RemediationToolkit | None) -> None:
    """Configure the toolkit used by all nodes. Called once at startup."""
    global _toolkit
    _toolkit = toolkit


def _get_toolkit() -> RemediationToolkit:
    if _toolkit is None:
        return RemediationToolkit()  # Empty toolkit — safe for tests
    return _toolkit


def _elapsed_ms(start: datetime) -> int:
    return int((datetime.now(UTC) - start).total_seconds() * 1000)


async def evaluate_policy(state: RemediationState) -> dict[str, Any]:
    """Evaluate the remediation action against OPA policies.

    This is the first gate — if policy denies the action, the workflow stops.
    """
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    logger.info(
        "remediation_evaluating_policy",
        remediation_id=state.remediation_id,
        action_type=state.action.action_type,
        target=state.action.target_resource,
    )

    decision = await toolkit.evaluate_policy(state.action)

    policy_result = PolicyResult(
        allowed=decision.allowed,
        reasons=decision.reasons,
        evaluated_at=datetime.now(UTC),
    )

    output_summary = (
        f"Policy {'ALLOWED' if decision.allowed else 'DENIED'}: {'; '.join(decision.reasons[:3])}"
    )

    step = RemediationStep(
        step_number=1,
        action="evaluate_policy",
        input_summary=(
            f"Action: {state.action.action_type} on {state.action.target_resource} "
            f"({state.action.environment.value})"
        ),
        output_summary=output_summary,
        duration_ms=_elapsed_ms(start),
        tool_used="opa_policy_engine",
    )

    return {
        "remediation_start": start,
        "policy_result": policy_result,
        "reasoning_chain": [step],
        "current_step": "evaluate_policy",
    }


async def assess_risk(state: RemediationState) -> dict[str, Any]:
    """Assess the risk level of the action using policy engine + LLM."""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    logger.info(
        "remediation_assessing_risk",
        remediation_id=state.remediation_id,
        action_type=state.action.action_type,
    )

    # Get baseline risk from policy engine
    baseline_risk = toolkit.classify_risk(
        state.action.action_type,
        state.action.environment.value,
    )

    # Enhance with LLM analysis
    assessed_risk = baseline_risk
    output_summary = f"Baseline risk: {baseline_risk.value}"

    context_lines = [
        "## Remediation Action",
        f"Type: {state.action.action_type}",
        f"Target: {state.action.target_resource}",
        f"Environment: {state.action.environment.value}",
        f"Parameters: {state.action.parameters}",
        f"Description: {state.action.description}",
        "",
        "## Policy Evaluation",
        f"Allowed: {state.policy_result.allowed if state.policy_result else 'N/A'}",
        f"Reasons: {state.policy_result.reasons if state.policy_result else []}",
    ]
    if state.alert_context:
        context_lines.extend(
            [
                "",
                "## Alert Context",
                f"Alert: {state.alert_context.alert_name}",
                f"Severity: {state.alert_context.severity}",
                f"Resource: {state.alert_context.resource_id}",
            ]
        )

    try:
        assessment = cast(
            RiskAssessmentResult,
            await llm_structured(
                system_prompt=SYSTEM_RISK_ASSESSMENT,
                user_prompt="\n".join(context_lines),
                schema=RiskAssessmentResult,
            ),
        )

        try:
            llm_risk = RiskLevel(assessment.risk_level)
        except ValueError:
            llm_risk = baseline_risk

        # Use the higher of baseline and LLM-assessed risk (conservative)
        risk_order = [RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL]
        if risk_order.index(llm_risk) > risk_order.index(baseline_risk):
            assessed_risk = llm_risk

        output_summary = (
            f"Risk: {assessed_risk.value} (baseline: {baseline_risk.value}, "
            f"llm: {llm_risk.value}). Blast radius: {assessment.blast_radius}. "
            f"Reversible: {assessment.reversible}"
        )
    except Exception as e:
        logger.error("llm_risk_assessment_failed", error=str(e))
        output_summary += f". LLM assessment failed: {e}"

    step = RemediationStep(
        step_number=len(state.reasoning_chain) + 1,
        action="assess_risk",
        input_summary=(
            f"Assessing risk for {state.action.action_type} in {state.action.environment.value}"
        ),
        output_summary=output_summary,
        duration_ms=_elapsed_ms(start),
        tool_used="policy_engine + llm",
    )

    return {
        "assessed_risk": assessed_risk,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "assess_risk",
    }


async def request_approval(state: RemediationState) -> dict[str, Any]:
    """Request human approval for high/critical risk actions."""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    risk = state.assessed_risk or RiskLevel.HIGH
    request_id = f"apr-{uuid4().hex[:12]}"

    logger.info(
        "remediation_requesting_approval",
        remediation_id=state.remediation_id,
        risk_level=risk.value,
        request_id=request_id,
    )

    request = ApprovalRequest(
        request_id=request_id,
        action=state.action,
        agent_id="remediation-agent",
        reason=(
            f"Remediation action '{state.action.action_type}' on "
            f"{state.action.target_resource} requires approval "
            f"(risk: {risk.value})"
        ),
        required_approvals=2 if risk == RiskLevel.CRITICAL else 1,
    )

    approval_status = await toolkit.request_approval(request)

    output_summary = f"Approval {approval_status.value} for request {request_id}"

    step = RemediationStep(
        step_number=len(state.reasoning_chain) + 1,
        action="request_approval",
        input_summary=f"Requesting approval for {risk.value}-risk action",
        output_summary=output_summary,
        duration_ms=_elapsed_ms(start),
        tool_used="approval_workflow",
    )

    return {
        "approval_status": approval_status,
        "approval_request_id": request_id,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "request_approval",
    }


async def create_snapshot(state: RemediationState) -> dict[str, Any]:
    """Create infrastructure snapshot before executing the action."""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    logger.info(
        "remediation_creating_snapshot",
        remediation_id=state.remediation_id,
        target=state.action.target_resource,
    )

    snapshot = await toolkit.create_snapshot(state.action.target_resource)

    output_summary = (
        f"Snapshot created: {snapshot.id}"
        if snapshot
        else "Snapshot creation failed (proceeding without rollback capability)"
    )

    step = RemediationStep(
        step_number=len(state.reasoning_chain) + 1,
        action="create_snapshot",
        input_summary=f"Capturing state of {state.action.target_resource}",
        output_summary=output_summary,
        duration_ms=_elapsed_ms(start),
        tool_used="infra_connector",
    )

    return {
        "snapshot": snapshot,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "create_snapshot",
    }


async def execute_action(state: RemediationState) -> dict[str, Any]:
    """Execute the remediation action via the infrastructure connector."""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    logger.info(
        "remediation_executing_action",
        remediation_id=state.remediation_id,
        action_type=state.action.action_type,
        target=state.action.target_resource,
    )

    result = await toolkit.execute_action(state.action)

    if result.status == ExecutionStatus.SUCCESS:
        output_summary = f"Action succeeded: {result.message}"
    else:
        output_summary = f"Action failed: {result.message}"

    step = RemediationStep(
        step_number=len(state.reasoning_chain) + 1,
        action="execute_action",
        input_summary=(f"Executing {state.action.action_type} on {state.action.target_resource}"),
        output_summary=output_summary,
        duration_ms=_elapsed_ms(start),
        tool_used="infra_connector",
    )

    return {
        "execution_result": result,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "execute_action",
    }


async def validate_health(state: RemediationState) -> dict[str, Any]:
    """Validate system health after the remediation action."""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    logger.info(
        "remediation_validating_health",
        remediation_id=state.remediation_id,
        target=state.action.target_resource,
    )

    checks: list[ValidationCheck] = []
    health = await toolkit.validate_health(state.action.target_resource)

    if health:
        checks.append(
            ValidationCheck(
                check_name="resource_health",
                passed=health.healthy,
                message=f"Status: {health.status}. {health.message or ''}".strip(),
                checked_at=datetime.now(UTC),
            )
        )

    # Use LLM to assess overall validation results
    validation_passed = all(c.passed for c in checks) if checks else None
    output_summary = f"{len(checks)} checks, passed: {validation_passed}"

    if checks and state.execution_result:
        context_lines = [
            "## Action Executed",
            f"Type: {state.action.action_type}",
            f"Target: {state.action.target_resource}",
            f"Result: {state.execution_result.status.value}",
            f"Message: {state.execution_result.message}",
            "",
            "## Health Checks",
        ]
        for c in checks:
            context_lines.append(
                f"- {c.check_name}: {'PASS' if c.passed else 'FAIL'} — {c.message}"
            )

        try:
            assessment = cast(
                ValidationAssessmentResult,
                await llm_structured(
                    system_prompt=SYSTEM_VALIDATION_ASSESSMENT,
                    user_prompt="\n".join(context_lines),
                    schema=ValidationAssessmentResult,
                ),
            )
            validation_passed = assessment.overall_healthy
            output_summary = f"{assessment.summary}. Recommendation: {assessment.recommendation}"

            if assessment.concerns:
                checks.append(
                    ValidationCheck(
                        check_name="llm_assessment",
                        passed=assessment.overall_healthy,
                        message=f"Concerns: {'; '.join(assessment.concerns[:3])}",
                        checked_at=datetime.now(UTC),
                    )
                )
        except Exception as e:
            logger.error("llm_validation_assessment_failed", error=str(e))

    step = RemediationStep(
        step_number=len(state.reasoning_chain) + 1,
        action="validate_health",
        input_summary=f"Validating health of {state.action.target_resource}",
        output_summary=output_summary,
        duration_ms=_elapsed_ms(start),
        tool_used="infra_connector + llm",
    )

    return {
        "validation_checks": checks,
        "validation_passed": validation_passed,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "validate_health",
    }


async def perform_rollback(state: RemediationState) -> dict[str, Any]:
    """Rollback to pre-action state using the captured snapshot."""
    start = datetime.now(UTC)
    toolkit = _get_toolkit()

    logger.info(
        "remediation_rolling_back",
        remediation_id=state.remediation_id,
        snapshot_id=state.snapshot.id if state.snapshot else None,
    )

    rollback_result = None
    output_summary = "No snapshot available for rollback"

    if state.snapshot:
        rollback_result = await toolkit.rollback(state.snapshot.id)
        if rollback_result.status == ExecutionStatus.SUCCESS:
            output_summary = f"Rollback succeeded: {rollback_result.message}"
        else:
            output_summary = f"Rollback failed: {rollback_result.message}"
    else:
        output_summary = "No snapshot captured — manual intervention may be required"

    step = RemediationStep(
        step_number=len(state.reasoning_chain) + 1,
        action="perform_rollback",
        input_summary=f"Rolling back {state.action.target_resource}",
        output_summary=output_summary,
        duration_ms=_elapsed_ms(start),
        tool_used="infra_connector",
    )

    return {
        "rollback_result": rollback_result,
        "reasoning_chain": [*state.reasoning_chain, step],
        "current_step": "rolled_back",
    }
