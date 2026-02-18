"""Integration tests for chained Investigation → Remediation workflow.

Validates that an investigation's recommended_action can be fed directly
into the remediation pipeline for automated incident response.
"""

from unittest.mock import patch

import pytest

from shieldops.agents.investigation.prompts import (
    CorrelationResult,
    HypothesesOutput,
    HypothesisResult,
    LogAnalysisResult,
    MetricAnalysisResult,
    RecommendedActionOutput,
)
from shieldops.agents.investigation.runner import InvestigationRunner
from shieldops.agents.remediation.prompts import (
    RiskAssessmentResult,
    ValidationAssessmentResult,
)
from shieldops.agents.remediation.runner import RemediationRunner
from shieldops.models.base import Environment, RemediationAction, RiskLevel
from shieldops.policy.approval.workflow import ApprovalWorkflow


@pytest.fixture
def investigation_llm_responses():
    return {
        LogAnalysisResult: LogAnalysisResult(
            summary="OOMKill pattern detected",
            error_patterns=["OOMKilled", "Exit code 137"],
            severity="error",
            root_cause_hints=["Memory leak"],
            affected_services=["api-server"],
        ),
        MetricAnalysisResult: MetricAnalysisResult(
            summary="Memory spike",
            anomalies_detected=["Memory doubled from baseline"],
            resource_pressure="high",
            likely_bottleneck="memory",
        ),
        CorrelationResult: CorrelationResult(
            timeline=["Memory spike correlates with OOM events"],
            causal_chain="Memory leak → OOM kill → crash loop",
            correlated_events=["OOM events match memory spike"],
            key_evidence=["OOM", "Memory spike"],
        ),
        HypothesesOutput: HypothesesOutput(
            hypotheses=[
                HypothesisResult(
                    description="Memory leak in API service",
                    confidence=0.9,
                    evidence=["OOM", "Memory spike"],
                    affected_resources=["default/api-server"],
                    recommended_action="restart_pod",
                    reasoning=["Memory doubled", "Causes OOM"],
                )
            ],
        ),
        RecommendedActionOutput: RecommendedActionOutput(
            action_type="restart_pod",
            target_resource="default/api-server",
            description="Restart pod to clear memory leak",
            risk_level="medium",
            parameters={"grace_period": 30},
            estimated_duration_seconds=60,
        ),
    }


@pytest.fixture
def remediation_llm_responses():
    return {
        RiskAssessmentResult: RiskAssessmentResult(
            risk_level="medium",
            reasoning=["Pod restart with graceful shutdown is safe"],
            blast_radius="single_pod",
            reversible=True,
            precautions=["Monitor after restart"],
        ),
        ValidationAssessmentResult: ValidationAssessmentResult(
            overall_healthy=True,
            summary="All checks passed",
            concerns=[],
            recommendation="proceed",
        ),
    }


@pytest.mark.asyncio
async def test_investigation_produces_action_for_remediation(
    mock_connector_router,
    mock_log_source,
    mock_metric_source,
    mock_trace_source,
    mock_policy_engine,
    crash_loop_alert,
    investigation_llm_responses,
    remediation_llm_responses,
):
    """Full chain: investigation → recommended_action → remediation succeeds."""

    # Phase 1: Investigation
    async def inv_llm(system_prompt="", user_prompt="", schema=None, **kwargs):
        return investigation_llm_responses[schema]

    with (
        patch("shieldops.agents.investigation.nodes.llm_structured", side_effect=inv_llm),
        patch("shieldops.agents.investigation.graph.llm_structured", side_effect=inv_llm),
    ):
        inv_runner = InvestigationRunner(
            connector_router=mock_connector_router,
            log_sources=[mock_log_source],
            metric_sources=[mock_metric_source],
            trace_sources=[mock_trace_source],
        )
        inv_result = await inv_runner.investigate(crash_loop_alert)

    assert inv_result.recommended_action is not None

    # Phase 2: Convert recommendation to RemediationAction
    rec = inv_result.recommended_action
    action = RemediationAction(
        id="act-chained-001",
        action_type=rec.action_type,
        target_resource=rec.target_resource,
        environment=Environment.PRODUCTION,
        risk_level=RiskLevel(rec.risk_level),
        parameters=rec.parameters or {},
        description=rec.description,
    )

    # Phase 3: Remediation
    async def rem_llm(system_prompt="", user_prompt="", schema=None, **kwargs):
        return remediation_llm_responses[schema]

    with patch("shieldops.agents.remediation.nodes.llm_structured", side_effect=rem_llm):
        rem_runner = RemediationRunner(
            connector_router=mock_connector_router,
            policy_engine=mock_policy_engine,
            approval_workflow=ApprovalWorkflow(timeout_seconds=1),
        )
        rem_result = await rem_runner.remediate(
            action,
            alert_context=crash_loop_alert,
            investigation_id=inv_result.alert_id,
        )

    assert rem_result.error is None
    assert rem_result.current_step == "validate_health"
    assert rem_result.validation_passed is True


@pytest.mark.asyncio
async def test_chained_workflow_links_investigation_id(
    mock_connector_router,
    mock_log_source,
    mock_metric_source,
    mock_trace_source,
    mock_policy_engine,
    crash_loop_alert,
    investigation_llm_responses,
    remediation_llm_responses,
):
    """Remediation records the investigation_id for traceability."""

    async def inv_llm(system_prompt="", user_prompt="", schema=None, **kwargs):
        return investigation_llm_responses[schema]

    with (
        patch("shieldops.agents.investigation.nodes.llm_structured", side_effect=inv_llm),
        patch("shieldops.agents.investigation.graph.llm_structured", side_effect=inv_llm),
    ):
        inv_runner = InvestigationRunner(
            connector_router=mock_connector_router,
            log_sources=[mock_log_source],
            metric_sources=[mock_metric_source],
            trace_sources=[mock_trace_source],
        )
        inv_result = await inv_runner.investigate(crash_loop_alert)

    rec = inv_result.recommended_action
    action = RemediationAction(
        id="act-chained-002",
        action_type=rec.action_type,
        target_resource=rec.target_resource,
        environment=Environment.PRODUCTION,
        risk_level=RiskLevel(rec.risk_level),
        parameters=rec.parameters or {},
        description=rec.description,
    )

    async def rem_llm(system_prompt="", user_prompt="", schema=None, **kwargs):
        return remediation_llm_responses[schema]

    with patch("shieldops.agents.remediation.nodes.llm_structured", side_effect=rem_llm):
        rem_runner = RemediationRunner(
            connector_router=mock_connector_router,
            policy_engine=mock_policy_engine,
            approval_workflow=ApprovalWorkflow(timeout_seconds=1),
        )
        rem_result = await rem_runner.remediate(
            action,
            alert_context=crash_loop_alert,
            investigation_id="inv-linked-001",
        )

    assert rem_result.investigation_id == "inv-linked-001"
