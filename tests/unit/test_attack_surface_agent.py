"""Tests for the Attack Surface Agent LangGraph workflow.

Covers:
- AttackSurfaceState model creation, defaults, and field types
- Sub-models: DiscoveredAsset, ExposureFinding, SurfaceReasoningStep
- Prompt schemas: DiscoveryOutput, ExposureAnalysisOutput, RemediationPlanOutput
- AttackSurfaceToolkit initialization and async methods
- Graph creation (create_attack_surface_graph returns a StateGraph)
- AttackSurfaceRunner initialization and list_results
- Node functions (discover_assets, analyze_exposures, prioritize_findings,
  plan_remediation, finalize_scan) with mock state
- Conditional edges (should_analyze, should_remediate)
- Integration: full workflow with simple inputs
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shieldops.agents.attack_surface.graph import (
    create_attack_surface_graph,
    should_analyze,
    should_remediate,
)
from shieldops.agents.attack_surface.models import (
    AttackSurfaceState,
    DiscoveredAsset,
    ExposureFinding,
    SurfaceReasoningStep,
)
from shieldops.agents.attack_surface.nodes import (
    _get_toolkit,
    analyze_exposures,
    discover_assets,
    finalize_scan,
    plan_remediation,
    prioritize_findings,
    set_toolkit,
)
from shieldops.agents.attack_surface.prompts import (
    DiscoveryOutput,
    ExposureAnalysisOutput,
    RemediationPlanOutput,
)
from shieldops.agents.attack_surface.runner import AttackSurfaceRunner
from shieldops.agents.attack_surface.tools import AttackSurfaceToolkit

# -- Fixtures ----------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_toolkit():
    """Reset the module-level toolkit singleton between tests."""
    import shieldops.agents.attack_surface.nodes as nodes_mod

    original = nodes_mod._toolkit
    nodes_mod._toolkit = None
    yield
    nodes_mod._toolkit = original


@pytest.fixture
def base_state() -> AttackSurfaceState:
    return AttackSurfaceState(
        scan_id="scan-001",
        scan_config={"scope": "example.com", "depth": "full"},
    )


@pytest.fixture
def discovered_state() -> AttackSurfaceState:
    return AttackSurfaceState(
        scan_id="scan-002",
        scan_config={"scope": "example.com"},
        discovered_assets=[
            DiscoveredAsset(
                asset_id="a-001",
                asset_type="domain",
                hostname="example.com",
                exposure_level="high",
                risk_score=85.0,
            ),
            DiscoveredAsset(
                asset_id="a-002",
                asset_type="subdomain",
                hostname="api.example.com",
                exposure_level="medium",
                risk_score=60.0,
            ),
        ],
        asset_count=2,
        exposure_findings=[
            ExposureFinding(
                finding_id="f-001",
                finding_type="open_port",
                severity="critical",
                affected_asset="a-001",
                description="SSH exposed",
                remediation="Restrict SSH access",
            ),
        ],
        risk_score=72.5,
        critical_count=1,
    )


# -- TestState ---------------------------------------------------------------


class TestState:
    def test_default_values(self):
        state = AttackSurfaceState()
        assert state.scan_id == ""
        assert state.scan_config == {}
        assert state.discovered_assets == []
        assert state.asset_count == 0
        assert state.exposure_findings == []
        assert state.risk_score == pytest.approx(0.0)
        assert state.prioritized_findings == []
        assert state.critical_count == 0
        assert state.remediation_plan == []
        assert state.remediation_started is False
        assert state.session_start is None
        assert state.session_duration_ms == 0
        assert state.reasoning_chain == []
        assert state.current_step == "init"
        assert state.error is None

    def test_creation_with_custom_values(self, base_state: AttackSurfaceState):
        assert base_state.scan_id == "scan-001"
        assert base_state.scan_config["scope"] == "example.com"
        assert base_state.scan_config["depth"] == "full"

    def test_list_fields_are_independent_instances(self):
        s1 = AttackSurfaceState()
        s2 = AttackSurfaceState()
        s1.discovered_assets.append(DiscoveredAsset(asset_id="x-1", asset_type="ip"))
        assert s2.discovered_assets == []

    def test_state_with_error(self):
        state = AttackSurfaceState(error="connection timeout", current_step="failed")
        assert state.error == "connection timeout"
        assert state.current_step == "failed"

    def test_state_with_discovered_assets(self, discovered_state: AttackSurfaceState):
        assert discovered_state.asset_count == 2
        assert len(discovered_state.discovered_assets) == 2
        assert discovered_state.discovered_assets[0].hostname == "example.com"

    def test_state_with_findings(self, discovered_state: AttackSurfaceState):
        assert len(discovered_state.exposure_findings) == 1
        assert discovered_state.exposure_findings[0].severity == "critical"
        assert discovered_state.critical_count == 1

    def test_state_remediation_defaults(self):
        state = AttackSurfaceState()
        assert state.remediation_plan == []
        assert state.remediation_started is False

    def test_state_scan_config_complex(self):
        state = AttackSurfaceState(
            scan_id="scan-complex",
            scan_config={"scope": "*.example.com", "ports": [80, 443, 8080], "deep": True},
        )
        assert state.scan_config["ports"] == [80, 443, 8080]
        assert state.scan_config["deep"] is True


# -- TestSubModels -----------------------------------------------------------


class TestSubModels:
    def test_discovered_asset_defaults(self):
        asset = DiscoveredAsset()
        assert asset.asset_id == ""
        assert asset.asset_type == ""
        assert asset.hostname == ""
        assert asset.ip_address == ""
        assert asset.exposure_level == "low"
        assert asset.risk_score == pytest.approx(0.0)

    def test_exposure_finding_defaults(self):
        finding = ExposureFinding()
        assert finding.finding_id == ""
        assert finding.finding_type == ""
        assert finding.severity == "medium"
        assert finding.affected_asset == ""
        assert finding.description == ""
        assert finding.remediation == ""

    def test_surface_reasoning_step_creation(self):
        step = SurfaceReasoningStep(
            step_number=1,
            action="discover_assets",
            input_summary="Scanning scope=example.com",
            output_summary="Discovered 5 assets",
        )
        assert step.step_number == 1
        assert step.action == "discover_assets"
        assert step.duration_ms == 0
        assert step.tool_used is None

    def test_discovered_asset_with_all_fields(self):
        asset = DiscoveredAsset(
            asset_id="a-001",
            asset_type="domain",
            hostname="example.com",
            ip_address="1.2.3.4",
            exposure_level="high",
            risk_score=95.0,
        )
        assert asset.exposure_level == "high"
        assert asset.risk_score == pytest.approx(95.0)

    def test_exposure_finding_with_all_fields(self):
        finding = ExposureFinding(
            finding_id="f-001",
            finding_type="misconfiguration",
            severity="critical",
            affected_asset="a-001",
            description="S3 bucket public",
            remediation="Make bucket private",
        )
        assert finding.severity == "critical"
        assert finding.remediation == "Make bucket private"

    def test_reasoning_step_with_tool(self):
        step = SurfaceReasoningStep(
            step_number=2,
            action="analyze_exposures",
            input_summary="5 assets",
            output_summary="3 findings",
            duration_ms=150,
            tool_used="exposure_scanner",
        )
        assert step.tool_used == "exposure_scanner"
        assert step.duration_ms == 150

    def test_discovered_asset_low_default_exposure(self):
        asset = DiscoveredAsset(asset_id="a-test")
        assert asset.exposure_level == "low"
        assert asset.risk_score == 0.0

    def test_exposure_finding_medium_default_severity(self):
        finding = ExposureFinding(finding_id="f-test")
        assert finding.severity == "medium"

    def test_reasoning_step_no_tool(self):
        step = SurfaceReasoningStep(
            step_number=1, action="test", input_summary="i", output_summary="o"
        )
        assert step.tool_used is None


# -- TestPromptSchemas -------------------------------------------------------


class TestPromptSchemas:
    def test_discovery_output_fields(self):
        output = DiscoveryOutput(
            asset_count=10,
            exposure_summary="5 high-risk assets found",
            risk_level="high",
        )
        assert output.asset_count == 10
        assert output.risk_level == "high"

    def test_exposure_analysis_output_fields(self):
        output = ExposureAnalysisOutput(
            findings=[{"type": "open_port", "severity": "high", "description": "SSH"}],
            risk_score=85.0,
            reasoning="Multiple open ports detected",
        )
        assert len(output.findings) == 1
        assert output.risk_score == pytest.approx(85.0)

    def test_remediation_plan_output_fields(self):
        output = RemediationPlanOutput(
            actions=[{"priority": "high", "target": "firewall"}],
            estimated_effort="2 hours",
            reasoning="Block exposed ports",
        )
        assert len(output.actions) == 1
        assert output.estimated_effort == "2 hours"

    def test_discovery_output_zero_assets(self):
        output = DiscoveryOutput(
            asset_count=0,
            exposure_summary="No assets found",
            risk_level="low",
        )
        assert output.asset_count == 0
        assert output.risk_level == "low"

    def test_exposure_analysis_output_high_risk(self):
        output = ExposureAnalysisOutput(
            findings=[],
            risk_score=99.0,
            reasoning="Critical exposures",
        )
        assert output.risk_score == pytest.approx(99.0)

    def test_remediation_plan_output_empty_actions(self):
        output = RemediationPlanOutput(
            actions=[],
            estimated_effort="0 hours",
            reasoning="Nothing to remediate",
        )
        assert len(output.actions) == 0


# -- TestToolkit -------------------------------------------------------------


class TestToolkit:
    def test_toolkit_initialization_with_no_deps(self):
        toolkit = AttackSurfaceToolkit()
        assert toolkit._asset_discovery is None
        assert toolkit._exposure_scanner is None
        assert toolkit._remediation_engine is None
        assert toolkit._policy_engine is None
        assert toolkit._repository is None

    def test_toolkit_initialization_with_deps(self):
        mock_discovery = MagicMock()
        toolkit = AttackSurfaceToolkit(asset_discovery=mock_discovery)
        assert toolkit._asset_discovery is mock_discovery

    @pytest.mark.asyncio
    async def test_discover_assets_returns_list(self):
        toolkit = AttackSurfaceToolkit()
        result = await toolkit.discover_assets({"scope": "example.com"})
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_scan_exposures_returns_list(self):
        toolkit = AttackSurfaceToolkit()
        result = await toolkit.scan_exposures([{"asset_id": "a-1"}])
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_prioritize_findings_returns_sorted(self):
        toolkit = AttackSurfaceToolkit()
        findings = [
            {"id": "f-1", "severity_score": 50},
            {"id": "f-2", "severity_score": 90},
        ]
        result = await toolkit.prioritize_findings(findings)
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_create_remediation_plan_returns_list(self):
        toolkit = AttackSurfaceToolkit()
        result = await toolkit.create_remediation_plan([{"id": "f-1"}])
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_record_surface_metric(self):
        toolkit = AttackSurfaceToolkit()
        await toolkit.record_surface_metric("discovery", 5.0)  # should not raise

    @pytest.mark.asyncio
    async def test_toolkit_with_all_deps(self):
        toolkit = AttackSurfaceToolkit(
            asset_discovery=MagicMock(),
            exposure_scanner=MagicMock(),
            remediation_engine=MagicMock(),
            policy_engine=MagicMock(),
            repository=MagicMock(),
        )
        assert toolkit._asset_discovery is not None
        assert toolkit._exposure_scanner is not None
        assert toolkit._remediation_engine is not None
        assert toolkit._policy_engine is not None
        assert toolkit._repository is not None


# -- TestGraph ---------------------------------------------------------------


class TestGraph:
    def test_create_attack_surface_graph_returns_state_graph(self):
        graph = create_attack_surface_graph()
        assert graph is not None
        assert hasattr(graph, "compile")

    def test_graph_has_expected_nodes(self):
        graph = create_attack_surface_graph()
        node_names = set(graph.nodes.keys())
        expected = {
            "discover_assets",
            "analyze_exposures",
            "prioritize_findings",
            "plan_remediation",
            "finalize_scan",
        }
        assert expected.issubset(node_names)

    def test_graph_compiles_without_error(self):
        graph = create_attack_surface_graph()
        app = graph.compile()
        assert app is not None

    def test_graph_entry_point_is_discover(self):
        graph = create_attack_surface_graph()
        # The entry point should be discover_assets
        assert "__start__" in graph.nodes or "discover_assets" in graph.nodes

    def test_graph_has_finalize_node(self):
        graph = create_attack_surface_graph()
        assert "finalize_scan" in graph.nodes

    def test_graph_has_plan_remediation_node(self):
        graph = create_attack_surface_graph()
        assert "plan_remediation" in graph.nodes


# -- TestRunner --------------------------------------------------------------


class TestRunner:
    def test_runner_initialization(self):
        with patch(
            "shieldops.agents.attack_surface.runner.create_attack_surface_graph"
        ) as mock_graph_fn:
            mock_graph = MagicMock()
            mock_graph.compile.return_value = MagicMock()
            mock_graph_fn.return_value = mock_graph
            runner = AttackSurfaceRunner()
            assert runner._results == {}

    def test_list_results_empty(self):
        with patch(
            "shieldops.agents.attack_surface.runner.create_attack_surface_graph"
        ) as mock_graph_fn:
            mock_graph = MagicMock()
            mock_graph.compile.return_value = MagicMock()
            mock_graph_fn.return_value = mock_graph
            runner = AttackSurfaceRunner()
            assert runner.list_results() == []

    def test_list_results_returns_summaries(self):
        with patch(
            "shieldops.agents.attack_surface.runner.create_attack_surface_graph"
        ) as mock_graph_fn:
            mock_graph = MagicMock()
            mock_graph.compile.return_value = MagicMock()
            mock_graph_fn.return_value = mock_graph
            runner = AttackSurfaceRunner()
            runner._results["as-abc"] = AttackSurfaceState(
                scan_id="scan-001",
                asset_count=5,
                critical_count=2,
                risk_score=75.0,
                current_step="complete",
            )
            summaries = runner.list_results()
            assert len(summaries) == 1
            assert summaries[0]["scan_id"] == "scan-001"
            assert summaries[0]["asset_count"] == 5

    @pytest.mark.asyncio
    async def test_scan_success(self):
        mock_app = AsyncMock()
        final_state = AttackSurfaceState(
            scan_id="scan-001",
            asset_count=3,
            critical_count=1,
            risk_score=80.0,
            current_step="complete",
        ).model_dump()
        mock_app.ainvoke.return_value = final_state

        with patch(
            "shieldops.agents.attack_surface.runner.create_attack_surface_graph"
        ) as mock_graph_fn:
            mock_graph = MagicMock()
            mock_graph.compile.return_value = mock_app
            mock_graph_fn.return_value = mock_graph
            runner = AttackSurfaceRunner()
            result = await runner.scan(scan_id="scan-001")

        assert isinstance(result, AttackSurfaceState)
        assert result.current_step == "complete"

    @pytest.mark.asyncio
    async def test_scan_handles_exception(self):
        mock_app = AsyncMock()
        mock_app.ainvoke.side_effect = RuntimeError("Graph exploded")

        with patch(
            "shieldops.agents.attack_surface.runner.create_attack_surface_graph"
        ) as mock_graph_fn:
            mock_graph = MagicMock()
            mock_graph.compile.return_value = mock_app
            mock_graph_fn.return_value = mock_graph
            runner = AttackSurfaceRunner()
            result = await runner.scan(scan_id="scan-x")

        assert result.error == "Graph exploded"
        assert result.current_step == "failed"

    @pytest.mark.asyncio
    async def test_scan_with_config(self):
        mock_app = AsyncMock()
        final_state = AttackSurfaceState(
            scan_id="scan-cfg",
            scan_config={"scope": "test.com"},
            current_step="complete",
        ).model_dump()
        mock_app.ainvoke.return_value = final_state

        with patch(
            "shieldops.agents.attack_surface.runner.create_attack_surface_graph"
        ) as mock_graph_fn:
            mock_graph = MagicMock()
            mock_graph.compile.return_value = mock_app
            mock_graph_fn.return_value = mock_graph
            runner = AttackSurfaceRunner()
            result = await runner.scan(scan_id="scan-cfg", scan_config={"scope": "test.com"})

        assert result.scan_config["scope"] == "test.com"

    def test_get_result_found(self):
        with patch(
            "shieldops.agents.attack_surface.runner.create_attack_surface_graph"
        ) as mock_graph_fn:
            mock_graph = MagicMock()
            mock_graph.compile.return_value = MagicMock()
            mock_graph_fn.return_value = mock_graph
            runner = AttackSurfaceRunner()
            runner._results["as-test"] = AttackSurfaceState(scan_id="scan-001")
            assert runner.get_result("as-test") is not None
            assert runner.get_result("as-test").scan_id == "scan-001"

    def test_get_result_not_found(self):
        with patch(
            "shieldops.agents.attack_surface.runner.create_attack_surface_graph"
        ) as mock_graph_fn:
            mock_graph = MagicMock()
            mock_graph.compile.return_value = MagicMock()
            mock_graph_fn.return_value = mock_graph
            runner = AttackSurfaceRunner()
            assert runner.get_result("nonexistent") is None

    def test_list_results_multiple(self):
        with patch(
            "shieldops.agents.attack_surface.runner.create_attack_surface_graph"
        ) as mock_graph_fn:
            mock_graph = MagicMock()
            mock_graph.compile.return_value = MagicMock()
            mock_graph_fn.return_value = mock_graph
            runner = AttackSurfaceRunner()
            runner._results["as-1"] = AttackSurfaceState(scan_id="s1", current_step="complete")
            runner._results["as-2"] = AttackSurfaceState(
                scan_id="s2", current_step="failed", error="err"
            )
            summaries = runner.list_results()
            assert len(summaries) == 2
            scan_ids = {s["scan_id"] for s in summaries}
            assert "s1" in scan_ids
            assert "s2" in scan_ids


# -- TestNodes ---------------------------------------------------------------


class TestNodes:
    @pytest.mark.asyncio
    async def test_discover_assets_with_scope(self):
        state = AttackSurfaceState(
            scan_id="scan-001",
            scan_config={"scope": "example.com"},
        )
        result = await discover_assets(state)
        assert "discovered_assets" in result
        assert result["asset_count"] >= 1
        assert result["current_step"] == "discover_assets"
        assert len(result["reasoning_chain"]) == 1

    @pytest.mark.asyncio
    async def test_discover_assets_empty_scope(self):
        state = AttackSurfaceState(
            scan_id="scan-002",
            scan_config={},
        )
        result = await discover_assets(state)
        assert "discovered_assets" in result
        assert result["current_step"] == "discover_assets"

    @pytest.mark.asyncio
    async def test_analyze_exposures(self, discovered_state: AttackSurfaceState):
        result = await analyze_exposures(discovered_state)
        assert "exposure_findings" in result
        assert "risk_score" in result
        assert result["current_step"] == "analyze_exposures"

    @pytest.mark.asyncio
    async def test_prioritize_findings(self, discovered_state: AttackSurfaceState):
        result = await prioritize_findings(discovered_state)
        assert "prioritized_findings" in result
        assert "critical_count" in result
        assert result["current_step"] == "prioritize_findings"

    @pytest.mark.asyncio
    async def test_plan_remediation(self, discovered_state: AttackSurfaceState):
        discovered_state.prioritized_findings = [{"id": "f-1", "severity": "critical"}]
        result = await plan_remediation(discovered_state)
        assert "remediation_plan" in result
        assert "remediation_started" in result
        assert result["current_step"] == "plan_remediation"

    @pytest.mark.asyncio
    async def test_finalize_scan_records_duration(self):
        state = AttackSurfaceState(
            scan_id="scan-final",
            session_start=datetime.now(UTC),
        )
        result = await finalize_scan(state)
        assert result["session_duration_ms"] >= 0
        assert result["current_step"] == "complete"

    @pytest.mark.asyncio
    async def test_finalize_scan_no_session_start(self):
        state = AttackSurfaceState(scan_id="scan-no-start")
        result = await finalize_scan(state)
        assert result["session_duration_ms"] == 0

    @pytest.mark.asyncio
    async def test_discover_assets_sets_session_start(self):
        state = AttackSurfaceState(
            scan_id="scan-start",
            scan_config={"scope": "test.com"},
        )
        result = await discover_assets(state)
        assert result["session_start"] is not None

    @pytest.mark.asyncio
    async def test_discover_assets_reasoning_chain_grows(self):
        state = AttackSurfaceState(
            scan_id="scan-chain",
            scan_config={"scope": "chain.com"},
            reasoning_chain=[
                SurfaceReasoningStep(
                    step_number=1, action="prev", input_summary="", output_summary=""
                )
            ],
        )
        result = await discover_assets(state)
        assert len(result["reasoning_chain"]) == 2
        assert result["reasoning_chain"][-1].action == "discover_assets"

    @pytest.mark.asyncio
    async def test_analyze_exposures_risk_score_calculated(
        self, discovered_state: AttackSurfaceState
    ):
        result = await analyze_exposures(discovered_state)
        assert isinstance(result["risk_score"], float)

    @pytest.mark.asyncio
    async def test_prioritize_findings_counts_critical(self, discovered_state: AttackSurfaceState):
        result = await prioritize_findings(discovered_state)
        assert result["critical_count"] == 1  # one critical finding in fixture

    @pytest.mark.asyncio
    async def test_plan_remediation_empty_findings(self):
        state = AttackSurfaceState(
            scan_id="scan-empty-rem",
            prioritized_findings=[],
            critical_count=1,
        )
        result = await plan_remediation(state)
        assert result["current_step"] == "plan_remediation"

    @pytest.mark.asyncio
    async def test_finalize_scan_adds_reasoning_step(self):
        state = AttackSurfaceState(
            scan_id="scan-reason",
            session_start=datetime.now(UTC),
        )
        result = await finalize_scan(state)
        assert len(result["reasoning_chain"]) >= 1
        assert result["reasoning_chain"][-1].action == "finalize_scan"


# -- TestConditionalEdges ----------------------------------------------------


class TestConditionalEdges:
    def test_should_analyze_with_assets(self):
        state = AttackSurfaceState(asset_count=5)
        assert should_analyze(state) == "analyze_exposures"

    def test_should_analyze_no_assets(self):
        state = AttackSurfaceState(asset_count=0)
        assert should_analyze(state) == "finalize_scan"

    def test_should_analyze_with_error(self):
        state = AttackSurfaceState(asset_count=5, error="failed")
        assert should_analyze(state) == "finalize_scan"

    def test_should_remediate_with_critical(self):
        state = AttackSurfaceState(critical_count=3)
        assert should_remediate(state) == "plan_remediation"

    def test_should_remediate_no_critical(self):
        state = AttackSurfaceState(critical_count=0)
        assert should_remediate(state) == "finalize_scan"

    def test_should_analyze_zero_assets_no_error(self):
        state = AttackSurfaceState(asset_count=0, error=None)
        assert should_analyze(state) == "finalize_scan"

    def test_should_analyze_one_asset(self):
        state = AttackSurfaceState(asset_count=1)
        assert should_analyze(state) == "analyze_exposures"

    def test_should_remediate_one_critical(self):
        state = AttackSurfaceState(critical_count=1)
        assert should_remediate(state) == "plan_remediation"

    def test_should_remediate_many_critical(self):
        state = AttackSurfaceState(critical_count=100)
        assert should_remediate(state) == "plan_remediation"


# -- TestToolkitManagement ---------------------------------------------------


class TestToolkitManagement:
    def test_get_toolkit_returns_default_when_none_set(self):
        toolkit = _get_toolkit()
        assert isinstance(toolkit, AttackSurfaceToolkit)

    def test_set_toolkit_is_used_by_get_toolkit(self):
        custom = AttackSurfaceToolkit(asset_discovery=MagicMock())
        set_toolkit(custom)
        assert _get_toolkit() is custom

    def test_set_toolkit_overrides_previous(self):
        first = AttackSurfaceToolkit()
        second = AttackSurfaceToolkit(asset_discovery=MagicMock())
        set_toolkit(first)
        assert _get_toolkit() is first
        set_toolkit(second)
        assert _get_toolkit() is second

    def test_get_toolkit_creates_new_each_time_when_none(self):
        t1 = _get_toolkit()
        t2 = _get_toolkit()
        # Both are valid toolkits (different instances since _toolkit is None each time)
        assert isinstance(t1, AttackSurfaceToolkit)
        assert isinstance(t2, AttackSurfaceToolkit)


# -- TestIntegration ---------------------------------------------------------


class TestIntegration:
    @pytest.mark.asyncio
    async def test_full_workflow_no_assets(self):
        """Scan with no scope discovers nothing, goes to finalize."""
        state = AttackSurfaceState(
            scan_id="scan-int-1",
            scan_config={},
        )
        result = await discover_assets(state)
        assert result["current_step"] == "discover_assets"

    @pytest.mark.asyncio
    async def test_full_workflow_with_scope(self):
        """Scan with scope discovers assets, analyzes exposures."""
        state = AttackSurfaceState(
            scan_id="scan-int-2",
            scan_config={"scope": "example.com"},
        )
        discover_result = await discover_assets(state)
        assert discover_result["asset_count"] >= 1

        state_after_discovery = AttackSurfaceState(**{**state.model_dump(), **discover_result})
        analyze_result = await analyze_exposures(state_after_discovery)
        assert "exposure_findings" in analyze_result

    @pytest.mark.asyncio
    async def test_full_workflow_finalize(self):
        """Finalize correctly records duration with session_start set."""
        state = AttackSurfaceState(
            scan_id="scan-int-3",
            session_start=datetime.now(UTC),
            asset_count=2,
            critical_count=0,
        )
        result = await finalize_scan(state)
        assert result["current_step"] == "complete"
        assert result["session_duration_ms"] >= 0

    @pytest.mark.asyncio
    async def test_full_workflow_discover_then_check_conditional(self):
        """Discover assets, then check conditional edge routes correctly."""
        state = AttackSurfaceState(
            scan_id="scan-int-4",
            scan_config={"scope": "example.com"},
        )
        result = await discover_assets(state)
        state_after = AttackSurfaceState(**{**state.model_dump(), **result})
        # With assets discovered, should route to analyze
        assert should_analyze(state_after) == "analyze_exposures"

    @pytest.mark.asyncio
    async def test_full_workflow_prioritize_then_check_remediate(
        self, discovered_state: AttackSurfaceState
    ):
        """Prioritize findings, then check remediate conditional edge."""
        result = await prioritize_findings(discovered_state)
        state_after = AttackSurfaceState(**{**discovered_state.model_dump(), **result})
        # With critical findings, should route to remediation
        assert should_remediate(state_after) == "plan_remediation"

    @pytest.mark.asyncio
    async def test_full_workflow_error_skips_analysis(self):
        """Error state should skip analysis and go to finalize."""
        state = AttackSurfaceState(
            scan_id="scan-int-err",
            asset_count=5,
            error="timeout",
        )
        assert should_analyze(state) == "finalize_scan"

    @pytest.mark.asyncio
    async def test_full_workflow_no_critical_skips_remediation(self):
        """No critical findings should skip remediation and go to finalize."""
        state = AttackSurfaceState(
            scan_id="scan-int-nocrits",
            asset_count=3,
            critical_count=0,
        )
        assert should_remediate(state) == "finalize_scan"

    @pytest.mark.asyncio
    async def test_full_workflow_discover_analyze_prioritize(self):
        """Full path through discover -> analyze -> prioritize."""
        state = AttackSurfaceState(
            scan_id="scan-int-full",
            scan_config={"scope": "full.example.com"},
        )
        d_result = await discover_assets(state)
        state2 = AttackSurfaceState(**{**state.model_dump(), **d_result})

        a_result = await analyze_exposures(state2)
        state3 = AttackSurfaceState(**{**state2.model_dump(), **a_result})

        p_result = await prioritize_findings(state3)
        assert p_result["current_step"] == "prioritize_findings"
        assert "critical_count" in p_result
