"""Comprehensive tests for the Cost Agent."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from shieldops.agents.cost.graph import (
    create_cost_graph,
    should_detect_anomalies,
    should_recommend_optimizations,
)
from shieldops.agents.cost.models import (
    CostAnalysisState,
    CostAnomaly,
    CostSavings,
    CostStep,
    OptimizationRecommendation,
    ResourceCost,
)
from shieldops.agents.cost.nodes import (
    detect_anomalies,
    gather_costs,
    recommend_optimizations,
    set_toolkit,
    synthesize_savings,
)
from shieldops.agents.cost.runner import CostRunner
from shieldops.agents.cost.tools import CostToolkit
from shieldops.models.base import Environment


# ===========================================================================
# Toolkit Tests
# ===========================================================================


class TestCostToolkit:
    """Tests for CostToolkit."""

    @pytest.mark.asyncio
    async def test_query_billing_with_source(self):
        source = AsyncMock()
        source.query.return_value = {
            "total_daily": 500.0,
            "total_monthly": 15000.0,
            "by_service": {"compute": 10000.0},
            "by_environment": {"production": 12000.0},
            "resource_costs": [
                {"resource_id": "i-1", "daily_cost": 50.0, "monthly_cost": 1500.0},
            ],
        }
        toolkit = CostToolkit(billing_sources=[source])
        result = await toolkit.query_billing(Environment.PRODUCTION)
        assert result["total_monthly"] == 15000.0
        source.query.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_query_billing_no_sources(self):
        toolkit = CostToolkit()
        result = await toolkit.query_billing(Environment.PRODUCTION)
        assert result["total_monthly"] > 0
        assert "by_service" in result
        assert len(result["resource_costs"]) > 0

    @pytest.mark.asyncio
    async def test_query_billing_source_failure(self):
        source = AsyncMock()
        source.query.side_effect = RuntimeError("billing API down")
        toolkit = CostToolkit(billing_sources=[source])
        result = await toolkit.query_billing(Environment.PRODUCTION)
        # Falls back to stub data
        assert result["total_monthly"] > 0

    @pytest.mark.asyncio
    async def test_get_resource_inventory_no_router(self):
        toolkit = CostToolkit()
        result = await toolkit.get_resource_inventory(Environment.PRODUCTION)
        assert result["total_count"] > 0
        assert len(result["resources"]) > 0

    @pytest.mark.asyncio
    async def test_detect_anomalies(self):
        toolkit = CostToolkit()
        resources = [
            {"resource_id": "r1", "service": "compute", "daily_cost": 100, "monthly_cost": 3000, "usage_percent": 10},
            {"resource_id": "r2", "service": "compute", "daily_cost": 5, "monthly_cost": 150, "usage_percent": 90},
        ]
        result = await toolkit.detect_anomalies(resources)
        assert result["total_anomalies"] > 0
        # r1 has low usage + high cost — should be flagged
        anomaly_ids = [a["resource_id"] for a in result["anomalies"]]
        assert "r1" in anomaly_ids

    @pytest.mark.asyncio
    async def test_detect_anomalies_no_issues(self):
        toolkit = CostToolkit()
        resources = [
            {"resource_id": "r1", "service": "compute", "daily_cost": 5, "monthly_cost": 150, "usage_percent": 80},
        ]
        result = await toolkit.detect_anomalies(resources)
        # Low cost, high usage — no anomalies from the unused check
        unused = [a for a in result["anomalies"] if a["anomaly_type"] == "unused"]
        assert len(unused) == 0

    @pytest.mark.asyncio
    async def test_get_optimization_opportunities(self):
        toolkit = CostToolkit()
        resources = [
            {"resource_id": "r1", "service": "compute", "daily_cost": 50, "monthly_cost": 1500, "usage_percent": 20},
            {"resource_id": "r2", "service": "compute", "daily_cost": 50, "monthly_cost": 1500, "usage_percent": 90},
        ]
        result = await toolkit.get_optimization_opportunities(resources)
        assert result["total_recommendations"] > 0
        # r1 is underutilized — should get rightsizing recommendation
        rec_ids = [r["resource_id"] for r in result["recommendations"]]
        assert "r1" in rec_ids

    @pytest.mark.asyncio
    async def test_get_optimization_no_opportunities(self):
        toolkit = CostToolkit()
        resources = [
            {"resource_id": "r1", "service": "compute", "daily_cost": 50, "monthly_cost": 1500, "usage_percent": 90},
        ]
        result = await toolkit.get_optimization_opportunities(resources)
        assert result["total_recommendations"] == 0

    @pytest.mark.asyncio
    async def test_get_automation_savings(self):
        toolkit = CostToolkit()
        result = await toolkit.get_automation_savings(period="30d", engineer_hourly_rate=100.0)
        assert result["total_hours_saved"] > 0
        assert result["automation_savings_usd"] > 0
        assert result["engineer_hourly_rate"] == 100.0


# ===========================================================================
# Node Tests
# ===========================================================================


class TestGatherCostsNode:
    """Tests for gather_costs node."""

    @pytest.mark.asyncio
    async def test_gather_costs(self):
        toolkit = CostToolkit()
        set_toolkit(toolkit)

        state = CostAnalysisState(
            analysis_id="test-001",
            target_environment=Environment.PRODUCTION,
            period="30d",
        )
        result = await gather_costs(state)

        assert result["total_monthly_spend"] > 0
        assert len(result["resource_costs"]) > 0
        assert result["current_step"] == "gather_costs"
        assert len(result["reasoning_chain"]) == 1

        set_toolkit(None)

    @pytest.mark.asyncio
    async def test_gather_costs_builds_resource_models(self):
        toolkit = CostToolkit()
        set_toolkit(toolkit)

        state = CostAnalysisState(analysis_id="test-002")
        result = await gather_costs(state)

        for rc in result["resource_costs"]:
            assert isinstance(rc, ResourceCost)
            assert rc.daily_cost >= 0

        set_toolkit(None)


class TestDetectAnomaliesNode:
    """Tests for detect_anomalies node."""

    @pytest.mark.asyncio
    async def test_detect_with_anomalies(self):
        toolkit = CostToolkit()
        set_toolkit(toolkit)

        state = CostAnalysisState(
            analysis_id="test-003",
            resource_costs=[
                ResourceCost(resource_id="r1", resource_type="instance", service="compute", environment=Environment.PRODUCTION, provider="aws", daily_cost=100, monthly_cost=3000, usage_percent=5),
            ],
            reasoning_chain=[],
        )
        result = await detect_anomalies(state)

        assert len(result["cost_anomalies"]) > 0
        assert result["current_step"] == "detect_anomalies"

        set_toolkit(None)

    @pytest.mark.asyncio
    async def test_detect_llm_failure_graceful(self):
        toolkit = CostToolkit()
        set_toolkit(toolkit)

        state = CostAnalysisState(
            analysis_id="test-004",
            resource_costs=[
                ResourceCost(resource_id="r1", resource_type="instance", service="compute", environment=Environment.PRODUCTION, provider="aws", daily_cost=100, monthly_cost=3000, usage_percent=5),
            ],
            reasoning_chain=[],
        )

        with patch("shieldops.agents.cost.nodes.llm_structured", side_effect=RuntimeError("LLM down")):
            result = await detect_anomalies(state)

        # Should still return anomalies even if LLM fails
        assert result["current_step"] == "detect_anomalies"
        assert len(result["reasoning_chain"]) == 1

        set_toolkit(None)


class TestRecommendOptimizationsNode:
    """Tests for recommend_optimizations node."""

    @pytest.mark.asyncio
    async def test_recommend_with_underutilized(self):
        toolkit = CostToolkit()
        set_toolkit(toolkit)

        state = CostAnalysisState(
            analysis_id="test-005",
            resource_costs=[
                ResourceCost(resource_id="r1", resource_type="instance", service="compute", environment=Environment.PRODUCTION, provider="aws", daily_cost=50, monthly_cost=1500, usage_percent=20),
            ],
            reasoning_chain=[],
        )
        result = await recommend_optimizations(state)

        assert len(result["optimization_recommendations"]) > 0
        assert result["total_potential_savings"] > 0
        assert result["current_step"] == "recommend_optimizations"

        set_toolkit(None)

    @pytest.mark.asyncio
    async def test_recommend_no_opportunities(self):
        toolkit = CostToolkit()
        set_toolkit(toolkit)

        state = CostAnalysisState(
            analysis_id="test-006",
            resource_costs=[
                ResourceCost(resource_id="r1", resource_type="instance", service="compute", environment=Environment.PRODUCTION, provider="aws", daily_cost=50, monthly_cost=1500, usage_percent=90),
            ],
            reasoning_chain=[],
        )
        result = await recommend_optimizations(state)

        assert len(result["optimization_recommendations"]) == 0
        assert result["total_potential_savings"] == 0

        set_toolkit(None)


class TestSynthesizeSavingsNode:
    """Tests for synthesize_savings node."""

    @pytest.mark.asyncio
    async def test_synthesize_full(self):
        toolkit = CostToolkit()
        set_toolkit(toolkit)

        state = CostAnalysisState(
            analysis_id="test-007",
            analysis_start=datetime.now(timezone.utc) - timedelta(seconds=5),
            total_monthly_spend=10000.0,
            total_daily_spend=333.0,
            total_potential_savings=2000.0,
            spend_by_service={"compute": 7000, "storage": 3000},
            cost_anomalies=[
                CostAnomaly(resource_id="r1", service="compute", anomaly_type="spike", severity="critical", expected_daily_cost=50, actual_daily_cost=150, deviation_percent=200),
            ],
            critical_anomaly_count=1,
            optimization_recommendations=[
                OptimizationRecommendation(id="opt-1", category="rightsizing", resource_id="r1", service="compute", current_monthly_cost=1500, projected_monthly_cost=900, monthly_savings=600, confidence=0.8),
            ],
            reasoning_chain=[],
        )

        with patch("shieldops.agents.cost.nodes.llm_structured", side_effect=RuntimeError("LLM down")):
            result = await synthesize_savings(state)

        assert result["cost_savings"] is not None
        assert isinstance(result["cost_savings"], CostSavings)
        assert result["cost_savings"].total_monthly_spend == 10000.0
        assert result["current_step"] == "complete"

        set_toolkit(None)

    @pytest.mark.asyncio
    async def test_synthesize_aggregates_by_category(self):
        toolkit = CostToolkit()
        set_toolkit(toolkit)

        state = CostAnalysisState(
            analysis_id="test-008",
            analysis_start=datetime.now(timezone.utc),
            total_monthly_spend=5000.0,
            total_potential_savings=1000.0,
            optimization_recommendations=[
                OptimizationRecommendation(id="opt-1", category="rightsizing", resource_id="r1", service="compute", current_monthly_cost=1000, projected_monthly_cost=600, monthly_savings=400, confidence=0.8),
                OptimizationRecommendation(id="opt-2", category="rightsizing", resource_id="r2", service="compute", current_monthly_cost=800, projected_monthly_cost=500, monthly_savings=300, confidence=0.7),
                OptimizationRecommendation(id="opt-3", category="unused_resources", resource_id="r3", service="storage", current_monthly_cost=300, projected_monthly_cost=0, monthly_savings=300, confidence=0.9),
            ],
            reasoning_chain=[],
        )

        with patch("shieldops.agents.cost.nodes.llm_structured", side_effect=RuntimeError("skip")):
            result = await synthesize_savings(state)

        savings = result["cost_savings"]
        assert savings.savings_by_category["rightsizing"] == 700
        assert savings.savings_by_category["unused_resources"] == 300

        set_toolkit(None)


# ===========================================================================
# Graph Routing Tests
# ===========================================================================


class TestGraphRouting:
    """Tests for conditional routing functions."""

    def test_should_detect_anomalies_full(self):
        state = CostAnalysisState(analysis_type="full")
        assert should_detect_anomalies(state) == "detect_anomalies"

    def test_should_skip_anomalies_optimization_only(self):
        state = CostAnalysisState(analysis_type="optimization_only")
        assert should_detect_anomalies(state) == "recommend_optimizations"

    def test_should_skip_anomalies_savings_only(self):
        state = CostAnalysisState(analysis_type="savings_only")
        assert should_detect_anomalies(state) == "synthesize_savings"

    def test_should_skip_anomalies_on_error(self):
        state = CostAnalysisState(analysis_type="full", error="something broke")
        assert should_detect_anomalies(state) == "synthesize_savings"

    def test_should_recommend_optimizations_full(self):
        state = CostAnalysisState(analysis_type="full")
        assert should_recommend_optimizations(state) == "recommend_optimizations"

    def test_should_skip_optimizations_anomaly_only(self):
        state = CostAnalysisState(analysis_type="anomaly_only")
        assert should_recommend_optimizations(state) == "synthesize_savings"

    def test_should_skip_optimizations_on_error(self):
        state = CostAnalysisState(analysis_type="full", error="broken")
        assert should_recommend_optimizations(state) == "synthesize_savings"


class TestGraphConstruction:
    """Tests for graph construction."""

    def test_create_cost_graph(self):
        graph = create_cost_graph()
        compiled = graph.compile()
        assert compiled is not None


# ===========================================================================
# Runner Tests
# ===========================================================================


class TestCostRunner:
    """Tests for CostRunner."""

    def test_runner_init(self):
        runner = CostRunner()
        assert runner.list_analyses() == []

    @pytest.mark.asyncio
    async def test_analyze_returns_state(self):
        runner = CostRunner()

        with patch.object(runner, "_app") as mock_app:
            mock_app.ainvoke = AsyncMock(return_value=CostAnalysisState(
                analysis_id="cost-test",
                analysis_type="full",
                current_step="complete",
                total_monthly_spend=10000.0,
                analysis_start=datetime.now(timezone.utc),
            ).model_dump())

            result = await runner.analyze(environment=Environment.PRODUCTION)

        assert result.current_step == "complete"
        assert len(runner.list_analyses()) == 1

    @pytest.mark.asyncio
    async def test_analyze_handles_error(self):
        runner = CostRunner()

        with patch.object(runner, "_app") as mock_app:
            mock_app.ainvoke = AsyncMock(side_effect=RuntimeError("graph failed"))
            result = await runner.analyze()

        assert result.current_step == "failed"
        assert result.error == "graph failed"
        assert len(runner.list_analyses()) == 1

    def test_list_analyses_empty(self):
        runner = CostRunner()
        assert runner.list_analyses() == []

    def test_get_analysis_not_found(self):
        runner = CostRunner()
        assert runner.get_analysis("nonexistent") is None


# ===========================================================================
# API Tests
# ===========================================================================


class TestCostAPI:
    """Tests for cost API endpoints."""

    def _make_app(self):
        from shieldops.api.routes import cost as cost_module

        runner = CostRunner()
        cost_module.set_runner(runner)

        from shieldops.api.app import create_app
        from shieldops.api.auth.dependencies import get_current_user
        from shieldops.api.auth.models import UserResponse, UserRole

        app = create_app()

        def _mock_admin_user():
            return UserResponse(
                id="test-admin", email="admin@test.com", name="Test Admin",
                role=UserRole.ADMIN, is_active=True,
            )

        app.dependency_overrides[get_current_user] = _mock_admin_user

        return TestClient(app), runner

    def test_list_analyses(self):
        client, _ = self._make_app()
        resp = client.get("/api/v1/cost/analyses")
        assert resp.status_code == 200
        assert resp.json()["analyses"] == []

    def test_get_analysis_not_found(self):
        client, _ = self._make_app()
        resp = client.get("/api/v1/cost/analyses/nonexistent")
        assert resp.status_code == 404

    def test_get_analysis_found(self):
        client, runner = self._make_app()
        state = CostAnalysisState(
            analysis_id="cost-123",
            analysis_type="full",
            current_step="complete",
            total_monthly_spend=8000.0,
        )
        runner._analyses["cost-123"] = state

        resp = client.get("/api/v1/cost/analyses/cost-123")
        assert resp.status_code == 200
        assert resp.json()["analysis_id"] == "cost-123"

    def test_trigger_analysis_async(self):
        client, _ = self._make_app()
        resp = client.post("/api/v1/cost/analyses", json={
            "environment": "production",
            "analysis_type": "full",
            "period": "30d",
        })
        assert resp.status_code == 202
        assert resp.json()["status"] == "accepted"

    def test_trigger_analysis_sync(self):
        client, runner = self._make_app()

        async def mock_analyze(**kwargs):
            return CostAnalysisState(
                analysis_id="cost-sync",
                current_step="complete",
                total_monthly_spend=5000.0,
            )

        runner.analyze = mock_analyze

        resp = client.post("/api/v1/cost/analyses/sync", json={
            "environment": "staging",
            "analysis_type": "full",
        })
        assert resp.status_code == 200
        assert resp.json()["current_step"] == "complete"

    def test_list_anomalies_no_analyses(self):
        client, _ = self._make_app()
        resp = client.get("/api/v1/cost/anomalies")
        assert resp.status_code == 200
        assert resp.json()["anomalies"] == []

    def test_list_anomalies_with_data(self):
        client, runner = self._make_app()
        state = CostAnalysisState(
            analysis_id="cost-anom",
            current_step="complete",
            cost_anomalies=[
                CostAnomaly(resource_id="r1", service="compute", anomaly_type="spike", severity="critical", expected_daily_cost=50, actual_daily_cost=150, deviation_percent=200),
                CostAnomaly(resource_id="r2", service="storage", anomaly_type="unused", severity="medium", expected_daily_cost=10, actual_daily_cost=30, deviation_percent=200),
            ],
        )
        runner._analyses["cost-anom"] = state

        resp = client.get("/api/v1/cost/anomalies")
        assert resp.status_code == 200
        assert resp.json()["total"] == 2

    def test_list_anomalies_filter_severity(self):
        client, runner = self._make_app()
        state = CostAnalysisState(
            analysis_id="cost-anom2",
            current_step="complete",
            cost_anomalies=[
                CostAnomaly(resource_id="r1", service="compute", anomaly_type="spike", severity="critical", expected_daily_cost=50, actual_daily_cost=150, deviation_percent=200),
                CostAnomaly(resource_id="r2", service="storage", anomaly_type="unused", severity="medium", expected_daily_cost=10, actual_daily_cost=30, deviation_percent=200),
            ],
        )
        runner._analyses["cost-anom2"] = state

        resp = client.get("/api/v1/cost/anomalies?severity=critical")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    def test_list_optimizations(self):
        client, runner = self._make_app()
        state = CostAnalysisState(
            analysis_id="cost-opt",
            current_step="complete",
            total_potential_savings=600.0,
            optimization_recommendations=[
                OptimizationRecommendation(id="opt-1", category="rightsizing", resource_id="r1", service="compute", current_monthly_cost=1500, projected_monthly_cost=900, monthly_savings=600, confidence=0.8),
            ],
        )
        runner._analyses["cost-opt"] = state

        resp = client.get("/api/v1/cost/optimizations")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1
        assert resp.json()["total_potential_savings"] == 600.0

    def test_list_optimizations_filter_category(self):
        client, runner = self._make_app()
        state = CostAnalysisState(
            analysis_id="cost-opt2",
            current_step="complete",
            total_potential_savings=1000.0,
            optimization_recommendations=[
                OptimizationRecommendation(id="opt-1", category="rightsizing", resource_id="r1", service="compute", current_monthly_cost=1500, projected_monthly_cost=900, monthly_savings=600, confidence=0.8),
                OptimizationRecommendation(id="opt-2", category="unused_resources", resource_id="r2", service="storage", current_monthly_cost=400, projected_monthly_cost=0, monthly_savings=400, confidence=0.9),
            ],
        )
        runner._analyses["cost-opt2"] = state

        resp = client.get("/api/v1/cost/optimizations?category=unused_resources")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    def test_get_savings_no_analyses(self):
        client, _ = self._make_app()
        resp = client.get("/api/v1/cost/savings")
        assert resp.status_code == 200
        assert "message" in resp.json()

    def test_get_savings_with_data(self):
        client, runner = self._make_app()
        state = CostAnalysisState(
            analysis_id="cost-sav",
            current_step="complete",
            cost_savings=CostSavings(
                period="30d",
                total_monthly_spend=10000.0,
                total_potential_savings=2000.0,
                hours_saved_by_automation=100,
                automation_savings_usd=7500.0,
            ),
        )
        runner._analyses["cost-sav"] = state

        resp = client.get("/api/v1/cost/savings")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_monthly_spend"] == 10000.0
        assert data["automation_savings_usd"] == 7500.0


# ===========================================================================
# Model Tests
# ===========================================================================


class TestCostModels:
    """Tests for cost data models."""

    def test_resource_cost(self):
        rc = ResourceCost(
            resource_id="i-1",
            resource_type="instance",
            service="compute",
            environment=Environment.PRODUCTION,
            provider="aws",
            daily_cost=48.0,
            monthly_cost=1440.0,
            usage_percent=35.0,
        )
        assert rc.daily_cost == 48.0
        assert rc.environment == Environment.PRODUCTION

    def test_cost_anomaly(self):
        a = CostAnomaly(
            resource_id="r1",
            service="compute",
            anomaly_type="spike",
            severity="critical",
            expected_daily_cost=50.0,
            actual_daily_cost=150.0,
            deviation_percent=200.0,
        )
        assert a.severity == "critical"
        assert a.deviation_percent == 200.0

    def test_optimization_recommendation(self):
        rec = OptimizationRecommendation(
            id="opt-1",
            category="rightsizing",
            resource_id="r1",
            service="compute",
            current_monthly_cost=1500.0,
            projected_monthly_cost=900.0,
            monthly_savings=600.0,
            confidence=0.8,
        )
        assert rec.monthly_savings == 600.0
        assert rec.confidence == 0.8

    def test_cost_savings(self):
        s = CostSavings(
            total_monthly_spend=10000.0,
            total_potential_savings=2000.0,
            hours_saved_by_automation=100,
            automation_savings_usd=7500.0,
        )
        assert s.optimized_monthly_spend == 0.0  # default
        assert s.engineer_hourly_rate == 75.0

    def test_cost_step(self):
        step = CostStep(
            step_number=1,
            action="gather_costs",
            input_summary="test input",
            output_summary="test output",
            duration_ms=100,
        )
        assert step.step_number == 1

    def test_cost_analysis_state_defaults(self):
        state = CostAnalysisState()
        assert state.analysis_type == "full"
        assert state.target_environment == Environment.PRODUCTION
        assert state.resource_costs == []
        assert state.cost_anomalies == []
        assert state.optimization_recommendations == []
        assert state.current_step == "pending"
        assert state.error is None
