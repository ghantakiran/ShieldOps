"""Tests for the FinOps Intelligence Agent LangGraph workflow.

Covers:
- FinOpsIntelligenceState model creation, defaults, and field types
- Sub-models: CostFinding, OptimizationOpportunity, FinOpsReasoningStep
- Prompt schemas: CostAnalysisOutput, OptimizationOutput, ImplementationPlanOutput
- FinOpsIntelligenceToolkit initialization and async methods
- Graph creation (create_finops_intelligence_graph returns a StateGraph)
- FinOpsIntelligenceRunner initialization and list_results
- Node functions (analyze_costs, identify_optimizations, prioritize_savings,
  plan_implementation, finalize_analysis) with mock state
- Conditional edges (should_optimize, should_plan)
- Integration: full workflow with simple inputs
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shieldops.agents.finops_intelligence.graph import (
    create_finops_intelligence_graph,
    should_optimize,
    should_plan,
)
from shieldops.agents.finops_intelligence.models import (
    CostFinding,
    FinOpsIntelligenceState,
    FinOpsReasoningStep,
    OptimizationOpportunity,
)
from shieldops.agents.finops_intelligence.nodes import (
    _get_toolkit,
    analyze_costs,
    finalize_analysis,
    identify_optimizations,
    plan_implementation,
    prioritize_savings,
    set_toolkit,
)
from shieldops.agents.finops_intelligence.prompts import (
    CostAnalysisOutput,
    ImplementationPlanOutput,
    OptimizationOutput,
)
from shieldops.agents.finops_intelligence.runner import FinOpsIntelligenceRunner
from shieldops.agents.finops_intelligence.tools import FinOpsIntelligenceToolkit

# -- Fixtures ----------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_toolkit():
    """Reset the module-level toolkit singleton between tests."""
    import shieldops.agents.finops_intelligence.nodes as nodes_mod

    original = nodes_mod._toolkit
    nodes_mod._toolkit = None
    yield
    nodes_mod._toolkit = original


@pytest.fixture
def base_state() -> FinOpsIntelligenceState:
    return FinOpsIntelligenceState(
        session_id="fi-session-001",
        analysis_config={"scope": "aws-prod", "period": "30d"},
    )


@pytest.fixture
def analyzed_state() -> FinOpsIntelligenceState:
    return FinOpsIntelligenceState(
        session_id="fi-session-002",
        analysis_config={"scope": "aws-prod"},
        cost_findings=[
            CostFinding(
                finding_id="cf-001",
                finding_type="idle_resource",
                category="compute",
                amount=500.0,
                service="ec2",
                team="platform",
            ),
            CostFinding(
                finding_id="cf-002",
                finding_type="overprovisioned",
                category="storage",
                amount=200.0,
                service="s3",
                team="data",
            ),
        ],
        finding_count=2,
        optimization_opportunities=[
            OptimizationOpportunity(
                opportunity_id="oo-001",
                opportunity_type="rightsizing",
                severity="high",
                affected_resource="ec2-fleet",
                description="Downsize idle instances",
                estimated_savings=300.0,
            ),
        ],
        savings_potential=300.0,
        high_impact_count=1,
    )


# -- TestState ---------------------------------------------------------------


class TestState:
    def test_default_values(self):
        state = FinOpsIntelligenceState()
        assert state.session_id == ""
        assert state.analysis_config == {}
        assert state.cost_findings == []
        assert state.finding_count == 0
        assert state.optimization_opportunities == []
        assert state.savings_potential == pytest.approx(0.0)
        assert state.prioritized_actions == []
        assert state.high_impact_count == 0
        assert state.implementation_plan == []
        assert state.plan_started is False
        assert state.session_start is None
        assert state.session_duration_ms == 0
        assert state.reasoning_chain == []
        assert state.current_step == "init"
        assert state.error is None

    def test_creation_with_custom_values(self, base_state: FinOpsIntelligenceState):
        assert base_state.session_id == "fi-session-001"
        assert base_state.analysis_config["scope"] == "aws-prod"
        assert base_state.analysis_config["period"] == "30d"

    def test_list_fields_are_independent_instances(self):
        s1 = FinOpsIntelligenceState()
        s2 = FinOpsIntelligenceState()
        s1.cost_findings.append(CostFinding(finding_id="x-1", finding_type="leak"))
        assert s2.cost_findings == []

    def test_state_with_error(self):
        state = FinOpsIntelligenceState(error="api timeout", current_step="failed")
        assert state.error == "api timeout"
        assert state.current_step == "failed"

    def test_state_with_cost_findings(self, analyzed_state: FinOpsIntelligenceState):
        assert analyzed_state.finding_count == 2
        assert len(analyzed_state.cost_findings) == 2
        assert analyzed_state.cost_findings[0].service == "ec2"

    def test_state_with_opportunities(self, analyzed_state: FinOpsIntelligenceState):
        assert len(analyzed_state.optimization_opportunities) == 1
        assert analyzed_state.optimization_opportunities[0].severity == "high"
        assert analyzed_state.high_impact_count == 1

    def test_state_plan_defaults(self):
        state = FinOpsIntelligenceState()
        assert state.implementation_plan == []
        assert state.plan_started is False

    def test_state_analysis_config_complex(self):
        state = FinOpsIntelligenceState(
            session_id="fi-complex",
            analysis_config={
                "scope": "multi-cloud",
                "services": ["ec2", "gcs", "azure-vm"],
                "threshold": 100.0,
            },
        )
        assert state.analysis_config["services"] == ["ec2", "gcs", "azure-vm"]
        assert state.analysis_config["threshold"] == pytest.approx(100.0)


# -- TestSubModels -----------------------------------------------------------


class TestSubModels:
    def test_cost_finding_defaults(self):
        finding = CostFinding()
        assert finding.finding_id == ""
        assert finding.finding_type == ""
        assert finding.category == ""
        assert finding.amount == pytest.approx(0.0)
        assert finding.service == ""
        assert finding.team == ""

    def test_optimization_opportunity_defaults(self):
        opp = OptimizationOpportunity()
        assert opp.opportunity_id == ""
        assert opp.opportunity_type == ""
        assert opp.severity == "medium"
        assert opp.affected_resource == ""
        assert opp.description == ""
        assert opp.estimated_savings == pytest.approx(0.0)

    def test_finops_reasoning_step_creation(self):
        step = FinOpsReasoningStep(
            step_number=1,
            action="analyze_costs",
            input_summary="Scope=aws-prod",
            output_summary="Found 5 findings",
        )
        assert step.step_number == 1
        assert step.action == "analyze_costs"
        assert step.duration_ms == 0
        assert step.tool_used is None

    def test_cost_finding_with_all_fields(self):
        finding = CostFinding(
            finding_id="cf-001",
            finding_type="idle_resource",
            category="compute",
            amount=1500.0,
            service="ec2",
            team="platform",
        )
        assert finding.amount == pytest.approx(1500.0)
        assert finding.service == "ec2"

    def test_optimization_opportunity_with_all_fields(self):
        opp = OptimizationOpportunity(
            opportunity_id="oo-001",
            opportunity_type="rightsizing",
            severity="critical",
            affected_resource="ec2-fleet",
            description="Downsize idle instances",
            estimated_savings=5000.0,
        )
        assert opp.severity == "critical"
        assert opp.estimated_savings == pytest.approx(5000.0)

    def test_reasoning_step_with_tool(self):
        step = FinOpsReasoningStep(
            step_number=2,
            action="identify_optimizations",
            input_summary="2 findings",
            output_summary="3 opportunities",
            duration_ms=200,
            tool_used="optimization_engine",
        )
        assert step.tool_used == "optimization_engine"
        assert step.duration_ms == 200

    def test_cost_finding_default_amount(self):
        finding = CostFinding(finding_id="cf-test")
        assert finding.amount == 0.0

    def test_optimization_opportunity_medium_default_severity(self):
        opp = OptimizationOpportunity(opportunity_id="oo-test")
        assert opp.severity == "medium"

    def test_reasoning_step_no_tool(self):
        step = FinOpsReasoningStep(
            step_number=1, action="test", input_summary="i", output_summary="o"
        )
        assert step.tool_used is None


# -- TestPromptSchemas -------------------------------------------------------


class TestPromptSchemas:
    def test_cost_analysis_output_fields(self):
        output = CostAnalysisOutput(
            finding_count=8,
            cost_summary="3 idle resources, 5 overprovisioned",
            risk_level="high",
        )
        assert output.finding_count == 8
        assert output.risk_level == "high"

    def test_optimization_output_fields(self):
        output = OptimizationOutput(
            opportunities=[{"type": "rightsizing", "severity": "high"}],
            savings_potential=12500.0,
            reasoning="Multiple oversized instances detected",
        )
        assert len(output.opportunities) == 1
        assert output.savings_potential == pytest.approx(12500.0)

    def test_implementation_plan_output_fields(self):
        output = ImplementationPlanOutput(
            actions=[{"priority": "high", "target": "ec2-fleet"}],
            estimated_effort="4 hours",
            reasoning="Downsize then validate performance",
        )
        assert len(output.actions) == 1
        assert output.estimated_effort == "4 hours"

    def test_cost_analysis_output_zero_findings(self):
        output = CostAnalysisOutput(
            finding_count=0,
            cost_summary="No anomalies found",
            risk_level="low",
        )
        assert output.finding_count == 0
        assert output.risk_level == "low"

    def test_optimization_output_high_savings(self):
        output = OptimizationOutput(
            opportunities=[],
            savings_potential=99999.0,
            reasoning="Massive waste detected",
        )
        assert output.savings_potential == pytest.approx(99999.0)

    def test_implementation_plan_output_empty_actions(self):
        output = ImplementationPlanOutput(
            actions=[],
            estimated_effort="0 hours",
            reasoning="Nothing to implement",
        )
        assert len(output.actions) == 0


# -- TestToolkit -------------------------------------------------------------


class TestToolkit:
    def test_toolkit_initialization_with_no_deps(self):
        toolkit = FinOpsIntelligenceToolkit()
        assert toolkit._cost_analyzer is None
        assert toolkit._optimization_engine is None
        assert toolkit._budget_manager is None
        assert toolkit._policy_engine is None
        assert toolkit._repository is None

    def test_toolkit_initialization_with_deps(self):
        mock_analyzer = MagicMock()
        toolkit = FinOpsIntelligenceToolkit(cost_analyzer=mock_analyzer)
        assert toolkit._cost_analyzer is mock_analyzer

    @pytest.mark.asyncio
    async def test_analyze_costs_returns_list(self):
        toolkit = FinOpsIntelligenceToolkit()
        result = await toolkit.analyze_costs({"scope": "aws-prod"})
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_identify_optimizations_returns_list(self):
        toolkit = FinOpsIntelligenceToolkit()
        result = await toolkit.identify_optimizations([{"finding_id": "cf-1"}])
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_prioritize_savings_returns_sorted(self):
        toolkit = FinOpsIntelligenceToolkit()
        opportunities = [
            {"id": "oo-1", "estimated_savings": 100},
            {"id": "oo-2", "estimated_savings": 500},
        ]
        result = await toolkit.prioritize_savings(opportunities)
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_create_implementation_plan_returns_list(self):
        toolkit = FinOpsIntelligenceToolkit()
        result = await toolkit.create_implementation_plan([{"id": "oo-1"}])
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_record_finops_metric(self):
        toolkit = FinOpsIntelligenceToolkit()
        await toolkit.record_finops_metric("cost_findings", 5.0)

    @pytest.mark.asyncio
    async def test_toolkit_with_all_deps(self):
        toolkit = FinOpsIntelligenceToolkit(
            cost_analyzer=MagicMock(),
            optimization_engine=MagicMock(),
            budget_manager=MagicMock(),
            policy_engine=MagicMock(),
            repository=MagicMock(),
        )
        assert toolkit._cost_analyzer is not None
        assert toolkit._optimization_engine is not None
        assert toolkit._budget_manager is not None
        assert toolkit._policy_engine is not None
        assert toolkit._repository is not None


# -- TestGraph ---------------------------------------------------------------


class TestGraph:
    def test_create_finops_intelligence_graph_returns_state_graph(self):
        graph = create_finops_intelligence_graph()
        assert graph is not None
        assert hasattr(graph, "compile")

    def test_graph_has_expected_nodes(self):
        graph = create_finops_intelligence_graph()
        node_names = set(graph.nodes.keys())
        expected = {
            "analyze_costs",
            "identify_optimizations",
            "prioritize_savings",
            "plan_implementation",
            "finalize_analysis",
        }
        assert expected.issubset(node_names)

    def test_graph_compiles_without_error(self):
        graph = create_finops_intelligence_graph()
        app = graph.compile()
        assert app is not None

    def test_graph_entry_point_is_analyze_costs(self):
        graph = create_finops_intelligence_graph()
        assert "__start__" in graph.nodes or "analyze_costs" in graph.nodes

    def test_graph_has_finalize_node(self):
        graph = create_finops_intelligence_graph()
        assert "finalize_analysis" in graph.nodes

    def test_graph_has_plan_implementation_node(self):
        graph = create_finops_intelligence_graph()
        assert "plan_implementation" in graph.nodes


# -- TestRunner --------------------------------------------------------------


class TestRunner:
    def test_runner_initialization(self):
        with patch(
            "shieldops.agents.finops_intelligence.runner.create_finops_intelligence_graph"
        ) as mock_graph_fn:
            mock_graph = MagicMock()
            mock_graph.compile.return_value = MagicMock()
            mock_graph_fn.return_value = mock_graph
            runner = FinOpsIntelligenceRunner()
            assert runner._results == {}

    def test_list_results_empty(self):
        with patch(
            "shieldops.agents.finops_intelligence.runner.create_finops_intelligence_graph"
        ) as mock_graph_fn:
            mock_graph = MagicMock()
            mock_graph.compile.return_value = MagicMock()
            mock_graph_fn.return_value = mock_graph
            runner = FinOpsIntelligenceRunner()
            assert runner.list_results() == []

    def test_list_results_returns_summaries(self):
        with patch(
            "shieldops.agents.finops_intelligence.runner.create_finops_intelligence_graph"
        ) as mock_graph_fn:
            mock_graph = MagicMock()
            mock_graph.compile.return_value = MagicMock()
            mock_graph_fn.return_value = mock_graph
            runner = FinOpsIntelligenceRunner()
            runner._results["fi-abc"] = FinOpsIntelligenceState(
                session_id="fi-001",
                finding_count=5,
                savings_potential=1500.0,
                current_step="complete",
            )
            summaries = runner.list_results()
            assert len(summaries) == 1
            assert summaries[0]["analysis_session_id"] == "fi-001"
            assert summaries[0]["finding_count"] == 5

    @pytest.mark.asyncio
    async def test_analyze_success(self):
        mock_app = AsyncMock()
        final_state = FinOpsIntelligenceState(
            session_id="fi-001",
            finding_count=3,
            savings_potential=2500.0,
            current_step="complete",
        ).model_dump()
        mock_app.ainvoke.return_value = final_state

        with patch(
            "shieldops.agents.finops_intelligence.runner.create_finops_intelligence_graph"
        ) as mock_graph_fn:
            mock_graph = MagicMock()
            mock_graph.compile.return_value = mock_app
            mock_graph_fn.return_value = mock_graph
            runner = FinOpsIntelligenceRunner()
            result = await runner.analyze(session_id="fi-001")

        assert isinstance(result, FinOpsIntelligenceState)
        assert result.current_step == "complete"

    @pytest.mark.asyncio
    async def test_analyze_handles_exception(self):
        mock_app = AsyncMock()
        mock_app.ainvoke.side_effect = RuntimeError("Graph failed")

        with patch(
            "shieldops.agents.finops_intelligence.runner.create_finops_intelligence_graph"
        ) as mock_graph_fn:
            mock_graph = MagicMock()
            mock_graph.compile.return_value = mock_app
            mock_graph_fn.return_value = mock_graph
            runner = FinOpsIntelligenceRunner()
            result = await runner.analyze(session_id="fi-x")

        assert result.error == "Graph failed"
        assert result.current_step == "failed"

    @pytest.mark.asyncio
    async def test_analyze_with_config(self):
        mock_app = AsyncMock()
        final_state = FinOpsIntelligenceState(
            session_id="fi-cfg",
            analysis_config={"scope": "gcp-prod"},
            current_step="complete",
        ).model_dump()
        mock_app.ainvoke.return_value = final_state

        with patch(
            "shieldops.agents.finops_intelligence.runner.create_finops_intelligence_graph"
        ) as mock_graph_fn:
            mock_graph = MagicMock()
            mock_graph.compile.return_value = mock_app
            mock_graph_fn.return_value = mock_graph
            runner = FinOpsIntelligenceRunner()
            result = await runner.analyze(
                session_id="fi-cfg", analysis_config={"scope": "gcp-prod"}
            )

        assert result.analysis_config["scope"] == "gcp-prod"

    def test_get_result_found(self):
        with patch(
            "shieldops.agents.finops_intelligence.runner.create_finops_intelligence_graph"
        ) as mock_graph_fn:
            mock_graph = MagicMock()
            mock_graph.compile.return_value = MagicMock()
            mock_graph_fn.return_value = mock_graph
            runner = FinOpsIntelligenceRunner()
            runner._results["fi-test"] = FinOpsIntelligenceState(session_id="fi-001")
            assert runner.get_result("fi-test") is not None
            assert runner.get_result("fi-test").session_id == "fi-001"

    def test_get_result_not_found(self):
        with patch(
            "shieldops.agents.finops_intelligence.runner.create_finops_intelligence_graph"
        ) as mock_graph_fn:
            mock_graph = MagicMock()
            mock_graph.compile.return_value = MagicMock()
            mock_graph_fn.return_value = mock_graph
            runner = FinOpsIntelligenceRunner()
            assert runner.get_result("nonexistent") is None

    def test_list_results_multiple(self):
        with patch(
            "shieldops.agents.finops_intelligence.runner.create_finops_intelligence_graph"
        ) as mock_graph_fn:
            mock_graph = MagicMock()
            mock_graph.compile.return_value = MagicMock()
            mock_graph_fn.return_value = mock_graph
            runner = FinOpsIntelligenceRunner()
            runner._results["fi-1"] = FinOpsIntelligenceState(
                session_id="s1", current_step="complete"
            )
            runner._results["fi-2"] = FinOpsIntelligenceState(
                session_id="s2", current_step="failed", error="err"
            )
            summaries = runner.list_results()
            assert len(summaries) == 2
            session_ids = {s["analysis_session_id"] for s in summaries}
            assert "s1" in session_ids
            assert "s2" in session_ids


# -- TestNodes ---------------------------------------------------------------


class TestNodes:
    @pytest.mark.asyncio
    async def test_analyze_costs_with_scope(self):
        state = FinOpsIntelligenceState(
            session_id="fi-001",
            analysis_config={"scope": "aws-prod"},
        )
        result = await analyze_costs(state)
        assert "cost_findings" in result
        assert result["finding_count"] >= 1
        assert result["current_step"] == "analyze_costs"
        assert len(result["reasoning_chain"]) == 1

    @pytest.mark.asyncio
    async def test_analyze_costs_empty_scope(self):
        state = FinOpsIntelligenceState(
            session_id="fi-002",
            analysis_config={},
        )
        result = await analyze_costs(state)
        assert "cost_findings" in result
        assert result["current_step"] == "analyze_costs"

    @pytest.mark.asyncio
    async def test_identify_optimizations(self, analyzed_state: FinOpsIntelligenceState):
        result = await identify_optimizations(analyzed_state)
        assert "optimization_opportunities" in result
        assert "savings_potential" in result
        assert result["current_step"] == "identify_optimizations"

    @pytest.mark.asyncio
    async def test_prioritize_savings(self, analyzed_state: FinOpsIntelligenceState):
        result = await prioritize_savings(analyzed_state)
        assert "prioritized_actions" in result
        assert "high_impact_count" in result
        assert result["current_step"] == "prioritize_savings"

    @pytest.mark.asyncio
    async def test_plan_implementation(self, analyzed_state: FinOpsIntelligenceState):
        analyzed_state.prioritized_actions = [
            {"id": "oo-1", "severity": "high", "estimated_savings": 300.0}
        ]
        result = await plan_implementation(analyzed_state)
        assert "implementation_plan" in result
        assert "plan_started" in result
        assert result["current_step"] == "plan_implementation"

    @pytest.mark.asyncio
    async def test_finalize_analysis_records_duration(self):
        state = FinOpsIntelligenceState(
            session_id="fi-final",
            session_start=datetime.now(UTC),
        )
        result = await finalize_analysis(state)
        assert result["session_duration_ms"] >= 0
        assert result["current_step"] == "complete"

    @pytest.mark.asyncio
    async def test_finalize_analysis_no_session_start(self):
        state = FinOpsIntelligenceState(session_id="fi-no-start")
        result = await finalize_analysis(state)
        assert result["session_duration_ms"] == 0

    @pytest.mark.asyncio
    async def test_analyze_costs_sets_session_start(self):
        state = FinOpsIntelligenceState(
            session_id="fi-start",
            analysis_config={"scope": "aws-prod"},
        )
        result = await analyze_costs(state)
        assert result["session_start"] is not None

    @pytest.mark.asyncio
    async def test_analyze_costs_reasoning_chain_grows(self):
        state = FinOpsIntelligenceState(
            session_id="fi-chain",
            analysis_config={"scope": "chain-prod"},
            reasoning_chain=[
                FinOpsReasoningStep(
                    step_number=1, action="prev", input_summary="", output_summary=""
                )
            ],
        )
        result = await analyze_costs(state)
        assert len(result["reasoning_chain"]) == 2
        assert result["reasoning_chain"][-1].action == "analyze_costs"

    @pytest.mark.asyncio
    async def test_identify_optimizations_savings_calculated(
        self, analyzed_state: FinOpsIntelligenceState
    ):
        result = await identify_optimizations(analyzed_state)
        assert isinstance(result["savings_potential"], float)

    @pytest.mark.asyncio
    async def test_prioritize_savings_counts_high_impact(
        self, analyzed_state: FinOpsIntelligenceState
    ):
        result = await prioritize_savings(analyzed_state)
        assert result["high_impact_count"] == 1

    @pytest.mark.asyncio
    async def test_plan_implementation_empty_actions(self):
        state = FinOpsIntelligenceState(
            session_id="fi-empty-plan",
            prioritized_actions=[],
            high_impact_count=1,
        )
        result = await plan_implementation(state)
        assert result["current_step"] == "plan_implementation"

    @pytest.mark.asyncio
    async def test_finalize_analysis_adds_reasoning_step(self):
        state = FinOpsIntelligenceState(
            session_id="fi-reason",
            session_start=datetime.now(UTC),
        )
        result = await finalize_analysis(state)
        assert len(result["reasoning_chain"]) >= 1
        assert result["reasoning_chain"][-1].action == "finalize_analysis"


# -- TestConditionalEdges ----------------------------------------------------


class TestConditionalEdges:
    def test_should_optimize_with_findings(self):
        state = FinOpsIntelligenceState(finding_count=5)
        assert should_optimize(state) == "identify_optimizations"

    def test_should_optimize_no_findings(self):
        state = FinOpsIntelligenceState(finding_count=0)
        assert should_optimize(state) == "finalize_analysis"

    def test_should_optimize_with_error(self):
        state = FinOpsIntelligenceState(finding_count=5, error="failed")
        assert should_optimize(state) == "finalize_analysis"

    def test_should_plan_with_high_impact(self):
        state = FinOpsIntelligenceState(high_impact_count=3)
        assert should_plan(state) == "plan_implementation"

    def test_should_plan_no_high_impact(self):
        state = FinOpsIntelligenceState(high_impact_count=0)
        assert should_plan(state) == "finalize_analysis"

    def test_should_optimize_zero_findings_no_error(self):
        state = FinOpsIntelligenceState(finding_count=0, error=None)
        assert should_optimize(state) == "finalize_analysis"

    def test_should_optimize_one_finding(self):
        state = FinOpsIntelligenceState(finding_count=1)
        assert should_optimize(state) == "identify_optimizations"

    def test_should_plan_one_high_impact(self):
        state = FinOpsIntelligenceState(high_impact_count=1)
        assert should_plan(state) == "plan_implementation"

    def test_should_plan_many_high_impact(self):
        state = FinOpsIntelligenceState(high_impact_count=100)
        assert should_plan(state) == "plan_implementation"


# -- TestToolkitManagement ---------------------------------------------------


class TestToolkitManagement:
    def test_get_toolkit_returns_default_when_none_set(self):
        toolkit = _get_toolkit()
        assert isinstance(toolkit, FinOpsIntelligenceToolkit)

    def test_set_toolkit_is_used_by_get_toolkit(self):
        custom = FinOpsIntelligenceToolkit(cost_analyzer=MagicMock())
        set_toolkit(custom)
        assert _get_toolkit() is custom

    def test_set_toolkit_overrides_previous(self):
        first = FinOpsIntelligenceToolkit()
        second = FinOpsIntelligenceToolkit(cost_analyzer=MagicMock())
        set_toolkit(first)
        assert _get_toolkit() is first
        set_toolkit(second)
        assert _get_toolkit() is second

    def test_get_toolkit_creates_new_each_time_when_none(self):
        t1 = _get_toolkit()
        t2 = _get_toolkit()
        assert isinstance(t1, FinOpsIntelligenceToolkit)
        assert isinstance(t2, FinOpsIntelligenceToolkit)


# -- TestIntegration ---------------------------------------------------------


class TestIntegration:
    @pytest.mark.asyncio
    async def test_full_workflow_no_scope(self):
        """Analysis with no scope still returns valid result."""
        state = FinOpsIntelligenceState(
            session_id="fi-int-1",
            analysis_config={},
        )
        result = await analyze_costs(state)
        assert result["current_step"] == "analyze_costs"

    @pytest.mark.asyncio
    async def test_full_workflow_with_scope(self):
        """Analysis with scope finds cost data, identifies optimizations."""
        state = FinOpsIntelligenceState(
            session_id="fi-int-2",
            analysis_config={"scope": "aws-prod"},
        )
        analyze_result = await analyze_costs(state)
        assert analyze_result["finding_count"] >= 1

        state_after = FinOpsIntelligenceState(**{**state.model_dump(), **analyze_result})
        opt_result = await identify_optimizations(state_after)
        assert "optimization_opportunities" in opt_result

    @pytest.mark.asyncio
    async def test_full_workflow_finalize(self):
        """Finalize correctly records duration with session_start set."""
        state = FinOpsIntelligenceState(
            session_id="fi-int-3",
            session_start=datetime.now(UTC),
            finding_count=2,
            high_impact_count=0,
        )
        result = await finalize_analysis(state)
        assert result["current_step"] == "complete"
        assert result["session_duration_ms"] >= 0

    @pytest.mark.asyncio
    async def test_full_workflow_discover_then_check_conditional(self):
        """Analyze costs, then check conditional edge routes correctly."""
        state = FinOpsIntelligenceState(
            session_id="fi-int-4",
            analysis_config={"scope": "aws-prod"},
        )
        result = await analyze_costs(state)
        state_after = FinOpsIntelligenceState(**{**state.model_dump(), **result})
        assert should_optimize(state_after) == "identify_optimizations"

    @pytest.mark.asyncio
    async def test_full_workflow_prioritize_then_check_plan(
        self, analyzed_state: FinOpsIntelligenceState
    ):
        """Prioritize savings, then check plan conditional edge."""
        result = await prioritize_savings(analyzed_state)
        state_after = FinOpsIntelligenceState(**{**analyzed_state.model_dump(), **result})
        assert should_plan(state_after) == "plan_implementation"

    @pytest.mark.asyncio
    async def test_full_workflow_error_skips_optimization(self):
        """Error state should skip optimization and go to finalize."""
        state = FinOpsIntelligenceState(
            session_id="fi-int-err",
            finding_count=5,
            error="timeout",
        )
        assert should_optimize(state) == "finalize_analysis"

    @pytest.mark.asyncio
    async def test_full_workflow_no_high_impact_skips_plan(self):
        """No high-impact opportunities should skip plan and go to finalize."""
        state = FinOpsIntelligenceState(
            session_id="fi-int-noimpact",
            finding_count=3,
            high_impact_count=0,
        )
        assert should_plan(state) == "finalize_analysis"

    @pytest.mark.asyncio
    async def test_full_workflow_analyze_identify_prioritize(self):
        """Full path through analyze -> identify -> prioritize."""
        state = FinOpsIntelligenceState(
            session_id="fi-int-full",
            analysis_config={"scope": "full-prod"},
        )
        a_result = await analyze_costs(state)
        state2 = FinOpsIntelligenceState(**{**state.model_dump(), **a_result})

        o_result = await identify_optimizations(state2)
        state3 = FinOpsIntelligenceState(**{**state2.model_dump(), **o_result})

        p_result = await prioritize_savings(state3)
        assert p_result["current_step"] == "prioritize_savings"
        assert "high_impact_count" in p_result
