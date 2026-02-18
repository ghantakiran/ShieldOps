"""Integration tests for policy enforcement across the agent pipeline.

Validates that OPA policy decisions correctly gate agent actions:
- DENIED blocks execution
- HIGH risk requires 1 approval
- CRITICAL risk requires 2 approvals (four-eyes principle)
"""

import asyncio
from unittest.mock import patch

import pytest

from shieldops.agents.remediation.prompts import (
    RiskAssessmentResult,
    ValidationAssessmentResult,
)
from shieldops.agents.remediation.runner import RemediationRunner
from shieldops.models.base import ApprovalStatus
from shieldops.policy.approval.workflow import ApprovalWorkflow


@pytest.fixture
def llm_responses():
    return {
        RiskAssessmentResult: RiskAssessmentResult(
            risk_level="medium",
            reasoning=["Standard operation"],
            blast_radius="single_pod",
            reversible=True,
            precautions=["Monitor"],
        ),
        ValidationAssessmentResult: ValidationAssessmentResult(
            overall_healthy=True,
            summary="Healthy",
            concerns=[],
            recommendation="proceed",
        ),
    }


@pytest.mark.asyncio
async def test_policy_denied_blocks_all_execution(
    mock_connector_router,
    mock_policy_engine_deny,
    restart_pod_action,
    llm_responses,
):
    """When policy engine returns DENIED, no execution occurs."""

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
    connector = mock_connector_router.get.return_value
    connector.execute_action.assert_not_called()
    connector.create_snapshot.assert_not_called()


@pytest.mark.asyncio
async def test_high_risk_requires_single_approval(
    mock_connector_router,
    mock_policy_engine,
    high_risk_action,
    llm_responses,
):
    """HIGH risk action requires exactly 1 approval."""
    workflow = ApprovalWorkflow(timeout_seconds=5)

    async def fake_llm(system_prompt="", user_prompt="", schema=None, **kwargs):
        if schema == RiskAssessmentResult:
            return RiskAssessmentResult(
                risk_level="high",
                reasoning=["Rollback affects all traffic"],
                blast_radius="deployment",
                reversible=True,
                precautions=["Monitor error rates"],
            )
        return llm_responses[schema]

    with patch("shieldops.agents.remediation.nodes.llm_structured", side_effect=fake_llm):
        runner = RemediationRunner(
            connector_router=mock_connector_router,
            policy_engine=mock_policy_engine,
            approval_workflow=workflow,
        )

        task = asyncio.create_task(runner.remediate(high_risk_action))

        await asyncio.sleep(0.5)

        for req_id in list(workflow._pending.keys()):
            workflow.approve(req_id, "sre-lead")

        result = await task

    assert result.error is None
    assert result.current_step == "validate_health"


@pytest.mark.asyncio
async def test_critical_risk_requires_two_approvals(
    mock_connector_router,
    mock_policy_engine,
    critical_action,
    llm_responses,
):
    """CRITICAL risk action requires 2 approvals (four-eyes principle)."""
    workflow = ApprovalWorkflow(timeout_seconds=5)

    async def fake_llm(system_prompt="", user_prompt="", schema=None, **kwargs):
        if schema == RiskAssessmentResult:
            return RiskAssessmentResult(
                risk_level="critical",
                reasoning=["Cluster-wide scaling in production"],
                blast_radius="cluster",
                reversible=False,
                precautions=["Staged rollout", "Monitor capacity"],
            )
        return llm_responses[schema]

    with patch("shieldops.agents.remediation.nodes.llm_structured", side_effect=fake_llm):
        runner = RemediationRunner(
            connector_router=mock_connector_router,
            policy_engine=mock_policy_engine,
            approval_workflow=workflow,
        )

        task = asyncio.create_task(runner.remediate(critical_action))
        await asyncio.sleep(0.5)

        for req_id in list(workflow._pending.keys()):
            workflow.approve(req_id, "sre-lead")

        await asyncio.sleep(0.3)

        for req_id in list(workflow._pending.keys()):
            req = workflow._pending[req_id]
            if not req.is_approved:
                workflow.approve(req_id, "security-lead")

        result = await task

    assert result.error is None
    assert result.current_step == "validate_health"


@pytest.mark.asyncio
async def test_approval_timeout_escalates(
    mock_connector_router,
    mock_policy_engine,
    high_risk_action,
    llm_responses,
):
    """Approval timeout results in escalation status."""
    workflow = ApprovalWorkflow(timeout_seconds=1)

    async def fake_llm(system_prompt="", user_prompt="", schema=None, **kwargs):
        if schema == RiskAssessmentResult:
            return RiskAssessmentResult(
                risk_level="high",
                reasoning=["Rollback"],
                blast_radius="deployment",
                reversible=True,
                precautions=[],
            )
        return llm_responses[schema]

    with patch("shieldops.agents.remediation.nodes.llm_structured", side_effect=fake_llm):
        runner = RemediationRunner(
            connector_router=mock_connector_router,
            policy_engine=mock_policy_engine,
            approval_workflow=workflow,
        )

        result = await runner.remediate(high_risk_action)

    # No one approved within 1s → escalated → graph routes to END
    assert result.approval_status in (
        ApprovalStatus.ESCALATED,
        ApprovalStatus.TIMEOUT,
    )
    assert result.current_step == "request_approval"
