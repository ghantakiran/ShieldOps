"""End-to-end integration tests for the Investigation Agent.

Tests the full LangGraph workflow: init → collect_logs → collect_metrics →
correlate → hypothesize → recommend, with mocked external dependencies.
"""

from unittest.mock import patch

import pytest

from shieldops.agents.investigation.models import InvestigationState
from shieldops.agents.investigation.prompts import (
    CorrelationResult,
    HypothesesOutput,
    HypothesisResult,
    LogAnalysisResult,
    MetricAnalysisResult,
    RecommendedActionOutput,
)
from shieldops.agents.investigation.runner import InvestigationRunner


@pytest.fixture
def llm_responses():
    """Deterministic LLM responses matching actual Pydantic schemas."""
    return {
        LogAnalysisResult: LogAnalysisResult(
            summary="Container repeatedly OOMKilled due to memory limit breach",
            error_patterns=["OOMKilled", "Exit code 137"],
            severity="critical",
            root_cause_hints=["Memory leak in recent deployment"],
            affected_services=["api-server"],
        ),
        MetricAnalysisResult: MetricAnalysisResult(
            summary="Memory usage 2x baseline and trending up",
            anomalies_detected=["Memory usage doubled from 512Mi to 1Gi"],
            resource_pressure="high",
            likely_bottleneck="memory",
        ),
        CorrelationResult: CorrelationResult(
            timeline=["T-2h: New image deployed", "T-30m: Memory usage spiking", "T-0: OOMKill"],
            causal_chain="New deployment introduced memory leak causing OOM kills",
            correlated_events=["Deployment of new image preceded OOM events by 2 hours"],
            key_evidence=["OOMKill events", "Memory 2x baseline", "Recent deployment"],
        ),
        HypothesesOutput: HypothesesOutput(
            hypotheses=[
                HypothesisResult(
                    description="Memory leak in new deployment causing OOMKill",
                    confidence=0.85,
                    evidence=["OOMKill events", "Memory 2x baseline", "Recent deployment"],
                    affected_resources=["default/api-server"],
                    recommended_action="restart_pod",
                    reasoning=["Memory usage doubled", "Coincides with deployment"],
                ),
            ],
        ),
        RecommendedActionOutput: RecommendedActionOutput(
            action_type="restart_pod",
            target_resource="default/api-server",
            description="Restart pod to recover from OOMKill",
            risk_level="medium",
            parameters={"grace_period": 30},
            estimated_duration_seconds=60,
        ),
    }


@pytest.mark.asyncio
async def test_investigation_full_pipeline(
    mock_connector_router,
    mock_log_source,
    mock_metric_source,
    mock_trace_source,
    crash_loop_alert,
    llm_responses,
):
    """Investigation runs full pipeline and produces hypotheses + recommended action."""

    async def fake_llm(system_prompt="", user_prompt="", schema=None, **kwargs):
        return llm_responses[schema]

    with (
        patch("shieldops.agents.investigation.nodes.llm_structured", side_effect=fake_llm),
        patch("shieldops.agents.investigation.graph.llm_structured", side_effect=fake_llm),
    ):
        runner = InvestigationRunner(
            connector_router=mock_connector_router,
            log_sources=[mock_log_source],
            metric_sources=[mock_metric_source],
            trace_sources=[mock_trace_source],
        )

        result = await runner.investigate(crash_loop_alert)

    assert isinstance(result, InvestigationState)
    assert result.error is None
    assert result.current_step == "complete"
    assert len(result.hypotheses) >= 1
    assert result.confidence_score > 0
    assert len(result.reasoning_chain) >= 4
    assert result.recommended_action is not None
    assert result.recommended_action.action_type == "restart_pod"
    assert result.investigation_duration_ms > 0


@pytest.mark.asyncio
async def test_investigation_records_reasoning_chain(
    mock_connector_router,
    mock_log_source,
    mock_metric_source,
    mock_trace_source,
    crash_loop_alert,
    llm_responses,
):
    """Each pipeline stage records a reasoning step."""

    async def fake_llm(system_prompt="", user_prompt="", schema=None, **kwargs):
        return llm_responses[schema]

    with (
        patch("shieldops.agents.investigation.nodes.llm_structured", side_effect=fake_llm),
        patch("shieldops.agents.investigation.graph.llm_structured", side_effect=fake_llm),
    ):
        runner = InvestigationRunner(
            connector_router=mock_connector_router,
            log_sources=[mock_log_source],
            metric_sources=[mock_metric_source],
            trace_sources=[mock_trace_source],
        )
        result = await runner.investigate(crash_loop_alert)

    step_names = [step.action for step in result.reasoning_chain]
    assert len(step_names) >= 2


@pytest.mark.asyncio
async def test_investigation_stores_result_in_memory(
    mock_connector_router,
    mock_log_source,
    mock_metric_source,
    mock_trace_source,
    crash_loop_alert,
    llm_responses,
):
    """Runner stores completed investigation in its internal dict."""

    async def fake_llm(system_prompt="", user_prompt="", schema=None, **kwargs):
        return llm_responses[schema]

    with (
        patch("shieldops.agents.investigation.nodes.llm_structured", side_effect=fake_llm),
        patch("shieldops.agents.investigation.graph.llm_structured", side_effect=fake_llm),
    ):
        runner = InvestigationRunner(
            connector_router=mock_connector_router,
            log_sources=[mock_log_source],
            metric_sources=[mock_metric_source],
            trace_sources=[mock_trace_source],
        )
        result = await runner.investigate(crash_loop_alert)

    listed = runner.list_investigations()
    assert len(listed) == 1
    assert listed[0]["alert_id"] == crash_loop_alert.alert_id


@pytest.mark.asyncio
async def test_investigation_handles_llm_failure(
    mock_connector_router,
    mock_log_source,
    mock_metric_source,
    mock_trace_source,
    crash_loop_alert,
):
    """Investigation degrades gracefully when LLM calls fail."""
    with patch(
        "shieldops.agents.investigation.nodes.llm_structured",
        side_effect=RuntimeError("LLM provider unavailable"),
    ):
        runner = InvestigationRunner(
            connector_router=mock_connector_router,
            log_sources=[mock_log_source],
            metric_sources=[mock_metric_source],
            trace_sources=[mock_trace_source],
        )
        result = await runner.investigate(crash_loop_alert)

    # Nodes catch LLM errors internally, so investigation completes with degraded quality
    assert isinstance(result, InvestigationState)
    assert len(result.hypotheses) == 0
    assert result.confidence_score == 0.0
    assert len(result.reasoning_chain) >= 2
