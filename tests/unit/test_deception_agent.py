"""Tests for the Deception Agent LangGraph workflow.

Covers:
- DeceptionState model creation, defaults, and field types
- Sub-models: DeceptionAsset, HoneypotInteraction, ReasoningStep
- Prompt schemas: BehaviorAnalysisOutput
- DeceptionToolkit initialization and async methods
- Graph creation (create_deception_graph returns a StateGraph)
- DeceptionRunner initialization and list_results
- Node functions (deploy_assets, monitor_interactions, analyze_behavior,
  extract_indicators, respond_to_threat, update_strategy, generate_report)
  with mock state
- Conditional edges (should_analyze, should_respond)
- Integration: full workflow with simple inputs
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shieldops.agents.deception.graph import (
    create_deception_graph,
    should_analyze,
    should_respond,
)
from shieldops.agents.deception.models import (
    DeceptionAsset,
    DeceptionState,
    HoneypotInteraction,
    ReasoningStep,
)
from shieldops.agents.deception.nodes import (
    _get_toolkit,
    analyze_behavior,
    deploy_assets,
    extract_indicators,
    generate_report,
    monitor_interactions,
    respond_to_threat,
    set_toolkit,
    update_strategy,
)
from shieldops.agents.deception.prompts import BehaviorAnalysisOutput
from shieldops.agents.deception.runner import DeceptionRunner
from shieldops.agents.deception.tools import DeceptionToolkit

# -- Fixtures ----------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_toolkit():
    """Reset the module-level toolkit singleton between tests."""
    import shieldops.agents.deception.nodes as nodes_mod

    original = nodes_mod._toolkit
    nodes_mod._toolkit = None
    yield
    nodes_mod._toolkit = original


@pytest.fixture
def base_state() -> DeceptionState:
    return DeceptionState(
        campaign_id="camp-001",
        campaign_type="honeypot",
    )


@pytest.fixture
def active_state() -> DeceptionState:
    return DeceptionState(
        campaign_id="camp-002",
        campaign_type="honeytoken",
        deployed_assets=[
            {"asset_id": "hp-01", "asset_type": "ssh_honeypot", "status": "active"},
            {"asset_id": "ht-01", "asset_type": "honeytoken", "status": "active"},
        ],
        interactions=[
            {"source_ip": "10.0.0.99", "action": "ssh_login", "severity": "medium"},
            {"source_ip": "10.0.0.99", "action": "file_access", "severity": "high"},
        ],
        interaction_detected=True,
        behavioral_analysis={
            "attacker_profile": "Intermediate threat actor",
            "techniques": ["T1021", "T1083"],
            "sophistication_level": "intermediate",
            "intent": "reconnaissance",
        },
        severity_level="medium",
        extracted_indicators=["10.0.0.99", "evil_tool.exe"],
    )


# -- TestState ---------------------------------------------------------------


class TestState:
    def test_default_values(self):
        state = DeceptionState()
        assert state.campaign_id == ""
        assert state.campaign_type == ""
        assert state.deployed_assets == []
        assert state.interactions == []
        assert state.interaction_detected is False
        assert state.behavioral_analysis == {}
        assert state.extracted_indicators == []
        assert state.severity_level == "low"
        assert state.containment_triggered is False
        assert state.strategy_updates == []
        assert state.report == {}
        assert state.session_start is None
        assert state.session_duration_ms == 0
        assert state.reasoning_chain == []
        assert state.current_step == "init"
        assert state.error is None

    def test_creation_with_custom_values(self, base_state: DeceptionState):
        assert base_state.campaign_id == "camp-001"
        assert base_state.campaign_type == "honeypot"

    def test_list_fields_are_independent(self):
        s1 = DeceptionState()
        s2 = DeceptionState()
        s1.deployed_assets.append({"asset_id": "hp-x"})
        assert s2.deployed_assets == []

    def test_state_with_error(self):
        state = DeceptionState(error="deployment failed", current_step="failed")
        assert state.error == "deployment failed"
        assert state.current_step == "failed"

    def test_state_with_all_tracking_fields(self):
        now = datetime.now(UTC)
        step = ReasoningStep(
            step_number=1,
            action="deploy_assets",
            input_summary="Deploying",
            output_summary="Deployed",
        )
        state = DeceptionState(
            session_start=now,
            session_duration_ms=500,
            reasoning_chain=[step],
            current_step="deploy_assets",
        )
        assert state.session_start == now
        assert state.session_duration_ms == 500
        assert len(state.reasoning_chain) == 1


# -- TestSubModels -----------------------------------------------------------


class TestSubModels:
    def test_deception_asset_defaults(self):
        asset = DeceptionAsset()
        assert asset.asset_id == ""
        assert asset.asset_type == ""
        assert asset.location == ""
        assert asset.status == "pending"
        assert asset.config == {}

    def test_deception_asset_with_values(self):
        asset = DeceptionAsset(
            asset_id="hp-001",
            asset_type="ssh_honeypot",
            location="dmz",
            status="active",
            config={"port": 22, "banner": "OpenSSH_8.2"},
        )
        assert asset.asset_id == "hp-001"
        assert asset.status == "active"
        assert asset.config["port"] == 22

    def test_honeypot_interaction_defaults(self):
        interaction = HoneypotInteraction()
        assert interaction.timestamp == ""
        assert interaction.source_ip == ""
        assert interaction.action == ""
        assert interaction.payload_hash == ""
        assert interaction.severity == "low"

    def test_honeypot_interaction_with_values(self):
        interaction = HoneypotInteraction(
            timestamp="2026-01-15T10:30:00Z",
            source_ip="192.168.1.50",
            action="brute_force_ssh",
            payload_hash="abc123",
            severity="high",
        )
        assert interaction.source_ip == "192.168.1.50"
        assert interaction.severity == "high"

    def test_reasoning_step_creation(self):
        step = ReasoningStep(
            step_number=1,
            action="deploy_assets",
            input_summary="Campaign camp-001",
            output_summary="Deployed 3 assets",
        )
        assert step.step_number == 1
        assert step.duration_ms == 0
        assert step.tool_used is None

    def test_reasoning_step_with_tool(self):
        step = ReasoningStep(
            step_number=2,
            action="monitor_interactions",
            input_summary="Monitoring 3 assets",
            output_summary="Found 5 interactions",
            duration_ms=200,
            tool_used="interaction_monitor",
        )
        assert step.tool_used == "interaction_monitor"
        assert step.duration_ms == 200


# -- TestPromptSchemas -------------------------------------------------------


class TestPromptSchemas:
    def test_behavior_analysis_output_fields(self):
        output = BehaviorAnalysisOutput(
            attacker_profile="Advanced threat actor using custom tools",
            techniques=["T1059", "T1021", "T1083"],
            sophistication_level="advanced",
            intent="exploitation",
        )
        assert output.sophistication_level == "advanced"
        assert len(output.techniques) == 3
        assert output.intent == "exploitation"


# -- TestToolkit -------------------------------------------------------------


class TestToolkit:
    def test_toolkit_initialization_with_no_deps(self):
        toolkit = DeceptionToolkit()
        assert toolkit._honeypot_manager is None
        assert toolkit._interaction_monitor is None
        assert toolkit._behavior_analyzer is None

    def test_toolkit_initialization_with_deps(self):
        mock_manager = MagicMock()
        toolkit = DeceptionToolkit(honeypot_manager=mock_manager)
        assert toolkit._honeypot_manager is mock_manager

    @pytest.mark.asyncio
    async def test_deploy_assets_returns_list(self):
        toolkit = DeceptionToolkit()
        result = await toolkit.deploy_assets("honeypot", {"port": 22})
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_monitor_interactions_returns_list(self):
        toolkit = DeceptionToolkit()
        result = await toolkit.monitor_interactions(["hp-01", "ht-01"])
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_analyze_behavior_returns_expected_keys(self):
        toolkit = DeceptionToolkit()
        result = await toolkit.analyze_behavior([{"action": "ssh_login"}])
        assert "attacker_profile" in result
        assert "techniques" in result
        assert "sophistication_level" in result
        assert "intent" in result

    @pytest.mark.asyncio
    async def test_extract_indicators_returns_list(self):
        toolkit = DeceptionToolkit()
        result = await toolkit.extract_indicators([{"source_ip": "10.0.0.1"}])
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_trigger_containment_returns_status(self):
        toolkit = DeceptionToolkit()
        result = await toolkit.trigger_containment("camp-001", "critical")
        assert result["status"] == "triggered"
        assert result["campaign_id"] == "camp-001"

    @pytest.mark.asyncio
    async def test_generate_report_returns_draft(self):
        toolkit = DeceptionToolkit()
        result = await toolkit.generate_report({"campaign_id": "camp-001"})
        assert result["status"] == "draft"


# -- TestGraph ---------------------------------------------------------------


class TestGraph:
    def test_create_deception_graph_returns_state_graph(self):
        graph = create_deception_graph()
        assert graph is not None
        assert hasattr(graph, "compile")

    def test_graph_has_expected_nodes(self):
        graph = create_deception_graph()
        node_names = set(graph.nodes.keys())
        expected = {
            "deploy_assets",
            "monitor_interactions",
            "analyze_behavior",
            "extract_indicators",
            "respond_to_threat",
            "update_strategy",
            "generate_report",
        }
        assert expected.issubset(node_names)

    def test_graph_compiles_without_error(self):
        graph = create_deception_graph()
        app = graph.compile()
        assert app is not None


# -- TestRunner --------------------------------------------------------------


class TestRunner:
    def test_runner_initialization(self):
        with patch("shieldops.agents.deception.runner.create_deception_graph") as mock_graph_fn:
            mock_graph = MagicMock()
            mock_graph.compile.return_value = MagicMock()
            mock_graph_fn.return_value = mock_graph
            runner = DeceptionRunner()
            assert runner._results == {}

    def test_list_results_empty(self):
        with patch("shieldops.agents.deception.runner.create_deception_graph") as mock_graph_fn:
            mock_graph = MagicMock()
            mock_graph.compile.return_value = MagicMock()
            mock_graph_fn.return_value = mock_graph
            runner = DeceptionRunner()
            assert runner.list_results() == []

    def test_list_results_returns_summaries(self):
        with patch("shieldops.agents.deception.runner.create_deception_graph") as mock_graph_fn:
            mock_graph = MagicMock()
            mock_graph.compile.return_value = MagicMock()
            mock_graph_fn.return_value = mock_graph
            runner = DeceptionRunner()
            runner._results["deception-abc"] = DeceptionState(
                campaign_id="camp-001",
                campaign_type="honeypot",
                interaction_detected=True,
                severity_level="high",
                containment_triggered=True,
                current_step="complete",
            )
            summaries = runner.list_results()
            assert len(summaries) == 1
            assert summaries[0]["campaign_id"] == "camp-001"
            assert summaries[0]["interaction_detected"] is True
            assert summaries[0]["severity_level"] == "high"
            assert summaries[0]["containment_triggered"] is True

    @pytest.mark.asyncio
    async def test_run_campaign_success(self):
        mock_app = AsyncMock()
        final_state = DeceptionState(
            campaign_id="camp-abc",
            campaign_type="honeypot",
            interaction_detected=True,
            severity_level="medium",
            current_step="complete",
        ).model_dump()
        mock_app.ainvoke.return_value = final_state

        with patch("shieldops.agents.deception.runner.create_deception_graph") as mock_graph_fn:
            mock_graph = MagicMock()
            mock_graph.compile.return_value = mock_app
            mock_graph_fn.return_value = mock_graph
            runner = DeceptionRunner()
            result = await runner.run_campaign(campaign_type="honeypot")

        assert isinstance(result, DeceptionState)
        assert result.current_step == "complete"
        assert result.interaction_detected is True

    @pytest.mark.asyncio
    async def test_run_campaign_handles_exception(self):
        mock_app = AsyncMock()
        mock_app.ainvoke.side_effect = RuntimeError("Campaign failed")

        with patch("shieldops.agents.deception.runner.create_deception_graph") as mock_graph_fn:
            mock_graph = MagicMock()
            mock_graph.compile.return_value = mock_app
            mock_graph_fn.return_value = mock_graph
            runner = DeceptionRunner()
            result = await runner.run_campaign(campaign_type="honeypot")

        assert result.error == "Campaign failed"
        assert result.current_step == "failed"


# -- TestNodes ---------------------------------------------------------------


class TestNodes:
    @pytest.mark.asyncio
    async def test_deploy_assets(self, base_state: DeceptionState):
        result = await deploy_assets(base_state)
        assert "deployed_assets" in result
        assert result["current_step"] == "deploy_assets"
        assert "session_start" in result
        assert len(result["reasoning_chain"]) == 1

    @pytest.mark.asyncio
    async def test_monitor_interactions_no_activity(self, base_state: DeceptionState):
        result = await monitor_interactions(base_state)
        assert result["interactions"] == []
        assert result["interaction_detected"] is False
        assert result["current_step"] == "monitor_interactions"

    @pytest.mark.asyncio
    async def test_monitor_interactions_with_deployed_assets(self):
        state = DeceptionState(
            deployed_assets=[
                {"asset_id": "hp-01", "status": "active"},
                {"asset_id": "ht-01", "status": "active"},
            ],
        )
        result = await monitor_interactions(state)
        assert isinstance(result["interactions"], list)

    @pytest.mark.asyncio
    async def test_analyze_behavior_default_toolkit(self, active_state: DeceptionState):
        result = await analyze_behavior(active_state)
        assert "behavioral_analysis" in result
        assert "severity_level" in result
        assert result["current_step"] == "analyze_behavior"

    @pytest.mark.asyncio
    async def test_analyze_behavior_severity_mapping(self):
        """Test that sophistication level maps to correct severity."""
        # Mock toolkit that returns advanced sophistication
        mock_toolkit = DeceptionToolkit()
        mock_toolkit.analyze_behavior = AsyncMock(
            return_value={
                "sophistication_level": "apt",
                "techniques": ["T1059"],
            }
        )
        set_toolkit(mock_toolkit)

        state = DeceptionState(interactions=[{"action": "test"}])
        result = await analyze_behavior(state)
        assert result["severity_level"] == "critical"

    @pytest.mark.asyncio
    async def test_analyze_behavior_unknown_sophistication(self):
        mock_toolkit = DeceptionToolkit()
        mock_toolkit.analyze_behavior = AsyncMock(
            return_value={
                "sophistication_level": "unknown",
            }
        )
        set_toolkit(mock_toolkit)

        state = DeceptionState(interactions=[{"action": "test"}])
        result = await analyze_behavior(state)
        assert result["severity_level"] == "low"

    @pytest.mark.asyncio
    async def test_extract_indicators(self, active_state: DeceptionState):
        result = await extract_indicators(active_state)
        assert isinstance(result["extracted_indicators"], list)
        assert result["current_step"] == "extract_indicators"

    @pytest.mark.asyncio
    async def test_respond_to_threat_critical(self):
        state = DeceptionState(
            campaign_id="camp-crit",
            severity_level="critical",
        )
        result = await respond_to_threat(state)
        assert result["containment_triggered"] is True
        assert result["current_step"] == "respond_to_threat"

    @pytest.mark.asyncio
    async def test_respond_to_threat_high(self):
        state = DeceptionState(
            campaign_id="camp-high",
            severity_level="high",
        )
        result = await respond_to_threat(state)
        assert result["containment_triggered"] is True

    @pytest.mark.asyncio
    async def test_respond_to_threat_medium_no_containment(self):
        state = DeceptionState(
            campaign_id="camp-med",
            severity_level="medium",
        )
        result = await respond_to_threat(state)
        assert result["containment_triggered"] is False

    @pytest.mark.asyncio
    async def test_respond_to_threat_low_no_containment(self):
        state = DeceptionState(
            campaign_id="camp-low",
            severity_level="low",
        )
        result = await respond_to_threat(state)
        assert result["containment_triggered"] is False

    @pytest.mark.asyncio
    async def test_update_strategy_advanced_attacker(self):
        state = DeceptionState(
            behavioral_analysis={"sophistication_level": "advanced"},
            extracted_indicators=["10.0.0.1", "evil.exe"],
            severity_level="high",
        )
        result = await update_strategy(state)
        updates = result["strategy_updates"]
        assert len(updates) == 2
        actions = [u["action"] for u in updates]
        assert "increase_complexity" in actions
        assert "deploy_targeted_honeytokens" in actions
        assert result["current_step"] == "update_strategy"

    @pytest.mark.asyncio
    async def test_update_strategy_apt_attacker(self):
        state = DeceptionState(
            behavioral_analysis={"sophistication_level": "apt"},
            extracted_indicators=[],
        )
        result = await update_strategy(state)
        updates = result["strategy_updates"]
        assert len(updates) == 1
        assert updates[0]["action"] == "increase_complexity"

    @pytest.mark.asyncio
    async def test_update_strategy_low_sophistication(self):
        state = DeceptionState(
            behavioral_analysis={"sophistication_level": "script_kiddie"},
            extracted_indicators=[],
        )
        result = await update_strategy(state)
        assert result["strategy_updates"] == []

    @pytest.mark.asyncio
    async def test_generate_report(self, active_state: DeceptionState):
        active_state.session_start = datetime.now(UTC)
        result = await generate_report(active_state)
        assert "report" in result
        assert result["report"]["status"] == "draft"
        assert result["session_duration_ms"] >= 0
        assert result["current_step"] == "complete"

    @pytest.mark.asyncio
    async def test_generate_report_no_session_start(self):
        state = DeceptionState(campaign_id="camp-no-start")
        result = await generate_report(state)
        assert result["session_duration_ms"] == 0


# -- TestConditionalEdges ----------------------------------------------------


class TestConditionalEdges:
    def test_should_analyze_interaction_detected(self):
        state = DeceptionState(interaction_detected=True)
        assert should_analyze(state) == "analyze_behavior"

    def test_should_analyze_no_interaction(self):
        state = DeceptionState(interaction_detected=False)
        assert should_analyze(state) == "generate_report"

    def test_should_analyze_with_error(self):
        state = DeceptionState(interaction_detected=True, error="monitoring failed")
        assert should_analyze(state) == "generate_report"

    def test_should_respond_critical(self):
        state = DeceptionState(severity_level="critical")
        assert should_respond(state) == "respond_to_threat"

    def test_should_respond_high(self):
        state = DeceptionState(severity_level="high")
        assert should_respond(state) == "respond_to_threat"

    def test_should_respond_medium(self):
        state = DeceptionState(severity_level="medium")
        assert should_respond(state) == "update_strategy"

    def test_should_respond_low(self):
        state = DeceptionState(severity_level="low")
        assert should_respond(state) == "update_strategy"


# -- TestToolkitManagement ---------------------------------------------------


class TestToolkitManagement:
    def test_get_toolkit_returns_default_when_none_set(self):
        toolkit = _get_toolkit()
        assert isinstance(toolkit, DeceptionToolkit)

    def test_set_toolkit_is_used_by_get_toolkit(self):
        custom = DeceptionToolkit(honeypot_manager=MagicMock())
        set_toolkit(custom)
        assert _get_toolkit() is custom


# -- TestIntegration ---------------------------------------------------------


class TestIntegration:
    @pytest.mark.asyncio
    async def test_full_workflow_no_interactions(self, base_state: DeceptionState):
        """No interactions detected: deploy -> monitor -> report."""
        r1 = await deploy_assets(base_state)
        state = DeceptionState(**{**base_state.model_dump(), **r1})
        assert state.current_step == "deploy_assets"

        r2 = await monitor_interactions(state)
        state = DeceptionState(**{**state.model_dump(), **r2})
        assert state.interaction_detected is False

        # Conditional: should go to report
        assert should_analyze(state) == "generate_report"

        state.session_start = datetime.now(UTC)
        r3 = await generate_report(state)
        assert r3["current_step"] == "complete"

    @pytest.mark.asyncio
    async def test_full_workflow_with_interactions_medium_severity(self):
        """Interactions with medium severity: deploy -> monitor -> analyze ->
        extract -> update_strategy -> report."""
        state = DeceptionState(
            campaign_id="camp-int",
            campaign_type="honeypot",
        )

        r1 = await deploy_assets(state)
        state = DeceptionState(**{**state.model_dump(), **r1})

        # Simulate interactions found
        state.interactions = [{"source_ip": "10.0.0.1", "action": "scan"}]
        state.interaction_detected = True

        assert should_analyze(state) == "analyze_behavior"

        r3 = await analyze_behavior(state)
        state = DeceptionState(**{**state.model_dump(), **r3})

        r4 = await extract_indicators(state)
        state = DeceptionState(**{**state.model_dump(), **r4})

        # Medium severity: should go to update_strategy, not respond_to_threat
        assert should_respond(state) == "update_strategy"

        r5 = await update_strategy(state)
        state = DeceptionState(**{**state.model_dump(), **r5})

        state.session_start = datetime.now(UTC)
        r6 = await generate_report(state)
        assert r6["current_step"] == "complete"

    @pytest.mark.asyncio
    async def test_full_workflow_high_severity_with_containment(self):
        """High severity: deploy -> monitor -> analyze -> extract ->
        respond_to_threat -> update_strategy -> report."""
        # Set up toolkit to return high severity
        mock_toolkit = DeceptionToolkit()
        mock_toolkit.analyze_behavior = AsyncMock(
            return_value={
                "attacker_profile": "Advanced persistent threat",
                "techniques": ["T1059", "T1021"],
                "sophistication_level": "advanced",
                "intent": "exploitation",
            }
        )
        mock_toolkit.extract_indicators = AsyncMock(return_value=["10.0.0.99"])
        mock_toolkit.trigger_containment = AsyncMock(
            return_value={"status": "triggered", "campaign_id": "camp-high"}
        )
        mock_toolkit.generate_report = AsyncMock(
            return_value={"status": "draft", "report_id": "rpt-1"}
        )
        set_toolkit(mock_toolkit)

        state = DeceptionState(
            campaign_id="camp-high",
            campaign_type="honeypot",
            deployed_assets=[{"asset_id": "hp-01"}],
            interactions=[{"source_ip": "10.0.0.99", "action": "exploit"}],
            interaction_detected=True,
        )

        r1 = await analyze_behavior(state)
        state = DeceptionState(**{**state.model_dump(), **r1})
        assert state.severity_level == "high"

        r2 = await extract_indicators(state)
        state = DeceptionState(**{**state.model_dump(), **r2})

        assert should_respond(state) == "respond_to_threat"

        r3 = await respond_to_threat(state)
        state = DeceptionState(**{**state.model_dump(), **r3})
        assert state.containment_triggered is True

        r4 = await update_strategy(state)
        state = DeceptionState(**{**state.model_dump(), **r4})
        assert len(state.strategy_updates) >= 1

        state.session_start = datetime.now(UTC)
        r5 = await generate_report(state)
        assert r5["current_step"] == "complete"
