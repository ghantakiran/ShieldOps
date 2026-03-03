"""Tests for the Threat Automation Agent LangGraph workflow.

Covers:
- ThreatAutomationState model creation, defaults, and field types
- Sub-models: DetectedThreat, BehaviorAnalysis, IntelCorrelation, ThreatReasoningStep
- Prompt schemas: ThreatDetectionOutput, BehaviorAnalysisOutput, ResponseAutomationOutput
- ThreatAutomationToolkit initialization and async methods
- Graph creation (create_threat_automation_graph returns a StateGraph)
- ThreatAutomationRunner initialization and list_results
- Node functions (detect_threats, analyze_behavior, correlate_intelligence,
  automate_response, finalize_hunt) with mock state
- Conditional edges (should_analyze, should_respond)
- Integration: full workflow with simple inputs
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shieldops.agents.threat_automation.graph import (
    create_threat_automation_graph,
    should_analyze,
    should_respond,
)
from shieldops.agents.threat_automation.models import (
    BehaviorAnalysis,
    DetectedThreat,
    IntelCorrelation,
    ThreatAutomationState,
    ThreatReasoningStep,
)
from shieldops.agents.threat_automation.nodes import (
    _get_toolkit,
    analyze_behavior,
    automate_response,
    correlate_intelligence,
    detect_threats,
    finalize_hunt,
    set_toolkit,
)
from shieldops.agents.threat_automation.prompts import (
    BehaviorAnalysisOutput,
    ResponseAutomationOutput,
    ThreatDetectionOutput,
)
from shieldops.agents.threat_automation.runner import ThreatAutomationRunner
from shieldops.agents.threat_automation.tools import ThreatAutomationToolkit

# -- Fixtures ----------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_toolkit():
    """Reset the module-level toolkit singleton between tests."""
    import shieldops.agents.threat_automation.nodes as nodes_mod

    original = nodes_mod._toolkit
    nodes_mod._toolkit = None
    yield
    nodes_mod._toolkit = original


@pytest.fixture
def base_state() -> ThreatAutomationState:
    return ThreatAutomationState(
        hunt_id="hunt-001",
        hunt_config={"scope": "network", "depth": "deep"},
    )


@pytest.fixture
def threat_state() -> ThreatAutomationState:
    return ThreatAutomationState(
        hunt_id="hunt-002",
        hunt_config={"scope": "network"},
        detected_threats=[
            DetectedThreat(
                threat_id="t-001",
                threat_type="malware",
                severity="critical",
                source="endpoint",
                confidence=92.0,
                indicators=["suspicious_binary", "c2_beacon"],
            ),
            DetectedThreat(
                threat_id="t-002",
                threat_type="reconnaissance",
                severity="medium",
                source="network",
                confidence=65.0,
                indicators=["port_scan"],
            ),
        ],
        threat_count=2,
        behavior_analyses=[
            BehaviorAnalysis(
                analysis_id="ba-001",
                behavior_type="lateral_movement",
                risk_score=88.0,
                anomalies=["unusual_smb_traffic"],
                verdict="malicious",
            ),
        ],
        critical_count=1,
    )


# -- TestState ---------------------------------------------------------------


class TestState:
    def test_default_values(self):
        state = ThreatAutomationState()
        assert state.hunt_id == ""
        assert state.hunt_config == {}
        assert state.detected_threats == []
        assert state.behavior_analyses == []
        assert state.intel_correlations == []
        assert state.threat_count == 0
        assert state.critical_count == 0
        assert state.response_actions == []
        assert state.automated_responses == 0
        assert state.session_start is None
        assert state.session_duration_ms == 0
        assert state.reasoning_chain == []
        assert state.current_step == "init"
        assert state.error is None

    def test_creation_with_custom_values(self, base_state: ThreatAutomationState):
        assert base_state.hunt_id == "hunt-001"
        assert base_state.hunt_config["scope"] == "network"
        assert base_state.hunt_config["depth"] == "deep"

    def test_list_fields_are_independent_instances(self):
        s1 = ThreatAutomationState()
        s2 = ThreatAutomationState()
        s1.detected_threats.append(DetectedThreat(threat_id="x-1", threat_type="test"))
        assert s2.detected_threats == []

    def test_state_with_error(self):
        state = ThreatAutomationState(error="connection timeout", current_step="failed")
        assert state.error == "connection timeout"
        assert state.current_step == "failed"

    def test_state_with_threats(self, threat_state: ThreatAutomationState):
        assert threat_state.threat_count == 2
        assert len(threat_state.detected_threats) == 2
        assert threat_state.detected_threats[0].threat_type == "malware"

    def test_state_with_critical_threats(self):
        state = ThreatAutomationState(
            detected_threats=[
                DetectedThreat(threat_id="t-c1", severity="critical"),
                DetectedThreat(threat_id="t-c2", severity="high"),
            ],
            threat_count=2,
            critical_count=2,
        )
        assert state.critical_count == 2
        assert len(state.detected_threats) == 2

    def test_state_response_defaults(self):
        state = ThreatAutomationState()
        assert state.response_actions == []
        assert state.automated_responses == 0

    def test_state_hunt_config_complex(self):
        state = ThreatAutomationState(
            hunt_id="hunt-complex",
            hunt_config={"scope": "*.internal.net", "ports": [22, 443, 8080], "aggressive": True},
        )
        assert state.hunt_config["ports"] == [22, 443, 8080]
        assert state.hunt_config["aggressive"] is True


# -- TestSubModels -----------------------------------------------------------


class TestSubModels:
    def test_detected_threat_defaults(self):
        threat = DetectedThreat()
        assert threat.threat_id == ""
        assert threat.threat_type == ""
        assert threat.severity == "medium"
        assert threat.source == ""
        assert threat.confidence == pytest.approx(0.0)
        assert threat.indicators == []

    def test_behavior_analysis_defaults(self):
        analysis = BehaviorAnalysis()
        assert analysis.analysis_id == ""
        assert analysis.behavior_type == ""
        assert analysis.risk_score == pytest.approx(0.0)
        assert analysis.anomalies == []
        assert analysis.verdict == "benign"

    def test_intel_correlation_defaults(self):
        correlation = IntelCorrelation()
        assert correlation.correlation_id == ""
        assert correlation.intel_source == ""
        assert correlation.matched_indicators == 0
        assert correlation.campaign == ""
        assert correlation.confidence == pytest.approx(0.0)

    def test_reasoning_step_creation(self):
        step = ThreatReasoningStep(
            step_number=1,
            action="detect_threats",
            input_summary="Hunting scope=network",
            output_summary="Detected 3 threats",
        )
        assert step.step_number == 1
        assert step.action == "detect_threats"
        assert step.duration_ms == 0
        assert step.tool_used is None

    def test_detected_threat_with_all_fields(self):
        threat = DetectedThreat(
            threat_id="t-001",
            threat_type="malware",
            severity="critical",
            source="endpoint",
            confidence=95.0,
            indicators=["c2_beacon", "suspicious_binary"],
        )
        assert threat.severity == "critical"
        assert threat.confidence == pytest.approx(95.0)
        assert len(threat.indicators) == 2

    def test_behavior_analysis_with_all_fields(self):
        analysis = BehaviorAnalysis(
            analysis_id="ba-001",
            behavior_type="lateral_movement",
            risk_score=92.0,
            anomalies=["unusual_smb_traffic", "credential_dumping"],
            verdict="malicious",
        )
        assert analysis.verdict == "malicious"
        assert analysis.risk_score == pytest.approx(92.0)
        assert len(analysis.anomalies) == 2

    def test_intel_correlation_with_all_fields(self):
        correlation = IntelCorrelation(
            correlation_id="ic-001",
            intel_source="threat_feed_alpha",
            matched_indicators=5,
            campaign="APT29_Campaign",
            confidence=88.0,
        )
        assert correlation.campaign == "APT29_Campaign"
        assert correlation.matched_indicators == 5
        assert correlation.confidence == pytest.approx(88.0)

    def test_reasoning_step_with_tool(self):
        step = ThreatReasoningStep(
            step_number=2,
            action="analyze_behavior",
            input_summary="3 threats",
            output_summary="2 analyses",
            duration_ms=150,
            tool_used="behavior_analyzer",
        )
        assert step.tool_used == "behavior_analyzer"
        assert step.duration_ms == 150

    def test_reasoning_step_no_tool(self):
        step = ThreatReasoningStep(
            step_number=1, action="test", input_summary="i", output_summary="o"
        )
        assert step.tool_used is None


# -- TestPromptSchemas -------------------------------------------------------


class TestPromptSchemas:
    def test_threat_detection_output_fields(self):
        output = ThreatDetectionOutput(
            threat_count=10,
            severity_summary="5 critical, 3 high, 2 medium",
            risk_level="critical",
        )
        assert output.threat_count == 10
        assert output.risk_level == "critical"

    def test_behavior_analysis_output_fields(self):
        output = BehaviorAnalysisOutput(
            analyses=[{"type": "lateral_movement", "risk_score": "90", "verdict": "malicious"}],
            risk_score=90.0,
            reasoning="Active lateral movement detected",
        )
        assert len(output.analyses) == 1
        assert output.risk_score == pytest.approx(90.0)

    def test_response_automation_output_fields(self):
        output = ResponseAutomationOutput(
            actions=[{"type": "isolate", "target": "host-001", "status": "executed"}],
            automated_count=1,
            reasoning="Isolated compromised host",
        )
        assert len(output.actions) == 1
        assert output.automated_count == 1

    def test_detection_output_zero_threats(self):
        output = ThreatDetectionOutput(
            threat_count=0,
            severity_summary="No threats found",
            risk_level="low",
        )
        assert output.threat_count == 0
        assert output.risk_level == "low"

    def test_behavior_analysis_output_high_risk(self):
        output = BehaviorAnalysisOutput(
            analyses=[],
            risk_score=99.0,
            reasoning="Critical behavioral anomalies",
        )
        assert output.risk_score == pytest.approx(99.0)

    def test_response_automation_output_empty_actions(self):
        output = ResponseAutomationOutput(
            actions=[],
            automated_count=0,
            reasoning="No actions required",
        )
        assert len(output.actions) == 0


# -- TestToolkit -------------------------------------------------------------


class TestToolkit:
    def test_toolkit_initialization_with_no_deps(self):
        toolkit = ThreatAutomationToolkit()
        assert toolkit._threat_detector is None
        assert toolkit._behavior_analyzer is None
        assert toolkit._intel_provider is None
        assert toolkit._response_engine is None
        assert toolkit._repository is None

    def test_toolkit_initialization_with_deps(self):
        mock_detector = MagicMock()
        toolkit = ThreatAutomationToolkit(threat_detector=mock_detector)
        assert toolkit._threat_detector is mock_detector

    @pytest.mark.asyncio
    async def test_detect_threats_returns_list(self):
        toolkit = ThreatAutomationToolkit()
        result = await toolkit.detect_threats({"scope": "network"})
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_analyze_behaviors_returns_list(self):
        toolkit = ThreatAutomationToolkit()
        result = await toolkit.analyze_behaviors([{"threat_id": "t-1"}])
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_correlate_intel_returns_list(self):
        toolkit = ThreatAutomationToolkit()
        result = await toolkit.correlate_intel([{"threat_id": "t-1"}])
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_execute_responses_returns_list(self):
        toolkit = ThreatAutomationToolkit()
        result = await toolkit.execute_responses([{"threat_id": "t-1"}])
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_record_hunt_metric(self):
        toolkit = ThreatAutomationToolkit()
        await toolkit.record_hunt_metric("detection", 5.0)  # should not raise

    def test_toolkit_with_all_deps(self):
        toolkit = ThreatAutomationToolkit(
            threat_detector=MagicMock(),
            behavior_analyzer=MagicMock(),
            intel_provider=MagicMock(),
            response_engine=MagicMock(),
            repository=MagicMock(),
        )
        assert toolkit._threat_detector is not None
        assert toolkit._behavior_analyzer is not None
        assert toolkit._intel_provider is not None
        assert toolkit._response_engine is not None
        assert toolkit._repository is not None


# -- TestGraph ---------------------------------------------------------------


class TestGraph:
    def test_create_graph_returns_state_graph(self):
        graph = create_threat_automation_graph()
        assert graph is not None
        assert hasattr(graph, "compile")

    def test_graph_has_expected_nodes(self):
        graph = create_threat_automation_graph()
        node_names = set(graph.nodes.keys())
        expected = {
            "detect_threats",
            "analyze_behavior",
            "correlate_intelligence",
            "automate_response",
            "finalize_hunt",
        }
        assert expected.issubset(node_names)

    def test_graph_compiles_without_error(self):
        graph = create_threat_automation_graph()
        app = graph.compile()
        assert app is not None

    def test_graph_entry_point_is_detect(self):
        graph = create_threat_automation_graph()
        # The entry point should be detect_threats
        assert "__start__" in graph.nodes or "detect_threats" in graph.nodes

    def test_graph_has_finalize_node(self):
        graph = create_threat_automation_graph()
        assert "finalize_hunt" in graph.nodes

    def test_graph_has_automate_node(self):
        graph = create_threat_automation_graph()
        assert "automate_response" in graph.nodes


# -- TestRunner --------------------------------------------------------------


class TestRunner:
    def test_runner_initialization(self):
        with patch(
            "shieldops.agents.threat_automation.runner.create_threat_automation_graph"
        ) as mock_graph_fn:
            mock_graph = MagicMock()
            mock_graph.compile.return_value = MagicMock()
            mock_graph_fn.return_value = mock_graph
            runner = ThreatAutomationRunner()
            assert runner._results == {}

    def test_list_results_empty(self):
        with patch(
            "shieldops.agents.threat_automation.runner.create_threat_automation_graph"
        ) as mock_graph_fn:
            mock_graph = MagicMock()
            mock_graph.compile.return_value = MagicMock()
            mock_graph_fn.return_value = mock_graph
            runner = ThreatAutomationRunner()
            assert runner.list_results() == []

    def test_list_results_returns_summaries(self):
        with patch(
            "shieldops.agents.threat_automation.runner.create_threat_automation_graph"
        ) as mock_graph_fn:
            mock_graph = MagicMock()
            mock_graph.compile.return_value = MagicMock()
            mock_graph_fn.return_value = mock_graph
            runner = ThreatAutomationRunner()
            runner._results["ta-abc"] = ThreatAutomationState(
                hunt_id="hunt-001",
                threat_count=5,
                critical_count=2,
                automated_responses=1,
                current_step="complete",
            )
            summaries = runner.list_results()
            assert len(summaries) == 1
            assert summaries[0]["hunt_id"] == "hunt-001"
            assert summaries[0]["threat_count"] == 5

    @pytest.mark.asyncio
    async def test_hunt_success(self):
        mock_app = AsyncMock()
        final_state = ThreatAutomationState(
            hunt_id="hunt-001",
            threat_count=3,
            critical_count=1,
            automated_responses=1,
            current_step="complete",
        ).model_dump()
        mock_app.ainvoke.return_value = final_state

        with patch(
            "shieldops.agents.threat_automation.runner.create_threat_automation_graph"
        ) as mock_graph_fn:
            mock_graph = MagicMock()
            mock_graph.compile.return_value = mock_app
            mock_graph_fn.return_value = mock_graph
            runner = ThreatAutomationRunner()
            result = await runner.hunt(hunt_id="hunt-001")

        assert isinstance(result, ThreatAutomationState)
        assert result.current_step == "complete"

    @pytest.mark.asyncio
    async def test_hunt_handles_exception(self):
        mock_app = AsyncMock()
        mock_app.ainvoke.side_effect = RuntimeError("Graph exploded")

        with patch(
            "shieldops.agents.threat_automation.runner.create_threat_automation_graph"
        ) as mock_graph_fn:
            mock_graph = MagicMock()
            mock_graph.compile.return_value = mock_app
            mock_graph_fn.return_value = mock_graph
            runner = ThreatAutomationRunner()
            result = await runner.hunt(hunt_id="hunt-x")

        assert result.error == "Graph exploded"
        assert result.current_step == "failed"

    @pytest.mark.asyncio
    async def test_hunt_with_config(self):
        mock_app = AsyncMock()
        final_state = ThreatAutomationState(
            hunt_id="hunt-cfg",
            hunt_config={"scope": "network"},
            current_step="complete",
        ).model_dump()
        mock_app.ainvoke.return_value = final_state

        with patch(
            "shieldops.agents.threat_automation.runner.create_threat_automation_graph"
        ) as mock_graph_fn:
            mock_graph = MagicMock()
            mock_graph.compile.return_value = mock_app
            mock_graph_fn.return_value = mock_graph
            runner = ThreatAutomationRunner()
            result = await runner.hunt(hunt_id="hunt-cfg", hunt_config={"scope": "network"})

        assert result.hunt_config["scope"] == "network"

    def test_get_result_found(self):
        with patch(
            "shieldops.agents.threat_automation.runner.create_threat_automation_graph"
        ) as mock_graph_fn:
            mock_graph = MagicMock()
            mock_graph.compile.return_value = MagicMock()
            mock_graph_fn.return_value = mock_graph
            runner = ThreatAutomationRunner()
            runner._results["ta-test"] = ThreatAutomationState(hunt_id="hunt-001")
            assert runner.get_result("ta-test") is not None
            assert runner.get_result("ta-test").hunt_id == "hunt-001"

    def test_get_result_not_found(self):
        with patch(
            "shieldops.agents.threat_automation.runner.create_threat_automation_graph"
        ) as mock_graph_fn:
            mock_graph = MagicMock()
            mock_graph.compile.return_value = MagicMock()
            mock_graph_fn.return_value = mock_graph
            runner = ThreatAutomationRunner()
            assert runner.get_result("nonexistent") is None


# -- TestNodes ---------------------------------------------------------------


class TestNodes:
    @pytest.mark.asyncio
    async def test_detect_threats_with_scope(self):
        state = ThreatAutomationState(
            hunt_id="hunt-001",
            hunt_config={"scope": "network"},
        )
        result = await detect_threats(state)
        assert "detected_threats" in result
        assert result["threat_count"] >= 1
        assert result["current_step"] == "detect_threats"
        assert len(result["reasoning_chain"]) == 1

    @pytest.mark.asyncio
    async def test_detect_threats_empty_scope(self):
        state = ThreatAutomationState(
            hunt_id="hunt-002",
            hunt_config={},
        )
        result = await detect_threats(state)
        assert "detected_threats" in result
        assert result["current_step"] == "detect_threats"

    @pytest.mark.asyncio
    async def test_analyze_behavior(self, threat_state: ThreatAutomationState):
        result = await analyze_behavior(threat_state)
        assert "behavior_analyses" in result
        assert result["current_step"] == "analyze_behavior"

    @pytest.mark.asyncio
    async def test_correlate_intelligence(self, threat_state: ThreatAutomationState):
        result = await correlate_intelligence(threat_state)
        assert "intel_correlations" in result
        assert "critical_count" in result
        assert result["current_step"] == "correlate_intelligence"

    @pytest.mark.asyncio
    async def test_automate_response(self, threat_state: ThreatAutomationState):
        threat_state.critical_count = 2
        result = await automate_response(threat_state)
        assert "response_actions" in result
        assert "automated_responses" in result
        assert result["current_step"] == "automate_response"

    @pytest.mark.asyncio
    async def test_finalize_hunt_records_duration(self):
        state = ThreatAutomationState(
            hunt_id="hunt-final",
            session_start=datetime.now(UTC),
        )
        result = await finalize_hunt(state)
        assert result["session_duration_ms"] >= 0
        assert result["current_step"] == "complete"

    @pytest.mark.asyncio
    async def test_finalize_hunt_no_session_start(self):
        state = ThreatAutomationState(hunt_id="hunt-no-start")
        result = await finalize_hunt(state)
        assert result["session_duration_ms"] == 0

    @pytest.mark.asyncio
    async def test_detect_threats_sets_session_start(self):
        state = ThreatAutomationState(
            hunt_id="hunt-start",
            hunt_config={"scope": "test.net"},
        )
        result = await detect_threats(state)
        assert result["session_start"] is not None

    @pytest.mark.asyncio
    async def test_detect_threats_reasoning_chain_grows(self):
        state = ThreatAutomationState(
            hunt_id="hunt-chain",
            hunt_config={"scope": "chain.net"},
            reasoning_chain=[
                ThreatReasoningStep(
                    step_number=1, action="prev", input_summary="", output_summary=""
                )
            ],
        )
        result = await detect_threats(state)
        assert len(result["reasoning_chain"]) == 2
        assert result["reasoning_chain"][-1].action == "detect_threats"

    @pytest.mark.asyncio
    async def test_analyze_behavior_risk_score(self, threat_state: ThreatAutomationState):
        result = await analyze_behavior(threat_state)
        assert isinstance(result["behavior_analyses"], list)

    @pytest.mark.asyncio
    async def test_correlate_intelligence_counts(self, threat_state: ThreatAutomationState):
        result = await correlate_intelligence(threat_state)
        assert isinstance(result["critical_count"], int)


# -- TestConditionalEdges ----------------------------------------------------


class TestConditionalEdges:
    def test_should_analyze_with_threats(self):
        state = ThreatAutomationState(threat_count=5)
        assert should_analyze(state) == "analyze_behavior"

    def test_should_analyze_no_threats(self):
        state = ThreatAutomationState(threat_count=0)
        assert should_analyze(state) == "finalize_hunt"

    def test_should_analyze_with_error(self):
        state = ThreatAutomationState(threat_count=5, error="failed")
        assert should_analyze(state) == "finalize_hunt"

    def test_should_respond_with_critical(self):
        state = ThreatAutomationState(critical_count=3)
        assert should_respond(state) == "automate_response"

    def test_should_respond_no_critical(self):
        state = ThreatAutomationState(critical_count=0)
        assert should_respond(state) == "finalize_hunt"

    def test_should_analyze_zero_threats_no_error(self):
        state = ThreatAutomationState(threat_count=0, error=None)
        assert should_analyze(state) == "finalize_hunt"

    def test_should_analyze_one_threat(self):
        state = ThreatAutomationState(threat_count=1)
        assert should_analyze(state) == "analyze_behavior"

    def test_should_respond_one_critical(self):
        state = ThreatAutomationState(critical_count=1)
        assert should_respond(state) == "automate_response"

    def test_should_respond_many_critical(self):
        state = ThreatAutomationState(critical_count=100)
        assert should_respond(state) == "automate_response"


# -- TestToolkitManagement ---------------------------------------------------


class TestToolkitManagement:
    def test_get_toolkit_returns_default_when_none_set(self):
        toolkit = _get_toolkit()
        assert isinstance(toolkit, ThreatAutomationToolkit)

    def test_set_toolkit_is_used_by_get_toolkit(self):
        custom = ThreatAutomationToolkit(threat_detector=MagicMock())
        set_toolkit(custom)
        assert _get_toolkit() is custom

    def test_set_toolkit_overrides_previous(self):
        first = ThreatAutomationToolkit()
        second = ThreatAutomationToolkit(threat_detector=MagicMock())
        set_toolkit(first)
        assert _get_toolkit() is first
        set_toolkit(second)
        assert _get_toolkit() is second

    def test_get_toolkit_creates_new_each_time_when_none(self):
        t1 = _get_toolkit()
        t2 = _get_toolkit()
        # Both are valid toolkits (different instances since _toolkit is None each time)
        assert isinstance(t1, ThreatAutomationToolkit)
        assert isinstance(t2, ThreatAutomationToolkit)


# -- TestIntegration ---------------------------------------------------------


class TestIntegration:
    @pytest.mark.asyncio
    async def test_full_workflow_no_threats(self):
        """Hunt with no scope discovers nothing, goes to finalize."""
        state = ThreatAutomationState(
            hunt_id="hunt-int-1",
            hunt_config={},
        )
        result = await detect_threats(state)
        assert result["current_step"] == "detect_threats"

    @pytest.mark.asyncio
    async def test_full_workflow_with_scope(self):
        """Hunt with scope detects threats, analyzes behavior."""
        state = ThreatAutomationState(
            hunt_id="hunt-int-2",
            hunt_config={"scope": "network"},
        )
        detect_result = await detect_threats(state)
        assert detect_result["threat_count"] >= 1

        state_after_detection = ThreatAutomationState(**{**state.model_dump(), **detect_result})
        analyze_result = await analyze_behavior(state_after_detection)
        assert "behavior_analyses" in analyze_result

    @pytest.mark.asyncio
    async def test_full_workflow_finalize(self):
        """Finalize correctly records duration with session_start set."""
        state = ThreatAutomationState(
            hunt_id="hunt-int-3",
            session_start=datetime.now(UTC),
            threat_count=2,
            critical_count=0,
        )
        result = await finalize_hunt(state)
        assert result["current_step"] == "complete"
        assert result["session_duration_ms"] >= 0

    @pytest.mark.asyncio
    async def test_full_workflow_detect_then_check_conditional(self):
        """Detect threats, then check conditional edge routes correctly."""
        state = ThreatAutomationState(
            hunt_id="hunt-int-4",
            hunt_config={"scope": "network"},
        )
        result = await detect_threats(state)
        state_after = ThreatAutomationState(**{**state.model_dump(), **result})
        # With threats detected, should route to analyze
        assert should_analyze(state_after) == "analyze_behavior"

    @pytest.mark.asyncio
    async def test_full_workflow_correlate_then_check_respond(
        self, threat_state: ThreatAutomationState
    ):
        """Correlate intelligence, then check respond conditional edge."""
        result = await correlate_intelligence(threat_state)
        state_after = ThreatAutomationState(**{**threat_state.model_dump(), **result})
        # With critical threats (from fixture), should route to response or finalize
        if state_after.critical_count > 0:
            assert should_respond(state_after) == "automate_response"
        else:
            assert should_respond(state_after) == "finalize_hunt"

    @pytest.mark.asyncio
    async def test_full_workflow_error_skips_analysis(self):
        """Error state should skip analysis and go to finalize."""
        state = ThreatAutomationState(
            hunt_id="hunt-int-err",
            threat_count=5,
            error="timeout",
        )
        assert should_analyze(state) == "finalize_hunt"

    @pytest.mark.asyncio
    async def test_full_workflow_no_critical_skips_response(self):
        """No critical threats should skip response and go to finalize."""
        state = ThreatAutomationState(
            hunt_id="hunt-int-nocrits",
            threat_count=3,
            critical_count=0,
        )
        assert should_respond(state) == "finalize_hunt"

    @pytest.mark.asyncio
    async def test_full_workflow_detect_analyze_correlate(self):
        """Full path through detect -> analyze -> correlate."""
        state = ThreatAutomationState(
            hunt_id="hunt-int-full",
            hunt_config={"scope": "full.internal.net"},
        )
        d_result = await detect_threats(state)
        state2 = ThreatAutomationState(**{**state.model_dump(), **d_result})

        a_result = await analyze_behavior(state2)
        state3 = ThreatAutomationState(**{**state2.model_dump(), **a_result})

        c_result = await correlate_intelligence(state3)
        assert c_result["current_step"] == "correlate_intelligence"
        assert "critical_count" in c_result
