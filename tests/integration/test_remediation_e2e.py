"""End-to-end integration tests for the Remediation Agent.

Tests the full LangGraph workflow: policy_check → risk_assess → approval →
snapshot → execute → validate, with mocked external dependencies.
"""

from unittest.mock import patch

import pytest

from shieldops.agents.remediation.models import RemediationState
from shieldops.agents.remediation.prompts import (
    RiskAssessmentResult,
    ValidationAssessmentResult,
)
from shieldops.agents.remediation.runner import RemediationRunner
from shieldops.models.base import ApprovalStatus
from shieldops.policy.approval.workflow import ApprovalWorkflow


@pytest.fixture
def llm_responses():
    """Deterministic LLM responses matching actual Pydantic schemas."""
    return {
        RiskAssessmentResult: RiskAssessmentResult(
            risk_level="medium",
            reasoning=["Pod restart with graceful shutdown", "Limited blast radius"],
            blast_radius="single_pod",
            reversible=True,
            precautions=["Take snapshot first", "Monitor after restart"],
        ),
        ValidationAssessmentResult: ValidationAssessmentResult(
            overall_healthy=True,
            summary="All post-remediation checks passed",
            concerns=[],
            recommendation="proceed",
        ),
    }


@pytest.mark.asyncio
async def test_remediation_full_pipeline_allowed(
    mock_connector_router,
    mock_policy_engine,
    restart_pod_action,
    crash_loop_alert,
    llm_responses,
):
    """Remediation runs full pipeline when policy allows and action succeeds."""

    async def fake_llm(system_prompt="", user_prompt="", schema=None, **kwargs):
        return llm_responses[schema]

    with patch("shieldops.agents.remediation.nodes.llm_structured", side_effect=fake_llm):
        runner = RemediationRunner(
            connector_router=mock_connector_router,
            policy_engine=mock_policy_engine,
            approval_workflow=ApprovalWorkflow(timeout_seconds=1),
        )

        result = await runner.remediate(
            restart_pod_action,
            alert_context=crash_loop_alert,
        )

    assert isinstance(result, RemediationState)
    assert result.error is None
    assert result.current_step == "validate_health"
    assert result.policy_result is not None
    assert result.policy_result.allowed is True
    assert result.validation_passed is True
    assert result.remediation_duration_ms > 0
    assert len(result.reasoning_chain) >= 3


@pytest.mark.asyncio
async def test_remediation_policy_denied_blocks_execution(
    mock_connector_router,
    mock_policy_engine_deny,
    restart_pod_action,
    llm_responses,
):
    """Remediation stops at policy check when denied."""

    async def fake_llm(system_prompt="", user_prompt="", schema=None, **kwargs):
        return llm_responses[schema]

    with patch("shieldops.agents.remediation.nodes.llm_structured", side_effect=fake_llm):
        runner = RemediationRunner(
            connector_router=mock_connector_router,
            policy_engine=mock_policy_engine_deny,
            approval_workflow=ApprovalWorkflow(timeout_seconds=1),
        )

        result = await runner.remediate(restart_pod_action)

    assert result.policy_result is not None
    assert result.policy_result.allowed is False
    assert result.current_step == "evaluate_policy"
    mock_connector_router.get.return_value.execute_action.assert_not_called()


@pytest.mark.asyncio
async def test_remediation_high_risk_requires_approval(
    mock_connector_router,
    mock_policy_engine,
    auto_approve_workflow,
    high_risk_action,
    llm_responses,
):
    """HIGH risk actions require and wait for approval."""

    async def fake_llm(system_prompt="", user_prompt="", schema=None, **kwargs):
        if schema == RiskAssessmentResult:
            return RiskAssessmentResult(
                risk_level="high",
                reasoning=["Rollback affects all users", "Production environment"],
                blast_radius="deployment",
                reversible=True,
                precautions=["Notify on-call", "Monitor error rates"],
            )
        return llm_responses[schema]

    with patch("shieldops.agents.remediation.nodes.llm_structured", side_effect=fake_llm):
        runner = RemediationRunner(
            connector_router=mock_connector_router,
            policy_engine=mock_policy_engine,
            approval_workflow=auto_approve_workflow,
        )

        result = await runner.remediate(high_risk_action)

    assert result.error is None
    assert result.approval_status == ApprovalStatus.APPROVED
    assert result.current_step == "validate_health"


@pytest.mark.asyncio
async def test_remediation_takes_snapshot_before_execution(
    mock_connector_router,
    mock_policy_engine,
    restart_pod_action,
    llm_responses,
):
    """Remediation takes a snapshot before executing the action."""

    async def fake_llm(system_prompt="", user_prompt="", schema=None, **kwargs):
        return llm_responses[schema]

    with patch("shieldops.agents.remediation.nodes.llm_structured", side_effect=fake_llm):
        runner = RemediationRunner(
            connector_router=mock_connector_router,
            policy_engine=mock_policy_engine,
            approval_workflow=ApprovalWorkflow(timeout_seconds=1),
        )
        result = await runner.remediate(restart_pod_action)

    assert result.snapshot is not None
    assert result.snapshot.resource_id == "default/api-server"


@pytest.mark.asyncio
async def test_remediation_validation_failure(
    mock_connector_router,
    mock_policy_engine,
    restart_pod_action,
    llm_responses,
):
    """Remediation reports when validation fails."""

    async def fake_llm(system_prompt="", user_prompt="", schema=None, **kwargs):
        if schema == ValidationAssessmentResult:
            return ValidationAssessmentResult(
                overall_healthy=False,
                summary="Post-remediation validation failed",
                concerns=["Pod still in CrashLoopBackOff"],
                recommendation="rollback",
            )
        return llm_responses[schema]

    with patch("shieldops.agents.remediation.nodes.llm_structured", side_effect=fake_llm):
        runner = RemediationRunner(
            connector_router=mock_connector_router,
            policy_engine=mock_policy_engine,
            approval_workflow=ApprovalWorkflow(timeout_seconds=1),
        )
        result = await runner.remediate(restart_pod_action)

    assert result.validation_passed is False


@pytest.mark.asyncio
async def test_remediation_stores_result(
    mock_connector_router,
    mock_policy_engine,
    restart_pod_action,
    llm_responses,
):
    """Runner stores completed remediation in its internal dict."""

    async def fake_llm(system_prompt="", user_prompt="", schema=None, **kwargs):
        return llm_responses[schema]

    with patch("shieldops.agents.remediation.nodes.llm_structured", side_effect=fake_llm):
        runner = RemediationRunner(
            connector_router=mock_connector_router,
            policy_engine=mock_policy_engine,
            approval_workflow=ApprovalWorkflow(timeout_seconds=1),
        )
        await runner.remediate(restart_pod_action)

    listed = runner.list_remediations()
    assert len(listed) == 1
    assert listed[0]["action_type"] == "restart_pod"
