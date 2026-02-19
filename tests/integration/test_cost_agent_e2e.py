"""End-to-end integration tests for the Cost Agent.

Tests the full LangGraph workflow: gather_costs → detect_anomalies →
recommend_optimizations → synthesize_savings, with mocked external dependencies.
"""

from unittest.mock import AsyncMock, patch

import pytest

from shieldops.agents.cost.models import CostAnalysisState
from shieldops.agents.cost.prompts import (
    CostAnomalyAssessmentResult,
    CostForecastResult,
    OptimizationAssessmentResult,
)
from shieldops.agents.cost.runner import CostRunner
from shieldops.models.base import Environment


@pytest.fixture
def mock_billing_source():
    """Fake billing source that returns test cost data.

    The CostToolkit.query_billing() calls `await source.query(...)` which must
    return a dict with keys: resource_costs, by_service, by_environment,
    total_daily, total_monthly, period, currency.
    """
    source = AsyncMock()
    source.source_name = "test-billing"
    source.query.return_value = {
        "period": "30d",
        "currency": "USD",
        "total_daily": 85.50,
        "total_monthly": 2565.00,
        "by_service": {"EC2": 1815.00, "RDS": 750.00},
        "by_environment": {"production": 2565.00},
        "resource_costs": [
            {
                "resource_id": "i-abc123",
                "resource_type": "instance",
                "service": "EC2",
                "daily_cost": 12.50,
                "monthly_cost": 375.00,
                "usage_percent": 15.0,
            },
            {
                "resource_id": "i-def456",
                "resource_type": "instance",
                "service": "EC2",
                "daily_cost": 48.00,
                "monthly_cost": 1440.00,
                "usage_percent": 85.0,
            },
            {
                "resource_id": "rds-prod-001",
                "resource_type": "database",
                "service": "RDS",
                "daily_cost": 25.00,
                "monthly_cost": 750.00,
                "usage_percent": 40.0,
            },
        ],
    }
    return source


@pytest.fixture
def cost_llm_responses():
    """Deterministic LLM responses for cost agent tests."""
    return {
        CostAnomalyAssessmentResult: CostAnomalyAssessmentResult(
            summary="One underutilized EC2 instance detected",
            critical_anomalies=["i-abc123"],
            root_causes=["Instance running at 15% CPU utilization"],
            immediate_actions=["Downsize i-abc123 to t3.small"],
        ),
        OptimizationAssessmentResult: OptimizationAssessmentResult(
            summary="EC2 rightsizing and reserved instance opportunities",
            top_recommendations=["Downsize i-abc123 from m5.xlarge to t3.small"],
            quick_wins=["Terminate unused EBS volumes"],
            estimated_total_monthly_savings=250.0,
        ),
        CostForecastResult: CostForecastResult(
            overall_health_score=65.0,
            summary="Moderate optimization opportunities available",
            monthly_forecast=2565.00,
            top_cost_risks=["Underutilized EC2 instances"],
            recommended_actions=["Rightsize i-abc123", "Consider reserved instances"],
        ),
    }


@pytest.mark.asyncio
async def test_cost_analysis_full_pipeline(
    mock_connector_router,
    mock_billing_source,
    cost_llm_responses,
):
    """Cost runner runs the full pipeline and produces recommendations."""

    async def fake_llm(system_prompt="", user_prompt="", schema=None, **kwargs):
        return cost_llm_responses[schema]

    with patch("shieldops.agents.cost.nodes.llm_structured", side_effect=fake_llm):
        runner = CostRunner(
            connector_router=mock_connector_router,
            billing_sources=[mock_billing_source],
        )

        result = await runner.analyze(
            environment=Environment.PRODUCTION,
            analysis_type="full",
        )

    assert isinstance(result, CostAnalysisState)
    assert result.error is None
    assert result.current_step != "failed"
    assert len(result.reasoning_chain) >= 2


@pytest.mark.asyncio
async def test_cost_analysis_stores_result(
    mock_connector_router,
    mock_billing_source,
    cost_llm_responses,
):
    """Cost runner stores completed analysis in its internal dict."""

    async def fake_llm(system_prompt="", user_prompt="", schema=None, **kwargs):
        return cost_llm_responses[schema]

    with patch("shieldops.agents.cost.nodes.llm_structured", side_effect=fake_llm):
        runner = CostRunner(
            connector_router=mock_connector_router,
            billing_sources=[mock_billing_source],
        )
        result = await runner.analyze(environment=Environment.PRODUCTION)

    listed = runner.list_analyses()
    assert len(listed) == 1
    assert listed[0]["analysis_id"] == result.analysis_id


@pytest.mark.asyncio
async def test_cost_analysis_handles_llm_failure(
    mock_connector_router,
    mock_billing_source,
):
    """Cost analysis degrades gracefully when LLM calls fail."""
    with patch(
        "shieldops.agents.cost.nodes.llm_structured",
        side_effect=RuntimeError("LLM unavailable"),
    ):
        runner = CostRunner(
            connector_router=mock_connector_router,
            billing_sources=[mock_billing_source],
        )
        result = await runner.analyze(environment=Environment.PRODUCTION)

    assert isinstance(result, CostAnalysisState)
    # Analysis should still complete (nodes catch LLM errors internally)
    assert len(result.reasoning_chain) >= 1


@pytest.mark.asyncio
async def test_cost_analysis_no_billing_sources(mock_connector_router):
    """Cost analysis works with no billing sources (uses stub data)."""

    async def fake_llm(system_prompt="", user_prompt="", schema=None, **kwargs):
        if schema == CostAnomalyAssessmentResult:
            return CostAnomalyAssessmentResult(
                summary="No anomalies", critical_anomalies=[], root_causes=[], immediate_actions=[]
            )
        if schema == OptimizationAssessmentResult:
            return OptimizationAssessmentResult(
                summary="No optimizations",
                top_recommendations=[],
                quick_wins=[],
                estimated_total_monthly_savings=0.0,
            )
        return CostForecastResult(
            overall_health_score=90.0,
            summary="Healthy",
            monthly_forecast=100.0,
            top_cost_risks=[],
            recommended_actions=[],
        )

    with patch("shieldops.agents.cost.nodes.llm_structured", side_effect=fake_llm):
        runner = CostRunner(connector_router=mock_connector_router)
        result = await runner.analyze(environment=Environment.PRODUCTION)

    assert isinstance(result, CostAnalysisState)
    assert result.error is None
