"""Tests for the Threat Hunter Agent LangGraph workflow.

Covers:
- ThreatHunterState model creation, defaults, and field types
- Sub-models: HuntFinding, ReasoningStep
- Prompt schemas: HypothesisOutput, ThreatAssessmentOutput
- ThreatHunterToolkit initialization and async methods
- Graph creation (create_threat_hunter_graph returns a StateGraph)
- ThreatHunterRunner initialization and list_results
- Node functions (generate_hypothesis, define_scope, collect_data, sweep_iocs,
  analyze_behavior, check_mitre, correlate_findings, assess_threat,
  recommend_response, track_effectiveness) with mock state
- Conditional edges (should_recommend_response)
- Integration: full workflow with simple inputs
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shieldops.agents.threat_hunter.graph import (
    create_threat_hunter_graph,
    should_recommend_response,
)
from shieldops.agents.threat_hunter.models import (
    HuntFinding,
    ReasoningStep,
    ThreatHunterState,
)
from shieldops.agents.threat_hunter.nodes import (
    _get_toolkit,
    analyze_behavior,
    assess_threat,
    check_mitre,
    collect_data,
    correlate_findings,
    define_scope,
    generate_hypothesis,
    recommend_response,
    set_toolkit,
    sweep_iocs,
    track_effectiveness,
)
from shieldops.agents.threat_hunter.prompts import (
    HypothesisOutput,
    ThreatAssessmentOutput,
)
from shieldops.agents.threat_hunter.runner import ThreatHunterRunner
from shieldops.agents.threat_hunter.tools import ThreatHunterToolkit

# -- Fixtures ----------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_toolkit():
    """Reset the module-level toolkit singleton between tests."""
    import shieldops.agents.threat_hunter.nodes as nodes_mod

    original = nodes_mod._toolkit
    nodes_mod._toolkit = None
    yield
    nodes_mod._toolkit = original


@pytest.fixture
def base_state() -> ThreatHunterState:
    return ThreatHunterState(
        hypothesis_id="hyp-001",
        hypothesis="Lateral movement via compromised service account",
        data_sources=["siem", "edr", "network_flow"],
    )


@pytest.fixture
def active_hunt_state() -> ThreatHunterState:
    return ThreatHunterState(
        hypothesis_id="hyp-002",
        hypothesis="APT using living-off-the-land binaries",
        data_sources=["siem", "edr"],
        hunt_scope={"time_range": "14d", "environments": ["production"]},
        ioc_sweep_results=[{"indicator": "evil.exe", "found": True}],
        behavioral_findings=[{"deviation": "unusual_process_tree"}],
        mitre_findings=[{"technique": "T1059", "coverage": "partial"}],
        correlated_findings=[{"group": "lateral_movement_cluster"}],
    )


# -- TestState ---------------------------------------------------------------


class TestState:
    def test_default_values(self):
        state = ThreatHunterState()
        assert state.hypothesis_id == ""
        assert state.hypothesis == ""
        assert state.hunt_scope == {}
        assert state.data_sources == []
        assert state.ioc_sweep_results == []
        assert state.behavioral_findings == []
        assert state.mitre_findings == []
        assert state.correlated_findings == []
        assert state.threat_assessment == {}
        assert state.response_recommendations == []
        assert state.threat_found is False
        assert state.effectiveness_score == pytest.approx(0.0)
        assert state.session_start is None
        assert state.session_duration_ms == 0
        assert state.reasoning_chain == []
        assert state.current_step == "init"
        assert state.error is None

    def test_creation_with_custom_values(self, base_state: ThreatHunterState):
        assert base_state.hypothesis_id == "hyp-001"
        assert "Lateral movement" in base_state.hypothesis
        assert len(base_state.data_sources) == 3

    def test_list_fields_are_independent(self):
        s1 = ThreatHunterState()
        s2 = ThreatHunterState()
        s1.data_sources.append("siem")
        assert s2.data_sources == []

    def test_state_with_error(self):
        state = ThreatHunterState(error="data source unavailable", current_step="failed")
        assert state.error == "data source unavailable"
        assert state.current_step == "failed"


# -- TestSubModels -----------------------------------------------------------


class TestSubModels:
    def test_hunt_finding_defaults(self):
        finding = HuntFinding()
        assert finding.source == ""
        assert finding.query == ""
        assert finding.summary == ""
        assert finding.severity == "low"
        assert finding.confidence == pytest.approx(0.0)

    def test_hunt_finding_with_values(self):
        finding = HuntFinding(
            source="edr",
            query="process_create where parent=cmd.exe",
            summary="Suspicious process chain",
            severity="high",
            confidence=0.85,
        )
        assert finding.source == "edr"
        assert finding.confidence == pytest.approx(0.85)

    def test_reasoning_step_creation(self):
        step = ReasoningStep(
            step_number=1,
            action="generate_hypothesis",
            input_summary="Initial hypothesis",
            output_summary="Refined hypothesis",
        )
        assert step.step_number == 1
        assert step.duration_ms == 0
        assert step.tool_used is None

    def test_reasoning_step_with_tool(self):
        step = ReasoningStep(
            step_number=2,
            action="sweep_iocs",
            input_summary="Sweep 5 indicators",
            output_summary="Found 2 matches",
            duration_ms=150,
            tool_used="ioc_scanner",
        )
        assert step.tool_used == "ioc_scanner"
        assert step.duration_ms == 150


# -- TestPromptSchemas -------------------------------------------------------


class TestPromptSchemas:
    def test_hypothesis_output_fields(self):
        output = HypothesisOutput(
            hypothesis="Adversary using PowerShell for C2",
            data_sources=["edr", "siem"],
            mitre_techniques=["T1059.001"],
            confidence=0.7,
        )
        assert output.confidence == pytest.approx(0.7)
        assert len(output.data_sources) == 2
        assert len(output.mitre_techniques) == 1

    def test_threat_assessment_output_fields(self):
        output = ThreatAssessmentOutput(
            threat_found=True,
            severity="critical",
            confidence=0.9,
            summary="Confirmed APT activity detected",
            affected_assets=["srv-web-01", "srv-db-01"],
        )
        assert output.threat_found is True
        assert output.severity == "critical"
        assert len(output.affected_assets) == 2


# -- TestToolkit -------------------------------------------------------------


class TestToolkit:
    def test_toolkit_initialization_with_no_deps(self):
        toolkit = ThreatHunterToolkit()
        assert toolkit._mitre_mapper is None
        assert toolkit._threat_intel is None
        assert toolkit._ioc_scanner is None

    def test_toolkit_initialization_with_deps(self):
        mock_scanner = MagicMock()
        toolkit = ThreatHunterToolkit(ioc_scanner=mock_scanner)
        assert toolkit._ioc_scanner is mock_scanner

    @pytest.mark.asyncio
    async def test_generate_hypothesis_returns_expected_keys(self):
        toolkit = ThreatHunterToolkit()
        result = await toolkit.generate_hypothesis({"hypothesis": "test"})
        assert "hypothesis" in result
        assert "data_sources" in result
        assert "confidence" in result

    @pytest.mark.asyncio
    async def test_sweep_iocs_returns_list(self):
        toolkit = ThreatHunterToolkit()
        result = await toolkit.sweep_iocs({}, ["indicator1"])
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_analyze_behavior_returns_list(self):
        toolkit = ThreatHunterToolkit()
        result = await toolkit.analyze_behavior({}, "default")
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_check_mitre_coverage_returns_list(self):
        toolkit = ThreatHunterToolkit()
        result = await toolkit.check_mitre_coverage(["T1059"])
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_correlate_findings_returns_list(self):
        toolkit = ThreatHunterToolkit()
        result = await toolkit.correlate_findings([{"type": "ioc"}])
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_track_effectiveness_returns_tracked(self):
        toolkit = ThreatHunterToolkit()
        result = await toolkit.track_effectiveness("hyp-001", {"score": 0.5})
        assert result["tracked"] is True


# -- TestGraph ---------------------------------------------------------------


class TestGraph:
    def test_create_threat_hunter_graph_returns_state_graph(self):
        graph = create_threat_hunter_graph()
        assert graph is not None
        assert hasattr(graph, "compile")

    def test_graph_has_expected_nodes(self):
        graph = create_threat_hunter_graph()
        node_names = set(graph.nodes.keys())
        expected = {
            "generate_hypothesis",
            "define_scope",
            "collect_data",
            "sweep_iocs",
            "analyze_behavior",
            "check_mitre",
            "correlate_findings",
            "assess_threat",
            "recommend_response",
            "track_effectiveness",
        }
        assert expected.issubset(node_names)

    def test_graph_compiles_without_error(self):
        graph = create_threat_hunter_graph()
        app = graph.compile()
        assert app is not None


# -- TestRunner --------------------------------------------------------------


class TestRunner:
    def test_runner_initialization(self):
        with patch(
            "shieldops.agents.threat_hunter.runner.create_threat_hunter_graph"
        ) as mock_graph_fn:
            mock_graph = MagicMock()
            mock_graph.compile.return_value = MagicMock()
            mock_graph_fn.return_value = mock_graph
            runner = ThreatHunterRunner()
            assert runner._results == {}

    def test_list_results_empty(self):
        with patch(
            "shieldops.agents.threat_hunter.runner.create_threat_hunter_graph"
        ) as mock_graph_fn:
            mock_graph = MagicMock()
            mock_graph.compile.return_value = MagicMock()
            mock_graph_fn.return_value = mock_graph
            runner = ThreatHunterRunner()
            assert runner.list_results() == []

    def test_list_results_returns_summaries(self):
        with patch(
            "shieldops.agents.threat_hunter.runner.create_threat_hunter_graph"
        ) as mock_graph_fn:
            mock_graph = MagicMock()
            mock_graph.compile.return_value = MagicMock()
            mock_graph_fn.return_value = mock_graph
            runner = ThreatHunterRunner()
            runner._results["hunt-abc"] = ThreatHunterState(
                hypothesis_id="hyp-001",
                hypothesis="Test hypothesis for lateral movement",
                threat_found=True,
                effectiveness_score=0.8,
                current_step="complete",
            )
            summaries = runner.list_results()
            assert len(summaries) == 1
            assert summaries[0]["hypothesis_id"] == "hyp-001"
            assert summaries[0]["threat_found"] is True

    @pytest.mark.asyncio
    async def test_hunt_success(self):
        mock_app = AsyncMock()
        final_state = ThreatHunterState(
            hypothesis_id="hyp-abc",
            hypothesis="Lateral movement via RDP",
            threat_found=True,
            effectiveness_score=0.7,
            current_step="complete",
        ).model_dump()
        mock_app.ainvoke.return_value = final_state

        with patch(
            "shieldops.agents.threat_hunter.runner.create_threat_hunter_graph"
        ) as mock_graph_fn:
            mock_graph = MagicMock()
            mock_graph.compile.return_value = mock_app
            mock_graph_fn.return_value = mock_graph
            runner = ThreatHunterRunner()
            result = await runner.hunt(hypothesis="Lateral movement via RDP")

        assert isinstance(result, ThreatHunterState)
        assert result.current_step == "complete"
        assert result.threat_found is True

    @pytest.mark.asyncio
    async def test_hunt_handles_exception(self):
        mock_app = AsyncMock()
        mock_app.ainvoke.side_effect = RuntimeError("Graph failed")

        with patch(
            "shieldops.agents.threat_hunter.runner.create_threat_hunter_graph"
        ) as mock_graph_fn:
            mock_graph = MagicMock()
            mock_graph.compile.return_value = mock_app
            mock_graph_fn.return_value = mock_graph
            runner = ThreatHunterRunner()
            result = await runner.hunt(hypothesis="Test hypothesis")

        assert result.error == "Graph failed"
        assert result.current_step == "failed"


# -- TestNodes ---------------------------------------------------------------


class TestNodes:
    @pytest.mark.asyncio
    async def test_generate_hypothesis(self, base_state: ThreatHunterState):
        result = await generate_hypothesis(base_state)
        assert "hypothesis" in result
        assert "data_sources" in result
        assert result["current_step"] == "generate_hypothesis"
        assert "session_start" in result
        assert len(result["reasoning_chain"]) == 1

    @pytest.mark.asyncio
    async def test_define_scope_sets_defaults(self, base_state: ThreatHunterState):
        result = await define_scope(base_state)
        scope = result["hunt_scope"]
        assert scope["time_range"] == "7d"
        assert scope["environments"] == ["production"]
        assert scope["data_sources"] == base_state.data_sources
        assert result["current_step"] == "define_scope"

    @pytest.mark.asyncio
    async def test_define_scope_preserves_existing(self):
        state = ThreatHunterState(
            hunt_scope={"time_range": "30d", "environments": ["staging"]},
            data_sources=["edr"],
        )
        result = await define_scope(state)
        scope = result["hunt_scope"]
        assert scope["time_range"] == "30d"
        assert scope["environments"] == ["staging"]

    @pytest.mark.asyncio
    async def test_collect_data_validates_sources(self, base_state: ThreatHunterState):
        result = await collect_data(base_state)
        assert result["data_sources"] == base_state.data_sources
        assert result["current_step"] == "collect_data"

    @pytest.mark.asyncio
    async def test_sweep_iocs_returns_results(self, base_state: ThreatHunterState):
        result = await sweep_iocs(base_state)
        assert isinstance(result["ioc_sweep_results"], list)
        assert result["current_step"] == "sweep_iocs"

    @pytest.mark.asyncio
    async def test_analyze_behavior_returns_findings(self, base_state: ThreatHunterState):
        result = await analyze_behavior(base_state)
        assert isinstance(result["behavioral_findings"], list)
        assert result["current_step"] == "analyze_behavior"

    @pytest.mark.asyncio
    async def test_check_mitre_returns_coverage(self, base_state: ThreatHunterState):
        result = await check_mitre(base_state)
        assert isinstance(result["mitre_findings"], list)
        assert result["current_step"] == "check_mitre"

    @pytest.mark.asyncio
    async def test_correlate_findings_returns_correlated(self, base_state: ThreatHunterState):
        result = await correlate_findings(base_state)
        assert isinstance(result["correlated_findings"], list)
        assert result["current_step"] == "correlate_findings"

    @pytest.mark.asyncio
    async def test_assess_threat_no_findings(self):
        state = ThreatHunterState()
        result = await assess_threat(state)
        assert result["threat_found"] is False
        assert result["threat_assessment"]["severity"] == "low"
        assert result["current_step"] == "assess_threat"

    @pytest.mark.asyncio
    async def test_assess_threat_many_findings(self, active_hunt_state: ThreatHunterState):
        result = await assess_threat(active_hunt_state)
        assert result["threat_found"] is True
        assert result["threat_assessment"]["severity"] in ("critical", "high")

    @pytest.mark.asyncio
    async def test_assess_threat_correlated_critical(self):
        state = ThreatHunterState(
            correlated_findings=[{"g1": True}, {"g2": True}, {"g3": True}],
            ioc_sweep_results=[{"i1": True}],
        )
        result = await assess_threat(state)
        assert result["threat_assessment"]["severity"] == "critical"
        assert result["threat_assessment"]["confidence"] == pytest.approx(0.9)

    @pytest.mark.asyncio
    async def test_recommend_response_critical(self):
        state = ThreatHunterState(
            threat_found=True,
            threat_assessment={"severity": "critical"},
            ioc_sweep_results=[{"indicator": "evil"}],
            behavioral_findings=[{"deviation": "anomaly"}],
        )
        result = await recommend_response(state)
        recs = result["response_recommendations"]
        actions = [r["action"] for r in recs]
        assert "escalate_to_ir" in actions
        assert "activate_war_room" in actions
        assert "block_iocs" in actions
        assert "enhance_monitoring" in actions

    @pytest.mark.asyncio
    async def test_recommend_response_high(self):
        state = ThreatHunterState(
            threat_found=True,
            threat_assessment={"severity": "high"},
        )
        result = await recommend_response(state)
        recs = result["response_recommendations"]
        actions = [r["action"] for r in recs]
        assert "escalate_to_ir" in actions
        assert "activate_war_room" not in actions

    @pytest.mark.asyncio
    async def test_track_effectiveness_threat_found(self):
        state = ThreatHunterState(
            hypothesis_id="hyp-eff",
            threat_found=True,
            correlated_findings=[{"g": True}],
            session_start=datetime.now(UTC),
        )
        result = await track_effectiveness(state)
        assert result["effectiveness_score"] >= 0.5
        assert result["session_duration_ms"] >= 0
        assert result["current_step"] == "complete"

    @pytest.mark.asyncio
    async def test_track_effectiveness_no_threat(self):
        state = ThreatHunterState(
            hypothesis_id="hyp-noeff",
            threat_found=False,
            session_start=datetime.now(UTC),
        )
        result = await track_effectiveness(state)
        assert result["effectiveness_score"] == pytest.approx(0.1)

    @pytest.mark.asyncio
    async def test_track_effectiveness_with_findings_no_threat(self):
        state = ThreatHunterState(
            hypothesis_id="hyp-partial",
            threat_found=False,
            ioc_sweep_results=[{"x": 1}],
            behavioral_findings=[{"y": 2}],
            session_start=datetime.now(UTC),
        )
        result = await track_effectiveness(state)
        assert 0.0 < result["effectiveness_score"] < 0.5


# -- TestConditionalEdges ----------------------------------------------------


class TestConditionalEdges:
    def test_should_recommend_response_threat_found(self):
        state = ThreatHunterState(threat_found=True)
        assert should_recommend_response(state) == "recommend_response"

    def test_should_recommend_response_no_threat(self):
        state = ThreatHunterState(threat_found=False)
        assert should_recommend_response(state) == "track_effectiveness"

    def test_should_recommend_response_with_error(self):
        state = ThreatHunterState(error="something broke", threat_found=True)
        assert should_recommend_response(state) == "track_effectiveness"


# -- TestToolkitManagement ---------------------------------------------------


class TestToolkitManagement:
    def test_get_toolkit_returns_default_when_none_set(self):
        toolkit = _get_toolkit()
        assert isinstance(toolkit, ThreatHunterToolkit)

    def test_set_toolkit_is_used_by_get_toolkit(self):
        custom = ThreatHunterToolkit(ioc_scanner=MagicMock())
        set_toolkit(custom)
        assert _get_toolkit() is custom


# -- TestIntegration ---------------------------------------------------------


class TestIntegration:
    @pytest.mark.asyncio
    async def test_full_workflow_no_threats(self):
        """A clean hunt: hypothesis -> scope -> collect -> sweep -> analyze ->
        check_mitre -> correlate -> assess -> track."""
        state = ThreatHunterState(
            hypothesis_id="hyp-clean",
            hypothesis="Check for unauthorized SSH tunnels",
            data_sources=["network_flow", "siem"],
        )

        r1 = await generate_hypothesis(state)
        state = ThreatHunterState(**{**state.model_dump(), **r1})

        r2 = await define_scope(state)
        state = ThreatHunterState(**{**state.model_dump(), **r2})
        assert state.hunt_scope["time_range"] == "7d"

        r3 = await collect_data(state)
        state = ThreatHunterState(**{**state.model_dump(), **r3})

        r4 = await sweep_iocs(state)
        state = ThreatHunterState(**{**state.model_dump(), **r4})

        r5 = await analyze_behavior(state)
        state = ThreatHunterState(**{**state.model_dump(), **r5})

        r6 = await check_mitre(state)
        state = ThreatHunterState(**{**state.model_dump(), **r6})

        r7 = await correlate_findings(state)
        state = ThreatHunterState(**{**state.model_dump(), **r7})

        r8 = await assess_threat(state)
        state = ThreatHunterState(**{**state.model_dump(), **r8})
        assert state.threat_found is False

        # Should skip recommend_response and go to track_effectiveness
        assert should_recommend_response(state) == "track_effectiveness"

        r9 = await track_effectiveness(state)
        assert r9["current_step"] == "complete"
        assert r9["effectiveness_score"] == pytest.approx(0.1)

    @pytest.mark.asyncio
    async def test_full_workflow_threat_detected(self, active_hunt_state: ThreatHunterState):
        """When findings exist, assess_threat should find a threat."""
        result = await assess_threat(active_hunt_state)
        assert result["threat_found"] is True
        assert (
            should_recommend_response(
                ThreatHunterState(**{**active_hunt_state.model_dump(), **result})
            )
            == "recommend_response"
        )
